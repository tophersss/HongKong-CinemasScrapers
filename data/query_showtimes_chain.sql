SELECT a.hkmovie6_code, a.showtime_code FROM SalesDetails as a 
INNER JOIN Houses as b on a.HouseID = b.HouseID
INNER JOIN Theatres as c on b.TheatreID = c.TheatreID
WHERE c.chain = 'Golden Harvest'
ORDER BY a.showtimeID
LIMIT 1000
OFFSET @n