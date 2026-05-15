"""
SkyRoute — Synthetic Data Generator
Z2004 DBMS | Milestone 2 | AlaguVishaalBalaji | ZDA24B036

Generates realistic aviation data across all 6 tables.
Outputs: cities.csv, airlines.csv, users.csv, flights.csv,
         flight_prices.csv, bookings.csv
Run: python generate_data.py
"""

import pandas as pd
import numpy as np
import random
from datetime import datetime, timedelta, date
import os

random.seed(42)
np.random.seed(42)

OUT = "data"
os.makedirs(OUT, exist_ok=True)

# ── 1. CITIES ────────────────────────────────────────────────
cities_raw = [
    ("Dar es Salaam",  "Tanzania",      "DAR"),
    ("Nairobi",        "Kenya",         "NBO"),
    ("Zanzibar",       "Tanzania",      "ZNZ"),
    ("Johannesburg",   "South Africa",  "JNB"),
    ("Cape Town",      "South Africa",  "CPT"),
    ("Lagos",          "Nigeria",       "LOS"),
    ("Addis Ababa",    "Ethiopia",      "ADD"),
    ("Cairo",          "Egypt",         "CAI"),
    ("Dubai",          "UAE",           "DXB"),
    ("Doha",           "Qatar",         "DOH"),
    ("London",         "UK",            "LHR"),
    ("Paris",          "France",        "CDG"),
    ("Amsterdam",      "Netherlands",   "AMS"),
    ("Frankfurt",      "Germany",       "FRA"),
    ("Istanbul",       "Turkey",        "IST"),
    ("Mumbai",         "India",         "BOM"),
    ("Delhi",          "India",         "DEL"),
    ("Singapore",      "Singapore",     "SIN"),
    ("Bangkok",        "Thailand",      "BKK"),
    ("New York",       "USA",           "JFK"),
    ("Lusaka",         "Zambia",        "LUN"),
    ("Kampala",        "Uganda",        "EBB"),
    ("Accra",          "Ghana",         "ACC"),
    ("Kigali",         "Rwanda",        "KGL"),
    ("Casablanca",     "Morocco",       "CMN"),
    ("Abu Dhabi",      "UAE",           "AUH"),   # NEW
    ("Chennai",        "India",         "MAA"),   # NEW
]

cities_df = pd.DataFrame(cities_raw, columns=["city_name", "country", "iata_code"])
cities_df.index = pd.RangeIndex(start=1, stop=len(cities_df)+1)
cities_df.index.name = "city_id"
cities_df.to_csv(f"{OUT}/cities.csv")
print(f"cities: {len(cities_df)} rows")

# city_id reference (1-indexed, matches order above)
# Abu Dhabi = 26, Chennai = 27

# ── 2. AIRLINES ──────────────────────────────────────────────
airlines_raw = [
    ("Qatar Airways",        "QR", "Qatar",        "Doha"),
    ("Emirates",             "EK", "UAE",           "Dubai"),
    ("Ethiopian Airlines",   "ET", "Ethiopia",      "Addis Ababa"),
    ("Kenya Airways",        "KQ", "Kenya",         "Nairobi"),
    ("Turkish Airlines",     "TK", "Turkey",        "Istanbul"),
    ("Lufthansa",            "LH", "Germany",       "Frankfurt"),
    ("British Airways",      "BA", "UK",            "London"),
    ("Air France",           "AF", "France",        "Paris"),
    ("KLM",                  "KL", "Netherlands",   "Amsterdam"),
    ("South African Airways","SA", "South Africa",  "Johannesburg"),
    ("EgyptAir",             "MS", "Egypt",         "Cairo"),
    ("Air Tanzania",         "TC", "Tanzania",      "Dar es Salaam"),
    ("RwandAir",             "WB", "Rwanda",        "Kigali"),
    ("Precision Air",        "PW", "Tanzania",      "Dar es Salaam"),
    ("Flydubai",             "FZ", "UAE",           "Dubai"),
    ("Etihad Airways",       "EY", "UAE",           "Abu Dhabi"),  # NEW
]

airlines_df = pd.DataFrame(airlines_raw, columns=["airline_name", "iata_code", "country", "hub_city"])
airlines_df.index = pd.RangeIndex(start=1, stop=len(airlines_df)+1)
airlines_df.index.name = "airline_id"
airlines_df.to_csv(f"{OUT}/airlines.csv")
print(f"airlines: {len(airlines_df)} rows")

# Etihad airline_id = 16

# ── 3. USERS ─────────────────────────────────────────────────
first_names = ["Amina","Hassan","Fatuma","John","Sarah","Mohammed","Grace","David",
               "Aisha","James","Mary","Ahmed","Lucia","Peter","Zara","Samuel","Nadia",
               "Omar","Priya","Kwame","Lena","Ibrahim","Sofia","Raj","Mei","Carlos",
               "Fatima","Daniel","Yuki","Chidi","Nia","Sven","Layla","Kofi","Elena"]
last_names  = ["Hassan","Mwanga","Ali","Okonkwo","Sharma","Mueller","Patel","Nguyen",
               "Garcia","Kim","Andersen","Rossi","Santos","Osei","Tanaka","Weber",
               "Diallo","Fernandez","Johansson","Mensah","Ibrahim","Nakamura","Dlamini",
               "Abebe","Kamau","Nkosi","Traore","Boateng","Rashid","Lindqvist"]
nationalities = ["Tanzanian","Kenyan","Nigerian","Ethiopian","South African","Egyptian",
                 "Ghanaian","Rwandan","Ugandan","Zambian","British","German","French",
                 "Dutch","Indian","Qatari","Emirati","Turkish","Singaporean","American"]

users = []
emails_seen = set()
for i in range(1, 301):
    fn = random.choice(first_names)
    ln = random.choice(last_names)
    base_email = f"{fn.lower()}.{ln.lower()}{random.randint(1,999)}@gmail.com"
    while base_email in emails_seen:
        base_email = f"{fn.lower()}.{ln.lower()}{random.randint(1,9999)}@gmail.com"
    emails_seen.add(base_email)
    dob = date(random.randint(1975, 2003), random.randint(1,12), random.randint(1,28))
    created = datetime(2023, random.randint(1,12), random.randint(1,28))
    users.append({
        "user_id": i,
        "full_name": f"{fn} {ln}",
        "email": base_email,
        "phone": f"+{random.randint(1,999)}{random.randint(100000000,999999999)}",
        "nationality": random.choice(nationalities),
        "dob": dob,
        "created_at": created,
    })

users_df = pd.DataFrame(users).set_index("user_id")
users_df.to_csv(f"{OUT}/users.csv")
print(f"users: {len(users_df)} rows")

# ── 4. FLIGHTS ───────────────────────────────────────────────
# city_id reference:
# DAR=1, NBO=2, ZNZ=3, JNB=4, CPT=5, LOS=6, ADD=7, CAI=8,
# DXB=9, DOH=10, LHR=11, CDG=12, AMS=13, FRA=14, IST=15,
# BOM=16, DEL=17, SIN=18, BKK=19, JFK=20, LUN=21, EBB=22,
# ACC=23, KGL=24, CMN=25, AUH=26, MAA=27
#
# airline_id reference:
# QR=1, EK=2, ET=3, KQ=4, TK=5, LH=6, BA=7, AF=8, KL=9,
# SA=10, MS=11, TC=12, WB=13, PW=14, FZ=15, EY=16

route_templates = [
    # existing routes
    (1,2,4),(1,4,10),(1,7,3),(1,9,2),(1,10,1),(1,11,12),(1,12,8),
    (1,14,6),(1,15,5),(1,3,14),(2,4,10),(2,7,3),(2,9,2),(2,10,1),
    (2,11,7),(2,12,8),(2,13,9),(2,15,5),(4,9,2),(4,10,1),(4,11,7),
    (4,12,8),(4,14,6),(6,9,2),(6,10,1),(6,11,7),(6,14,6),(6,15,5),
    (7,9,2),(7,10,1),(7,11,7),(7,12,8),(7,15,5),(8,9,2),(8,10,1),
    (8,11,11),(1,6,12),(1,8,11),(2,6,4),(2,8,11),(3,2,14),(3,4,14),
    (21,2,10),(22,2,4),(23,6,10),(24,2,13),(24,7,13),(25,8,11),
    (1,16,2),(1,18,1),(2,16,2),(4,18,2),(9,11,2),(9,12,2),(10,11,1),
    (10,12,1),(10,14,1),(10,15,5),(15,11,5),(15,12,8),(15,14,6),
    # NEW Etihad routes (airline_id=16, hub=Abu Dhabi city_id=26)
    (26,1,16),   # AUH → DAR
    (26,2,16),   # AUH → NBO
    (26,4,16),   # AUH → JNB
    (26,6,16),   # AUH → LOS
    (26,7,16),   # AUH → ADD
    (26,11,16),  # AUH → LHR
    (26,12,16),  # AUH → CDG
    (26,14,16),  # AUH → FRA
    (26,15,16),  # AUH → IST
    (26,16,16),  # AUH → BOM
    (26,17,16),  # AUH → DEL
    (26,27,16),  # AUH → MAA (Chennai)
    (26,18,16),  # AUH → SIN
    (26,20,16),  # AUH → JFK
    (1,26,16),   # DAR → AUH
    (2,26,16),   # NBO → AUH
    (4,26,16),   # JNB → AUH
    (10,26,1),   # DOH → AUH  (Qatar Airways)
    (9,26,2),    # DXB → AUH  (Emirates)
    # NEW Chennai routes
    (27,9,2),    # MAA → DXB  (Emirates)
    (27,26,16),  # MAA → AUH  (Etihad)
    (27,10,1),   # MAA → DOH  (Qatar Airways)
    (27,11,7),   # MAA → LHR  (British Airways)
    (27,15,5),   # MAA → IST  (Turkish Airlines)
    (27,14,6),   # MAA → FRA  (Lufthansa)
    (16,27,2),   # BOM → MAA  (Emirates — domestic India connection)
    (17,27,1),   # DEL → MAA  (Qatar Airways)
]

flights = []
flight_id = 1
used_numbers = {}

aircraft_types = ["Boeing 737","Boeing 777","Boeing 787","Airbus A320",
                  "Airbus A330","Airbus A350","Airbus A380","Bombardier Q400",
                  "Airbus A321neo","Boeing 777X"]

for (orig, dest, airline) in route_templates:
    n_flights = random.randint(2, 5)
    for _ in range(n_flights):
        al_code = airlines_df.loc[airline, "iata_code"]
        key = (airline,)
        used_numbers.setdefault(key, set())
        while True:
            num = f"{al_code}{random.randint(100,999)}"
            if num not in used_numbers[key]:
                used_numbers[key].add(num)
                break
        dep_h = random.randint(0, 22)
        dep_m = random.choice([0, 15, 30, 45])
        dep_time = f"{dep_h:02d}:{dep_m:02d}"
        dur = random.randint(60, 720)
        arr_total = dep_h * 60 + dep_m + dur
        arr_h = (arr_total // 60) % 24
        arr_m = arr_total % 60
        arr_time = f"{arr_h:02d}:{arr_m:02d}"
        flights.append({
            "flight_id": flight_id,
            "airline_id": airline,
            "origin_city_id": orig,
            "destination_city_id": dest,
            "flight_number": num,
            "departure_time": dep_time,
            "arrival_time": arr_time,
            "duration_minutes": dur,
            "aircraft_type": random.choice(aircraft_types),
        })
        flight_id += 1

flights_df = pd.DataFrame(flights).set_index("flight_id")
flights_df.to_csv(f"{OUT}/flights.csv")
print(f"flights: {len(flights_df)} rows")

# ── 5. FLIGHT PRICES ─────────────────────────────────────────
cabin_classes = ["Economy", "Business", "First"]
base_prices   = {"Economy": (120, 800), "Business": (600, 3000), "First": (2000, 8000)}

prices = []
price_id = 1
start_date = date(2024, 1, 1)
date_range = [start_date + timedelta(days=i*14) for i in range(13)]

for fid in flights_df.index:
    for cabin in cabin_classes:
        lo, hi = base_prices[cabin]
        for pd_date in random.sample(date_range, k=random.randint(3, 8)):
            bp = round(random.uniform(lo, hi), 2)
            seats = random.randint(0, 200) if cabin == "Economy" else random.randint(0, 40)
            prices.append({
                "price_id": price_id,
                "flight_id": fid,
                "cabin_class": cabin,
                "base_price": bp,
                "seats_available": seats,
                "price_date": pd_date,
            })
            price_id += 1

prices_df = pd.DataFrame(prices).set_index("price_id")
prices_df.to_csv(f"{OUT}/flight_prices.csv")
print(f"flight_prices: {len(prices_df)} rows")

# ── 6. BOOKINGS (2000+ rows) ─────────────────────────────────
statuses        = ["Confirmed", "Cancelled", "Completed", "Pending"]
status_weights  = [0.55, 0.15, 0.25, 0.05]

user_ids  = list(users_df.index)
price_ids = list(prices_df.index)
price_to_flight = prices_df["flight_id"].to_dict()

bookings = []
booking_id = 1

for uid in user_ids:
    n_bookings = random.randint(3, 15)
    for _ in range(n_bookings):
        pid = random.choice(price_ids)
        fid = price_to_flight[pid]
        bdate = datetime(2024, random.randint(1,12), random.randint(1,28),
                         random.randint(0,23), random.randint(0,59))
        base  = float(prices_df.loc[pid, "base_price"])
        total = round(base * random.uniform(1.0, 1.25), 2)
        status = random.choices(statuses, weights=status_weights)[0]
        seat_row = random.randint(1, 50)
        seat_col = random.choice(["A","B","C","D","E","F"])
        bookings.append({
            "booking_id": booking_id,
            "user_id": uid,
            "flight_id": fid,
            "price_id": pid,
            "booking_date": bdate,
            "booking_status": status,
            "seat_number": f"{seat_row}{seat_col}",
            "total_paid": total,
        })
        booking_id += 1

bookings_df = pd.DataFrame(bookings).set_index("booking_id")
bookings_df.to_csv(f"{OUT}/bookings.csv")
print(f"bookings: {len(bookings_df)} rows")
print(f"\nTotal rows across all tables: {len(cities_df)+len(airlines_df)+len(users_df)+len(flights_df)+len(prices_df)+len(bookings_df)}")
print("All CSV files saved to data/")
