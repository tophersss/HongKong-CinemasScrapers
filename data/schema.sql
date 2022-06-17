CREATE TABLE IF NOT EXISTS Movies ( MovieID integer PRIMARY KEY, hkmovie6_code text NOT NULL UNIQUE, name text NOT NULL, name_en text, synopsis text, release_date text, duration integer, category text, InTheatre integer NOT NULL, ModifiedDate integer(4) NOT NULL DEFAULT (strftime('%s','now')), EnteredDate integer(4) NOT NULL DEFAULT (strftime('%s','now')) );
CREATE TABLE IF NOT EXISTS Reactions ( ReactionID integer PRIMARY KEY, rating integer, like integer, comment_count integer, MovieID integer NOT NULL, EnteredDate integer(4) NOT NULL DEFAULT (strftime('%s','now')) );
CREATE TABLE IF NOT EXISTS Showtimes (ShowtimeID integer PRIMARY KEY, showtime_code text NOT NULL UNIQUE, HouseID integer, MovieID integer NOT NULL, start_time integer (4), EnteredDate integer (4) NOT NULL DEFAULT (strftime('%s', 'now')), price INTEGER);
CREATE TABLE IF NOT EXISTS Seats (SeatID integer PRIMARY KEY, seat_number text, HouseID integer, x INTEGER (4), y INTEGER (4), EnteredDate integer (4) NOT NULL DEFAULT (strftime('%s', 'now')));
CREATE TABLE IF NOT EXISTS SalesHistory (
    ID          INTEGER     PRIMARY KEY,
    SeatID      INTEGER     ,
    ShowtimeID  INTEGER,
    EnteredDate INTEGER (4) NOT NULL
                            DEFAULT (strftime('%s', 'now') ) ,
    UNIQUE(SeatID, ShowtimeID)
);
CREATE TABLE IF NOT EXISTS Theatres (
    TheatreID  INTEGER        PRIMARY KEY
                              UNIQUE,
    name       TEXT,
    name_en    TEXT,
    latitude   DECIMAL (8, 5),
    longitude  DECIMAL (9, 5),
    chain      TEXT,
    DistrictID INT
);
CREATE TABLE IF NOT EXISTS Districts (DistrictID INTEGER PRIMARY KEY, name TEXT, name_en TEXT);
CREATE TABLE IF NOT EXISTS Houses (HouseID integer PRIMARY KEY, name text NOT NULL, capacity INTEGER, svg TEXT, alias1, TheatreID integer, EnteredDate integer (4) NOT NULL DEFAULT (strftime('%s', 'now')));
CREATE INDEX IF NOT EXISTS Movies_indices ON Movies (hkmovie6_code, name, name_en);
CREATE INDEX IF NOT EXISTS Theatres_indices ON Theatres (name, name_en);
CREATE INDEX IF NOT EXISTS Showtimes_indices ON Showtimes (showtime_code, HouseID, MovieID);
CREATE VIEW IF NOT EXISTS SalesDetails AS WITH base AS (
    SELECT
        b.hkmovie6_code
        , b.MovieID
        , a.showtimeID
        , a.showtime_code
        , b.name
        , d.houseID
        , d.name as 'house_name'
        , datetime(a.start_time, 'unixepoch', 'localtime') as 'movie_starttime'
        , CASE WHEN a.start_time is null THEN -1 WHEN b.InTheatre = 1 and datetime(a.start_time, 'unixepoch', 'localtime') >= DATE('now') THEN 0 ELSE 1 END AS 'showed'
        , strftime('%w', datetime(a.start_time, 'unixepoch', 'localtime')) as 'weekday'
        , time(datetime(a.start_time, 'unixepoch', 'localtime')) as 'hour'
        , CASE 
            WHEN a.start_time is null THEN null
            WHEN time(datetime(a.start_time, 'unixepoch', 'localtime')) between '18:00:00' and '23:59:00' then 'night'
            ELSE 'day'
        END as 'time_check'
        , d.capacity
        , COUNT(c.ID) as 'ticket_sold'
        , COUNT(c.ID) * a.price as 'profit'
    FROM Showtimes AS a
    INNER JOIN Movies AS b
        ON a.MovieID = b.MovieID
    LEFT JOIN SalesHistory AS c
        ON a.ShowtimeID = c.ShowtimeID
    LEFT JOIN Houses AS d
        ON a.HouseID = d.HouseID
    GROUP BY a.showtime_code
        , b.hkmovie6_code
        , b.name
        , a.start_time
)
, timeslot_average AS (
    SELECT DISTINCT
        base.weekday || base.time_check AS 'timeslot'
        , (SUM(ticket_sold) OVER (PARTITION BY (base.weekday || base.time_check))) * 1.0 / (COUNT() OVER (PARTITION BY (base.weekday || base.time_check))) AS 'avg_tickets_sold_per_timeslot'
    FROM base
    WHERE base.weekday IS NOT NULL AND base.time_check IS NOT NULL
)
, house_average AS (
    SELECT DISTINCT
        base.houseID
        , (SUM(ticket_sold) OVER (PARTITION BY (base.houseID))) * 1.0 / (COUNT() OVER (PARTITION BY (base.houseID))) AS 'avg_tickets_sold_per_house'
    FROM base
    WHERE base.houseID IS NOT NULL
)
SELECT base.*, timeslot_average.*, house_average.avg_tickets_sold_per_house FROM base
LEFT JOIN timeslot_average ON (base.weekday || base.time_check) = timeslot_average.timeslot
LEFT JOIN house_average ON base.houseID = house_average.houseID;
CREATE VIEW IF NOT EXISTS OpeningWeekendSales AS SELECT * FROM (
    
    SELECT
        main.*
        , SUM(main.profit) OVER(PARTITION BY main.name ORDER BY main.name, main.[day#]) as 'acc'
        , COUNT(*) OVER(PARTITION BY main.name) as 'cnt'
    FROM (
    SELECT 
        a.name
        , a.MovieID
        , DATE(a.movie_starttime) as 'date'
        , SUM(a.ticket_sold) as 'ticket_sold'
        ,  ROUND(( STRFTIME('%s', DATE(a.movie_starttime)) - STRFTIME('%s', ( MIN( DATE(a.movie_starttime) ) OVER(PARTITION BY a.hkmovie6_code) ) ) ) / 86400.0 ) + 1 as 'day#'
        , a.weekday
        , SUM(a.profit) as 'profit'
    FROM SalesDetails as a
    GROUP BY a.name, a.movieid, ( DATE(a.movie_starttime) )
    ) main
    WHERE main.[day#] < 7 and main.weekday in ('5', '6', '0') and main.ticket_sold > 1000

) final
WHERE final.cnt = 3
ORDER BY final.name, final.[day#];
CREATE VIEW IF NOT EXISTS vLatestReactions AS SELECT 
  Movies.MovieID,
  Movies.hkmovie6_code,
  Movies.InTheatre,
  datetime(Movies.EnteredDate, 'unixepoch', 'localtime') AS MovieEnteredDate,
  datetime(Movies.EnteredDate, 'unixepoch', 'localtime') AS MovieModifiedDate ,
  Reactions.comment_count,
  Reactions."like",
  Reactions.rating,
  Reactions.ReactionID,
  datetime(Reactions.EnteredDate, 'unixepoch', 'localtime') AS ReactionDate
FROM Movies
LEFT JOIN Reactions ON Reactions.ReactionID =
  ( SELECT _a.ReactionID
    FROM Reactions AS _a
    WHERE _a.MovieID = Movies.MovieID
    ORDER BY _a.EnteredDate DESC LIMIT 1
  )
/* LatestReactions(MovieID,hkmovie6_code,InTheatre,MovieEnteredDate,MovieModifiedDate,comment_count,"like",rating,ReactionID,ReactionDate) */;
CREATE VIEW IF NOT EXISTS vDuplicatedShowtimes AS SELECT sd.movie_starttime, main.MovieID, main.ShowtimeID, main.houseID, sd.ticket_sold, ROW_NUMBER() OVER(PARTITION BY main.MovieID, main.houseID, main.start_time ORDER BY sd.ticket_sold desc, main.EnteredDate desc) as 'rank1-keep'  FROM Showtimes as main
INNER JOIN (
    SELECT a.start_time, a.MovieID, a.HouseID FROM Showtimes as a
    GROUP BY a.start_time, a.MovieID, a.HouseID
    HAVING COUNT(*) > 1
) dup ON main.start_time = dup.start_time and main.MovieID = dup.MovieID and main.HouseID = dup.HouseID
INNER JOIN vShowDetails as sd ON main.showtimeID = sd.showtimeID
ORDER BY main.start_time, main.MovieID, main.HouseID;
CREATE VIEW IF NOT EXISTS vSalesHistoryCount AS select a.ShowtimeID, COUNT(a.ShowtimeID) as 'cnt' from SalesHistory a 
group by a.ShowtimeID;
CREATE TRIGGER IF NOT EXISTS delete_sale_records AFTER DELETE ON Showtimes BEGIN DELETE FROM SalesHistory WHERE SalesHistory.ShowtimeID = OLD.showtimeID; END;
CREATE VIEW IF NOT EXISTS vShowDetails AS SELECT
    c.hkmovie6_code
    , c.MovieID
    , a.showtimeID
    , a.showtime_code
    , c.name
    , c.name_en
    , c.duration
    , a.price
    , d.houseID
    , d.name as 'house_name'
    , d.alias1 as 'house_alias1'
    , e.name as 'theatre'
    , e.name_en as 'theatre_en'
    , e.TheatreID
    , e.chain
    , f.name as 'district'
    , datetime(a.start_time, 'unixepoch', 'localtime') as 'movie_starttime'
    , CASE WHEN a.start_time is null THEN -1 WHEN c.InTheatre = 1 and datetime(a.start_time, 'unixepoch', 'localtime') >= DATE('now') THEN 0 ELSE 1 END AS 'showed'
    , strftime('%w', datetime(a.start_time, 'unixepoch', 'localtime')) as 'weekday'
    , time(datetime(a.start_time, 'unixepoch', 'localtime')) as 'hour'
    , CASE 
        WHEN a.start_time is null THEN null
        WHEN time(datetime(a.start_time, 'unixepoch', 'localtime')) between '18:00:00' and '23:59:00' then 'night'
        ELSE 'day'
    END as 'time_check'
    , d.capacity
    , b.cnt as 'ticket_sold'
    , b.cnt * a.price as 'profit'
    , g.comment_count
    , g.like
    , g.rating
FROM Showtimes AS a
LEFT JOIN vSalesHistoryCount AS b
    ON a.ShowtimeID = b.ShowtimeID
INNER JOIN Movies AS c
    ON a.MovieID = c.MovieID
LEFT JOIN Houses AS d
    ON a.HouseID = d.HouseID
LEFT JOIN Theatres as e
    ON d.TheatreID = e.TheatreID
LEFT JOIN Districts as f
    ON e.DistrictID = f.DistrictID
LEFT JOIN vLatestReactions as g
    ON a.MovieID = g.MovieID;
CREATE INDEX IF NOT EXISTS SalesHistory_indices ON SalesHistory (ShowtimeID);
