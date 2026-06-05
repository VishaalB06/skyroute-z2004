-- ============================================================
-- Z2004 Database Management Systems
-- Semester Project - Track B: AI Recommendation Engine
-- Project: SkyRoute — Aviation Flight Recommendation System
-- Name: AlaguVishaalBalaji | Roll No: ZDA24B036
-- File: performance.sql
-- Description: Index benchmarking + stored procedure
-- DBMS: PostgreSQL 18.4
-- ============================================================

-- ============================================================
-- SECTION 1: DROP EXISTING INDEXES (clean baseline)
-- Run this block first to get BEFORE timings
-- ============================================================

DROP INDEX IF EXISTS idx_booking_user_id;
DROP INDEX IF EXISTS idx_flight_route;
DROP INDEX IF EXISTS idx_price_flight;
DROP INDEX IF EXISTS idx_booking_flight_id;
DROP INDEX IF EXISTS idx_booking_status;


-- ============================================================
-- SECTION 2: BEFORE TIMINGS (no indexes)
-- Run EXPLAIN ANALYZE on each query before adding indexes
-- ============================================================

-- Q1_BEFORE: User revenue aggregation (full table join)
EXPLAIN ANALYZE
SELECT
    u.full_name,
    COUNT(b.booking_id)  AS total_bookings,
    SUM(b.total_paid)    AS total_spent
FROM users u
JOIN booking b ON u.user_id = b.user_id
WHERE b.booking_status = 'Confirmed'
GROUP BY u.user_id, u.full_name
ORDER BY total_spent DESC;

-- Q2_BEFORE: Route popularity (3-way join)
EXPLAIN ANALYZE
SELECT
    f.flight_number,
    oc.city_name  AS origin,
    dc.city_name  AS destination,
    COUNT(*)      AS bookings
FROM booking b
JOIN flight f  ON b.flight_id          = f.flight_id
JOIN city   oc ON f.origin_city_id     = oc.city_id
JOIN city   dc ON f.destination_city_id = dc.city_id
WHERE b.booking_status <> 'Cancelled'
GROUP BY f.flight_id, f.flight_number, oc.city_name, dc.city_name
ORDER BY bookings DESC;

-- Q3_BEFORE: Single user booking lookup (high selectivity)
EXPLAIN ANALYZE
SELECT
    b.booking_id,
    u.full_name,
    fp.cabin_class,
    b.total_paid
FROM booking b
JOIN users        u  ON b.user_id  = u.user_id
JOIN flight_price fp ON b.price_id = fp.price_id
WHERE b.user_id = 50;


-- ============================================================
-- SECTION 3: CREATE INDEXES
-- ============================================================

-- B-Tree index on booking.user_id
-- Justification: every recommendation query filters or joins
-- on user_id. Without this, PostgreSQL does a full seq scan
-- of all 2718 booking rows for every single-user lookup.
CREATE INDEX idx_booking_user_id
    ON booking(user_id);

-- Composite B-Tree index on flight route (origin + destination)
-- Justification: collaborative filtering groups bookings by
-- route. This index allows index-only scans on both columns
-- together instead of two separate lookups.
CREATE INDEX idx_flight_route
    ON flight(origin_city_id, destination_city_id);

-- B-Tree index on flight_price.flight_id
-- Justification: booking always joins to flight_price on
-- flight_id. This eliminates a seq scan on 5092 price rows.
CREATE INDEX idx_price_flight
    ON flight_price(flight_id);

-- B-Tree index on booking.flight_id
-- Justification: supports JOIN from booking to flight table
-- in route popularity and recommendation queries.
CREATE INDEX idx_booking_flight_id
    ON booking(flight_id);

-- B-Tree index on booking.booking_status
-- Justification: every analytical query filters on
-- booking_status (Confirmed / Cancelled etc.).
CREATE INDEX idx_booking_status
    ON booking(booking_status);


-- ============================================================
-- SECTION 4: AFTER TIMINGS (with indexes)
-- Run the same queries again and compare execution plans
-- ============================================================

-- Q1_AFTER: User revenue aggregation
EXPLAIN ANALYZE
SELECT
    u.full_name,
    COUNT(b.booking_id)  AS total_bookings,
    SUM(b.total_paid)    AS total_spent
FROM users u
JOIN booking b ON u.user_id = b.user_id
WHERE b.booking_status = 'Confirmed'
GROUP BY u.user_id, u.full_name
ORDER BY total_spent DESC;

-- Q2_AFTER: Route popularity
EXPLAIN ANALYZE
SELECT
    f.flight_number,
    oc.city_name  AS origin,
    dc.city_name  AS destination,
    COUNT(*)      AS bookings
FROM booking b
JOIN flight f  ON b.flight_id          = f.flight_id
JOIN city   oc ON f.origin_city_id     = oc.city_id
JOIN city   dc ON f.destination_city_id = dc.city_id
WHERE b.booking_status <> 'Cancelled'
GROUP BY f.flight_id, f.flight_number, oc.city_name, dc.city_name
ORDER BY bookings DESC;

-- Q3_AFTER: Single user booking lookup
EXPLAIN ANALYZE
SELECT
    b.booking_id,
    u.full_name,
    fp.cabin_class,
    b.total_paid
FROM booking b
JOIN users        u  ON b.user_id  = u.user_id
JOIN flight_price fp ON b.price_id = fp.price_id
WHERE b.user_id = 50;


-- ============================================================
-- SECTION 5: STORED PROCEDURE
-- get_user_recommendations(p_user_id, p_limit)
--
-- Returns top-N flight recommendations for a given user
-- based on collaborative filtering (route popularity among
-- all users excluding routes the target user already flew).
-- Also inserts a log entry into recommendation_log table.
-- ============================================================

-- create the log table first
CREATE TABLE IF NOT EXISTS recommendation_log (
    log_id        SERIAL      PRIMARY KEY,
    user_id       INT         NOT NULL,
    generated_at  TIMESTAMP   NOT NULL DEFAULT NOW(),
    num_results   INT         NOT NULL
);

-- stored procedure
CREATE OR REPLACE FUNCTION get_user_recommendations(
    p_user_id INT,
    p_limit   INT DEFAULT 5
)
RETURNS TABLE (
    flight_id       INT,
    flight_number   VARCHAR,
    origin          VARCHAR,
    destination     VARCHAR,
    airline_name    VARCHAR,
    popularity      BIGINT
) AS $$
DECLARE
    v_count INT;
BEGIN
    -- return top-N recommendations
    RETURN QUERY
    WITH user_routes AS (
        SELECT DISTINCT f.origin_city_id, f.destination_city_id
        FROM booking b
        JOIN flight f ON b.flight_id = f.flight_id
        WHERE b.user_id = p_user_id
          AND b.booking_status <> 'Cancelled'
    ),
    route_scores AS (
        SELECT
            f.flight_id,
            f.flight_number,
            oc.city_name  AS origin,
            dc.city_name  AS destination,
            a.airline_name,
            COUNT(*)      AS popularity
        FROM booking b
        JOIN flight  f  ON b.flight_id          = f.flight_id
        JOIN city    oc ON f.origin_city_id      = oc.city_id
        JOIN city    dc ON f.destination_city_id = dc.city_id
        JOIN airline a  ON f.airline_id          = a.airline_id
        WHERE b.booking_status <> 'Cancelled'
          AND NOT EXISTS (
              SELECT 1 FROM user_routes ur
              WHERE ur.origin_city_id      = f.origin_city_id
                AND ur.destination_city_id = f.destination_city_id
          )
        GROUP BY f.flight_id, f.flight_number,
                 oc.city_name, dc.city_name, a.airline_name
        ORDER BY popularity DESC
        LIMIT p_limit
    )
    SELECT * FROM route_scores;

    -- count results and log the call
    GET DIAGNOSTICS v_count = ROW_COUNT;
    INSERT INTO recommendation_log(user_id, generated_at, num_results)
    VALUES (p_user_id, NOW(), v_count);
END;
$$ LANGUAGE plpgsql;


-- ============================================================
-- SECTION 6: TRIGGER
-- After every new booking is inserted, automatically update
-- seats_available in flight_price to reflect the new booking.
-- ============================================================

CREATE OR REPLACE FUNCTION fn_update_seats()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE flight_price
    SET seats_available = GREATEST(seats_available - 1, 0)
    WHERE price_id = NEW.price_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_update_seats ON booking;

CREATE TRIGGER trg_update_seats
AFTER INSERT ON booking
FOR EACH ROW
EXECUTE FUNCTION fn_update_seats();


-- ============================================================
-- SECTION 7: TEST THE STORED PROCEDURE AND TRIGGER
-- ============================================================

-- Test stored procedure: get top 5 recommendations for user 1
SELECT * FROM get_user_recommendations(1, 5);

-- Check the log table was populated
SELECT * FROM recommendation_log;

-- Test the trigger: insert a test booking and check seats updated
INSERT INTO booking(user_id, flight_id, price_id, booking_status, total_paid)
VALUES (1, 1, 1, 'Confirmed', 500.00);

-- Verify seats_available decreased for price_id = 1
SELECT price_id, seats_available FROM flight_price WHERE price_id = 1;

-- ============================================================
-- End of performance.sql
-- ============================================================
