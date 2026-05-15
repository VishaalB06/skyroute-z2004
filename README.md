# SkyRoute — Aviation Flight Recommendation System

**Z2004 Database Management Systems | Track B: AI Recommendation Engine**
**Name:** AlaguVishaalBalaji | **Roll No:** ZDA24B036 | **Even Semester 2026**

---

## Project Overview

SkyRoute is an AI-powered flight recommendation system backed by a normalised PostgreSQL relational database. The system uses collaborative filtering over booking history to recommend flights to users based on what similar users have booked.

**Domain:** Aviation — flights, bookings, pricing, airlines, cities
**Track:** B — AI Recommendation Engine
**Database:** PostgreSQL 14+

---

## Repository Structure

```
skyroute/
├── schema/
│   └── schema.sql          # DDL — all 6 tables, constraints, indexes
├── data/                   # Dataset CSV/JSON + import script (added in M2)
├── queries/                # SQL query suite (added in M2)
├── app/                    # Python Flask API (added in M2/Final)
├── report/                 # Milestone design documents (PDF)
├── demo/                   # Demo video (added at Final)
└── README.md
```

---

## Database Schema

Six tables in 3NF:

| Table | Description |
|---|---|
| `users` | Registered travellers on the platform |
| `city` | All origin and destination cities (IATA codes) |
| `airline` | Airline identity and hub information |
| `flight` | Scheduled routes — references `city` twice (origin + destination) |
| `flight_price` | Cabin-class pricing per flight per date |
| `booking` | Core transactional table — 2000+ rows from dataset |

**Key design decisions:**
- `flight` references `city` twice via `origin_city_id` and `destination_city_id` — avoids duplicating a separate origin/destination table
- `flight_price` is separated from `flight` because price depends on `(flight, cabin_class, date)` not `flight_id` alone — keeping it on `flight` would break 3NF
- `booking` references `flight_price` (not just `flight`) so the exact fare and cabin class at booking time is permanently recorded

---

## Setup Instructions

### Requirements
- PostgreSQL 14+
- psql command-line tool

### Run the schema

```bash
# 1. Create the database
createdb skyroute

# 2. Run the DDL script
psql -d skyroute -f schema/schema.sql

# 3. Verify tables were created
psql -d skyroute -c "\dt"
```

The script is idempotent — it drops and recreates all tables, so it can be run multiple times safely during development.

---

## Milestones

| Milestone | Due | Status |
|---|---|---|
| M0 — Registration | 27 March 2026 | Done |
| M1 — Schema & DDL | 10 April 2026 | Done |
| M2 — Dataset & Queries | 15 May 2026 | Upcoming |
| M3 — Performance Evidence | 5 June 2026 | Upcoming |
| Final Submission | 22 June 2026 | Upcoming |

---

## AI Usage Disclosure

AI tools (Claude) were used for:
- Drafting the initial SQL schema structure
- Suggesting COMMENT ON annotations
- Helping format the design document

All SQL was reviewed, understood, and adapted. The design decisions (3NF justification, FK structure, index choices) are my own.

---

## Contact

**AlaguVishaalBalaji** | ZDA24B036
IIT Madras Zanzibar | Z2004 DBMS | Even Semester 2026
