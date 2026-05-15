-- ============================================================
-- Z2004 Database Management Systems
-- Semester Project - Track B: AI Recommendation Engine
-- Project: SkyRoute — Aviation Flight Recommendation System
-- Name: AlaguVishaalBalaji | Roll No: ZDA24B036
-- File: queries/queries.sql
-- Description: 10 labelled queries covering all required types
-- ============================================================


-- ============================================================
-- AGGREGATION QUERIES
-- ============================================================

-- Q1_AGG: Total bookings and revenue per airline
-- Shows which airlines generate the most business on the platform
SELECT
    a.airline_name,
    COUNT(b.booking_id)          AS total_bookings,
    SUM(b.total_paid)            AS total_revenue,
    ROUND(AVG(b.total_paid), 2)  AS avg_fare
FROM booking b
JOIN flight  f ON b.flight_id  = f.flight_id
JOIN airline a ON f.airline_id = a.airline_id
WHERE b.booking_status <> 'Cancelled'
GROUP BY a.airline_id, a.airline_name
ORDER BY total_revenue DESC;


-- Q2_AGG: Booking counts by cabin class and status
-- Useful for understanding demand distribution across cabin types
SELECT
    fp.cabin_class,
    b.booking_status,
    COUNT(*)                     AS num_bookings,
    ROUND(AVG(b.total_paid), 2)  AS avg_paid
FROM booking b
JOIN flight_price fp ON b.price_id = fp.price_id
GROUP BY fp.cabin_class, b.booking_status
ORDER BY fp.cabin_class, num_bookings DESC;


-- ============================================================
-- JOIN QUERIES
-- ============================================================

-- Q3_JOIN: Full booking details — user, flight, origin, destination, airline
-- The main joined view that combines all 6 tables
SELECT
    b.booking_id,
    u.full_name                  AS passenger,
    a.airline_name,
    f.flight_number,
    oc.city_name                 AS origin,
    dc.city_name                 AS destination,
    fp.cabin_class,
    b.total_paid,
    b.booking_status,
    b.booking_date
FROM booking b
JOIN users        u  ON b.user_id   = u.user_id
JOIN flight       f  ON b.flight_id = f.flight_id
JOIN airline      a  ON f.airline_id = a.airline_id
JOIN city         oc ON f.origin_city_id      = oc.city_id
JOIN city         dc ON f.destination_city_id = dc.city_id
JOIN flight_price fp ON b.price_id  = fp.price_id
ORDER BY b.booking_date DESC
LIMIT 50;


-- Q4_JOIN: Most popular routes — cities with the most confirmed bookings
SELECT
    oc.city_name   AS origin,
    dc.city_name   AS destination,
    COUNT(*)       AS confirmed_bookings,
    ROUND(AVG(b.total_paid), 2) AS avg_fare
FROM booking b
JOIN flight f  ON b.flight_id         = f.flight_id
JOIN city   oc ON f.origin_city_id    = oc.city_id
JOIN city   dc ON f.destination_city_id = dc.city_id
WHERE b.booking_status = 'Confirmed'
GROUP BY oc.city_id, oc.city_name, dc.city_id, dc.city_name
ORDER BY confirmed_bookings DESC
LIMIT 15;


-- ============================================================
-- SUBQUERY QUERIES
-- ============================================================

-- Q5_SUB: Users who have spent more than the average total paid
-- Finds high-value customers above the platform average
SELECT
    u.user_id,
    u.full_name,
    u.nationality,
    SUM(b.total_paid) AS total_spent
FROM users u
JOIN booking b ON u.user_id = b.user_id
WHERE b.booking_status <> 'Cancelled'
GROUP BY u.user_id, u.full_name, u.nationality
HAVING SUM(b.total_paid) > (
    SELECT AVG(sub.total_per_user)
    FROM (
        SELECT SUM(total_paid) AS total_per_user
        FROM booking
        WHERE booking_status <> 'Cancelled'
        GROUP BY user_id
    ) sub
)
ORDER BY total_spent DESC;


-- Q6_SUB: Flights that have never had a booking
-- Useful for identifying underperforming routes
SELECT
    f.flight_id,
    f.flight_number,
    a.airline_name,
    oc.city_name AS origin,
    dc.city_name AS destination
FROM flight f
JOIN airline a  ON f.airline_id          = a.airline_id
JOIN city    oc ON f.origin_city_id      = oc.city_id
JOIN city    dc ON f.destination_city_id = dc.city_id
WHERE NOT EXISTS (
    SELECT 1
    FROM booking b
    WHERE b.flight_id = f.flight_id
)
ORDER BY a.airline_name;


-- ============================================================
-- CTE QUERIES
-- ============================================================

-- Q7_CTE: Top 5 most booked routes per airline using CTEs
WITH route_counts AS (
    SELECT
        f.airline_id,
        f.origin_city_id,
        f.destination_city_id,
        COUNT(*) AS booking_count
    FROM booking b
    JOIN flight f ON b.flight_id = f.flight_id
    WHERE b.booking_status <> 'Cancelled'
    GROUP BY f.airline_id, f.origin_city_id, f.destination_city_id
),
ranked_routes AS (
    SELECT
        rc.*,
        ROW_NUMBER() OVER (
            PARTITION BY rc.airline_id
            ORDER BY rc.booking_count DESC
        ) AS route_rank
    FROM route_counts rc
)
SELECT
    a.airline_name,
    oc.city_name  AS origin,
    dc.city_name  AS destination,
    rr.booking_count,
    rr.route_rank
FROM ranked_routes rr
JOIN airline a  ON rr.airline_id          = a.airline_id
JOIN city    oc ON rr.origin_city_id      = oc.city_id
JOIN city    dc ON rr.destination_city_id = dc.city_id
WHERE rr.route_rank <= 5
ORDER BY a.airline_name, rr.route_rank;


-- Q8_CTE: Monthly booking trends with running total revenue
WITH monthly_stats AS (
    SELECT
        DATE_TRUNC('month', booking_date) AS month,
        COUNT(*)                          AS bookings,
        SUM(total_paid)                   AS monthly_revenue
    FROM booking
    WHERE booking_status <> 'Cancelled'
    GROUP BY DATE_TRUNC('month', booking_date)
)
SELECT
    TO_CHAR(month, 'YYYY-MM')  AS month,
    bookings,
    ROUND(monthly_revenue, 2)  AS monthly_revenue,
    ROUND(SUM(monthly_revenue) OVER (
        ORDER BY month
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ), 2)                      AS running_total_revenue
FROM monthly_stats
ORDER BY month;


-- ============================================================
-- WINDOW FUNCTION QUERIES (collaborative filtering core)
-- ============================================================

-- Q9_WIN: Rank users by number of bookings per nationality
-- RANK() + PARTITION BY — shows top travellers within each nationality
SELECT
    u.nationality,
    u.full_name,
    COUNT(b.booking_id)  AS total_bookings,
    SUM(b.total_paid)    AS total_spent,
    RANK() OVER (
        PARTITION BY u.nationality
        ORDER BY COUNT(b.booking_id) DESC
    )                    AS rank_in_nationality
FROM users u
JOIN booking b ON u.user_id = b.user_id
WHERE b.booking_status <> 'Cancelled'
GROUP BY u.user_id, u.full_name, u.nationality
ORDER BY u.nationality, rank_in_nationality;


-- Q10_WIN: Top-N flight recommendations per user (collaborative filtering)
-- Core recommendation query using ROW_NUMBER + SUM OVER PARTITION BY
-- Logic: score each unseen route by how many similar users booked it
WITH user_routes AS (
    -- routes each user has already booked
    SELECT DISTINCT
        b.user_id,
        f.origin_city_id,
        f.destination_city_id
    FROM booking b
    JOIN flight f ON b.flight_id = f.flight_id
    WHERE b.booking_status <> 'Cancelled'
),
route_popularity AS (
    -- total bookings per route across all users
    SELECT
        f.origin_city_id,
        f.destination_city_id,
        COUNT(*) AS popularity_score
    FROM booking b
    JOIN flight f ON b.flight_id = f.flight_id
    WHERE b.booking_status <> 'Cancelled'
    GROUP BY f.origin_city_id, f.destination_city_id
),
recommendations AS (
    -- for each user, find popular routes they haven't flown yet
    SELECT
        ur_all.user_id,
        rp.origin_city_id,
        rp.destination_city_id,
        rp.popularity_score,
        ROW_NUMBER() OVER (
            PARTITION BY ur_all.user_id
            ORDER BY rp.popularity_score DESC
        ) AS recommendation_rank
    FROM (SELECT DISTINCT user_id FROM booking) ur_all
    JOIN route_popularity rp ON TRUE
    WHERE NOT EXISTS (
        SELECT 1 FROM user_routes ur
        WHERE ur.user_id          = ur_all.user_id
          AND ur.origin_city_id   = rp.origin_city_id
          AND ur.destination_city_id = rp.destination_city_id
    )
)
SELECT
    r.user_id,
    u.full_name,
    oc.city_name  AS recommended_origin,
    dc.city_name  AS recommended_destination,
    r.popularity_score,
    r.recommendation_rank
FROM recommendations r
JOIN users u  ON r.user_id              = u.user_id
JOIN city  oc ON r.origin_city_id      = oc.city_id
JOIN city  dc ON r.destination_city_id = dc.city_id
WHERE r.recommendation_rank <= 3   -- top 3 recommendations per user
ORDER BY r.user_id, r.recommendation_rank;

-- ============================================================
-- End of queries.sql
-- ============================================================
