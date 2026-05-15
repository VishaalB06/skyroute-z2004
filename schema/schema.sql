-- ============================================================
-- Z2004 Database Management Systems
-- Semester Project - Track B: AI Recommendation Engine
-- Project: SkyRoute — Aviation Flight Recommendation System
-- Name: AlaguVishaalBalaji | Roll No: ZDA24B036
-- Date: April 2026
-- DBMS: PostgreSQL 14+
-- Run: psql -d skyroute -f schema/schema.sql
-- ============================================================

-- drop tables in FK-safe order so the script is idempotent
DROP TABLE IF EXISTS booking;
DROP TABLE IF EXISTS flight_price;
DROP TABLE IF EXISTS flight;
DROP TABLE IF EXISTS airline;
DROP TABLE IF EXISTS city;
DROP TABLE IF EXISTS users;


-- ============================================================
-- 1. city
-- Stores every city that can appear as an origin or destination.
-- Kept separate so flight doesn't duplicate city_name/country
-- across thousands of rows (avoids transitive dependency).
-- ============================================================
CREATE TABLE city (
    city_id    SERIAL       PRIMARY KEY,
    city_name  VARCHAR(100) NOT NULL,
    country    VARCHAR(100) NOT NULL,
    iata_code  CHAR(3)      NOT NULL UNIQUE  -- e.g. DAR, NBO, JNB
);

COMMENT ON TABLE  city           IS 'Master list of cities used as flight origins and destinations.';
COMMENT ON COLUMN city.iata_code IS '3-letter IATA airport code. UNIQUE enforces one row per airport.';
COMMENT ON COLUMN city.city_name IS 'Full city name — kept here so flight never stores it directly.';


-- ============================================================
-- 2. airline
-- One row per airline. Kept separate from flight so airline_name
-- and country are never repeated across route rows.
-- ============================================================
CREATE TABLE airline (
    airline_id    SERIAL       PRIMARY KEY,
    airline_name  VARCHAR(150) NOT NULL,
    iata_code     CHAR(2)      NOT NULL UNIQUE,  -- e.g. QR, EK, ET
    country       VARCHAR(100) NOT NULL,
    hub_city      VARCHAR(100)                   -- stored as text, not FK, to avoid circular dependency
);

COMMENT ON TABLE  airline           IS 'Airline identity — name, IATA code, home country.';
COMMENT ON COLUMN airline.iata_code IS '2-letter IATA airline code. UNIQUE — no two airlines share a code.';
COMMENT ON COLUMN airline.hub_city  IS 'Main hub stored as plain text to avoid a circular FK with city at insert time.';


-- ============================================================
-- 3. users
-- People registered on the platform. email is the natural
-- alternate key — kept UNIQUE to prevent duplicate accounts.
-- ============================================================
CREATE TABLE users (
    user_id     SERIAL       PRIMARY KEY,
    full_name   VARCHAR(150) NOT NULL,
    email       VARCHAR(200) NOT NULL UNIQUE,
    phone       VARCHAR(30),
    nationality VARCHAR(100),
    dob         DATE,
    created_at  TIMESTAMP    DEFAULT NOW()
);

COMMENT ON TABLE  users            IS 'Registered users of the SkyRoute platform.';
COMMENT ON COLUMN users.email      IS 'Alternate key — enforces one account per email address.';
COMMENT ON COLUMN users.created_at IS 'Auto-set on insert; used to track when a user joined.';


-- ============================================================
-- 4. flight
-- One row per scheduled route. References city TWICE —
-- once for origin, once for destination. The CHECK constraint
-- ensures a flight cannot have the same city on both ends.
-- airline_id + flight_number together form a natural unique key.
-- ============================================================
CREATE TABLE flight (
    flight_id            SERIAL      PRIMARY KEY,
    airline_id           INT         NOT NULL,
    origin_city_id       INT         NOT NULL,
    destination_city_id  INT         NOT NULL,
    flight_number        VARCHAR(10) NOT NULL,
    departure_time       TIME        NOT NULL,
    arrival_time         TIME        NOT NULL,
    duration_minutes     INT         NOT NULL CHECK (duration_minutes > 0),
    aircraft_type        VARCHAR(60),

    FOREIGN KEY (airline_id)          REFERENCES airline(airline_id),
    FOREIGN KEY (origin_city_id)      REFERENCES city(city_id),
    FOREIGN KEY (destination_city_id) REFERENCES city(city_id),

    -- a flight cannot depart and arrive at the same city
    CHECK (origin_city_id <> destination_city_id),

    -- flight number is only unique within an airline (e.g. QR542 belongs to Qatar Airways only)
    UNIQUE (airline_id, flight_number)
);

COMMENT ON TABLE  flight                      IS 'Scheduled flight routes. Each row is one origin-to-destination service.';
COMMENT ON COLUMN flight.origin_city_id       IS 'FK to city (origin). city is referenced twice in this table — once per direction.';
COMMENT ON COLUMN flight.destination_city_id  IS 'FK to city (destination). Separate FK from origin_city_id.';
COMMENT ON COLUMN flight.duration_minutes     IS 'CHECK > 0 ensures no zero or negative flight durations.';
COMMENT ON COLUMN flight.flight_number        IS 'Unique per airline only — UNIQUE(airline_id, flight_number) enforces this.';


-- ============================================================
-- 5. flight_price
-- Prices are separated from flight because the same route can
-- have different prices by cabin class (Economy / Business /
-- First) and by date (yield management). Putting price on
-- flight would create a partial dependency on (flight, cabin,
-- date) which breaks 3NF.
-- ============================================================
CREATE TABLE flight_price (
    price_id         SERIAL         PRIMARY KEY,
    flight_id        INT            NOT NULL,
    cabin_class      VARCHAR(20)    NOT NULL CHECK (cabin_class IN ('Economy', 'Business', 'First')),
    base_price       DECIMAL(10,2)  NOT NULL CHECK (base_price >= 0),
    seats_available  INT            DEFAULT 0,
    price_date       DATE           NOT NULL DEFAULT CURRENT_DATE,

    FOREIGN KEY (flight_id) REFERENCES flight(flight_id) ON DELETE CASCADE
);

COMMENT ON TABLE  flight_price                IS 'Per-flight pricing by cabin class and date. Separated from flight to satisfy 3NF.';
COMMENT ON COLUMN flight_price.cabin_class    IS 'CHECK limits values to Economy, Business, or First only.';
COMMENT ON COLUMN flight_price.base_price     IS 'CHECK >= 0 prevents negative prices being inserted.';
COMMENT ON COLUMN flight_price.seats_available IS 'Tracks remaining seat capacity — updated as bookings come in.';
COMMENT ON COLUMN flight_price.price_date     IS 'Allows different prices on different dates (yield management / dynamic pricing).';


-- ============================================================
-- 6. booking  (main transactional table — 2000+ rows in M2)
-- Central table linking users to flights at a specific price.
-- References flight_price (not flight directly) so the exact
-- cabin class and fare at time of booking is permanently recorded.
-- ============================================================
CREATE TABLE booking (
    booking_id      SERIAL         PRIMARY KEY,
    user_id         INT            NOT NULL,
    flight_id       INT            NOT NULL,
    price_id        INT            NOT NULL,
    booking_date    TIMESTAMP      DEFAULT NOW(),
    booking_status  VARCHAR(20)    DEFAULT 'Confirmed'
                                   CHECK (booking_status IN ('Confirmed', 'Cancelled', 'Pending', 'Completed')),
    seat_number     VARCHAR(6),
    total_paid      DECIMAL(10,2)  NOT NULL CHECK (total_paid >= 0),

    FOREIGN KEY (user_id)   REFERENCES users(user_id),
    FOREIGN KEY (flight_id) REFERENCES flight(flight_id),
    FOREIGN KEY (price_id)  REFERENCES flight_price(price_id)
);

COMMENT ON TABLE  booking               IS 'Core transactional table. Will hold 2000+ rows loaded from the Kaggle dataset in M2.';
COMMENT ON COLUMN booking.price_id      IS 'FK to flight_price — locks in the exact cabin class and fare at the time of booking.';
COMMENT ON COLUMN booking.booking_status IS 'CHECK limits to 4 valid states. Cancelled rows are kept for analytics, not deleted.';
COMMENT ON COLUMN booking.total_paid    IS 'Actual amount charged — may differ from base_price after discounts or fees.';
COMMENT ON COLUMN booking.seat_number   IS 'Optional — not all bookings assign a seat at booking time.';


-- ============================================================
-- Indexes (prep for M3 benchmarking)
-- Before/after EXPLAIN ANALYZE evidence will be in M3 report.
-- ============================================================

-- most recommendation queries filter bookings by user
CREATE INDEX idx_booking_user_id ON booking(user_id);

-- route lookups used in the recommendation engine
CREATE INDEX idx_flight_route    ON flight(origin_city_id, destination_city_id);

-- speeds up JOIN from booking to flight_price
CREATE INDEX idx_price_flight    ON flight_price(flight_id);

COMMENT ON INDEX idx_booking_user_id IS 'Speeds up per-user booking history queries used in collaborative filtering.';
COMMENT ON INDEX idx_flight_route    IS 'Composite index for origin-to-destination route lookups.';
COMMENT ON INDEX idx_price_flight    IS 'Supports JOIN from booking to flight_price on flight_id.';

-- ============================================================
-- End of schema.sql
-- ============================================================
