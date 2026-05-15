-- ============================================================
-- SkyRoute — Data Import Script (SQL Server / SSMS)
-- Run AFTER schema.sql has been executed
-- IMPORTANT: Update @datapath below to match where your
-- CSV files are saved on your laptop before running
-- ============================================================

-- Update this to your actual path (use double backslashes)
-- Example: C:\Users\USER\Downloads\files\skyroute\data\
DECLARE @datapath NVARCHAR(300) = 'C:\Users\USER\Downloads\files\skyroute_M2_ZDA24B036\skyroute\data\';

-- city
BULK INSERT city
FROM 'C:\Users\USER\Downloads\files\skyroute_M2_ZDA24B036\skyroute\data\cities.csv'
WITH (FIRSTROW=2, FIELDTERMINATOR=',', ROWTERMINATOR='\n', TABLOCK);

-- airline
BULK INSERT airline
FROM 'C:\Users\USER\Downloads\files\skyroute_M2_ZDA24B036\skyroute\data\airlines.csv'
WITH (FIRSTROW=2, FIELDTERMINATOR=',', ROWTERMINATOR='\n', TABLOCK);

-- users
BULK INSERT users
FROM 'C:\Users\USER\Downloads\files\skyroute_M2_ZDA24B036\skyroute\data\users.csv'
WITH (FIRSTROW=2, FIELDTERMINATOR=',', ROWTERMINATOR='\n', TABLOCK);

-- flight
BULK INSERT flight
FROM 'C:\Users\USER\Downloads\files\skyroute_M2_ZDA24B036\skyroute\data\flights.csv'
WITH (FIRSTROW=2, FIELDTERMINATOR=',', ROWTERMINATOR='\n', TABLOCK);

-- flight_price
BULK INSERT flight_price
FROM 'C:\Users\USER\Downloads\files\skyroute_M2_ZDA24B036\skyroute\data\flight_prices.csv'
WITH (FIRSTROW=2, FIELDTERMINATOR=',', ROWTERMINATOR='\n', TABLOCK);

-- booking
BULK INSERT booking
FROM 'C:\Users\USER\Downloads\files\skyroute_M2_ZDA24B036\skyroute\data\bookings.csv'
WITH (FIRSTROW=2, FIELDTERMINATOR=',', ROWTERMINATOR='\n', TABLOCK);

-- verify row counts
SELECT 'city'         AS tbl, COUNT(*) AS rows FROM city
UNION ALL SELECT 'airline',      COUNT(*) FROM airline
UNION ALL SELECT 'users',        COUNT(*) FROM users
UNION ALL SELECT 'flight',       COUNT(*) FROM flight
UNION ALL SELECT 'flight_price', COUNT(*) FROM flight_price
UNION ALL SELECT 'booking',      COUNT(*) FROM booking;
