SELECT b.hkmovie6_code, a.showtime_code
FROM Showtimes as a
INNER JOIN Movies as b on a.MovieID = b.MovieID
-- ! - where movie is still showing, showtime is unknown, show is scraped to db within 3 days
WHERE b.InTheatre = 1 
AND (a.start_time is null and datetime(a.EnteredDate, 'unixepoch', 'localtime') >= DATE('now', '-10 days'))
LIMIT 1000
