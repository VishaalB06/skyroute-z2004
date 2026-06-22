"""
SkyRoute — Flight Search & Admin Dashboard
Z2004 DBMS | Final Submission | AlaguVishaalBalaji | ZDA24B036
Run: python app.py
"""
 
from flask import Flask, jsonify, request, render_template_string
import psycopg2, psycopg2.extras, random, string, os
from datetime import datetime
from dotenv import load_dotenv
 
load_dotenv()  # reads variables from .env file in the same folder
 
app = Flask(__name__)
 
DB_CONFIG = {
    "host":     os.getenv("DB_HOST", "localhost"),
    "database": os.getenv("DB_NAME", "skyroute"),
    "user":     os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "postgres123"),
    "port":     int(os.getenv("DB_PORT", 5432)),
}
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "skyroute2026")

def get_conn():
    return psycopg2.connect(**DB_CONFIG)

def fmt_time(t):
    s = str(t); parts = s.split(":")
    return f"{parts[0]}:{parts[1]}" if len(parts) >= 2 else s

def booking_ref():
    return "SR" + "".join(random.choices(string.ascii_uppercase + string.digits, k=6))

# ── CITIES ────────────────────────────────────────────────────
@app.route("/api/cities")
def api_cities():
    conn = get_conn(); cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT city_id, city_name, country, iata_code FROM city ORDER BY city_name")
    rows = [dict(r) for r in cur.fetchall()]
    cur.close(); conn.close()
    return jsonify(rows)

# ── FLIGHT SEARCH ─────────────────────────────────────────────
@app.route("/api/search")
def api_search():
    origin = request.args.get("origin")
    dest   = request.args.get("dest")
    cabin  = request.args.get("cabin", "")
    if not origin or not dest:
        return jsonify({"error": "origin and dest required"}), 400
    try:
        conn = get_conn(); cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        def flight_query(orig, dst, cab):
            cabin_filter = "AND fp.cabin_class = %s" if cab else ""
            params = [orig, dst] + ([cab] if cab else [])
            cur.execute(f"""
                SELECT f.flight_id, f.flight_number,
                    a.airline_name, a.iata_code AS airline_code,
                    oc.city_name AS origin, oc.iata_code AS origin_iata,
                    dc.city_name AS destination, dc.iata_code AS dest_iata,
                    f.departure_time, f.arrival_time, f.duration_minutes, f.aircraft_type,
                    MIN(fp.base_price) AS min_price,
                    bool_or(fp.cabin_class='Economy')  AS has_economy,
                    bool_or(fp.cabin_class='Business') AS has_business,
                    bool_or(fp.cabin_class='First')    AS has_first,
                    MIN(CASE WHEN fp.cabin_class='Economy'  THEN fp.base_price END) AS eco_price,
                    MIN(CASE WHEN fp.cabin_class='Business' THEN fp.base_price END) AS bus_price,
                    MIN(CASE WHEN fp.cabin_class='First'    THEN fp.base_price END) AS fst_price,
                    MIN(CASE WHEN fp.cabin_class='Economy'  THEN fp.price_id END) AS eco_price_id,
                    MIN(CASE WHEN fp.cabin_class='Business' THEN fp.price_id END) AS bus_price_id,
                    MIN(CASE WHEN fp.cabin_class='First'    THEN fp.price_id END) AS fst_price_id,
                    MIN(fp.seats_available) AS seats_available,
                    COUNT(DISTINCT b.booking_id) AS total_bookings
                FROM flight f
                JOIN airline a       ON f.airline_id          = a.airline_id
                JOIN city    oc      ON f.origin_city_id      = oc.city_id
                JOIN city    dc      ON f.destination_city_id = dc.city_id
                JOIN flight_price fp ON fp.flight_id          = f.flight_id
                LEFT JOIN booking b  ON b.flight_id           = f.flight_id
                                    AND b.booking_status <> 'Cancelled'
                WHERE oc.city_id = %s AND dc.city_id = %s {cabin_filter}
                GROUP BY f.flight_id, f.flight_number, a.airline_name, a.iata_code,
                         oc.city_name, oc.iata_code, dc.city_name, dc.iata_code,
                         f.departure_time, f.arrival_time, f.duration_minutes, f.aircraft_type
                ORDER BY total_bookings DESC, min_price ASC
            """, params)
            return cur.fetchall()

        def row_to_dict(r):
            return {
                "flight_id":       r["flight_id"],
                "flight_number":   r["flight_number"],
                "airline":         r["airline_name"],
                "airline_code":    r["airline_code"],
                "origin":          r["origin"],
                "origin_iata":     r["origin_iata"],
                "destination":     r["destination"],
                "dest_iata":       r["dest_iata"],
                "departure_time":  fmt_time(r["departure_time"]),
                "arrival_time":    fmt_time(r["arrival_time"]),
                "duration_minutes":r["duration_minutes"],
                "aircraft_type":   r["aircraft_type"],
                "min_price":       float(r["min_price"]) if r["min_price"] else None,
                "has_economy":     bool(r["has_economy"]),
                "has_business":    bool(r["has_business"]),
                "has_first":       bool(r["has_first"]),
                "eco_price":       float(r["eco_price"]) if r["eco_price"] else None,
                "bus_price":       float(r["bus_price"]) if r["bus_price"] else None,
                "fst_price":       float(r["fst_price"]) if r["fst_price"] else None,
                "eco_price_id":    r["eco_price_id"],
                "bus_price_id":    r["bus_price_id"],
                "fst_price_id":    r["fst_price_id"],
                "seats_available": r["seats_available"],
                "total_bookings":  r["total_bookings"],
                "is_direct":       True,
                "stop_via":        None,
            }

        direct = flight_query(origin, dest, cabin)
        results = [row_to_dict(r) for r in direct]

        if not results:
            cur.execute("""
                SELECT DISTINCT c.city_id, c.city_name, c.iata_code
                FROM city c
                WHERE EXISTS (SELECT 1 FROM flight f1 JOIN flight_price fp1 ON fp1.flight_id=f1.flight_id
                              WHERE f1.origin_city_id=%s AND f1.destination_city_id=c.city_id)
                AND EXISTS   (SELECT 1 FROM flight f2 JOIN flight_price fp2 ON fp2.flight_id=f2.flight_id
                              WHERE f2.origin_city_id=c.city_id AND f2.destination_city_id=%s)
                AND c.city_id <> %s AND c.city_id <> %s
            """, [origin, dest, origin, dest])
            via_cities = cur.fetchall()
            for via in via_cities:
                leg1 = flight_query(origin, via["city_id"], cabin)
                leg2 = flight_query(via["city_id"], dest, cabin)
                if not leg1 or not leg2: continue
                b1 = sorted(leg1, key=lambda r: float(r["min_price"] or 9999))[0]
                b2 = sorted(leg2, key=lambda r: float(r["min_price"] or 9999))[0]
                if cabin == "Economy"  and not (b1["has_economy"]  and b2["has_economy"]):  continue
                if cabin == "Business" and not (b1["has_business"] and b2["has_business"]): continue
                if cabin == "First"    and not (b1["has_first"]    and b2["has_first"]):    continue
                eco = (float(b1["eco_price"] or 0) + float(b2["eco_price"] or 0)) or None
                bus = (float(b1["bus_price"] or 0) + float(b2["bus_price"] or 0)) or None
                fst = (float(b1["fst_price"] or 0) + float(b2["fst_price"] or 0)) or None
                results.append({
                    "flight_id":       f"{b1['flight_id']}-{b2['flight_id']}",
                    "flight_number":   f"{b1['flight_number']} + {b2['flight_number']}",
                    "airline":         f"{b1['airline_name']} / {b2['airline_name']}",
                    "airline_code":    f"{b1['airline_code']}+{b2['airline_code']}",
                    "origin":          b1["origin"], "origin_iata": b1["origin_iata"],
                    "destination":     b2["destination"], "dest_iata": b2["dest_iata"],
                    "departure_time":  fmt_time(b1["departure_time"]),
                    "arrival_time":    fmt_time(b2["arrival_time"]),
                    "duration_minutes":int(b1["duration_minutes"]) + int(b2["duration_minutes"]),
                    "aircraft_type":   f"{b1['aircraft_type'] or ''} / {b2['aircraft_type'] or ''}".strip(" /"),
                    "min_price":       float(b1["min_price"] or 0) + float(b2["min_price"] or 0),
                    "has_economy":     bool(b1["has_economy"])  and bool(b2["has_economy"]),
                    "has_business":    bool(b1["has_business"]) and bool(b2["has_business"]),
                    "has_first":       bool(b1["has_first"])    and bool(b2["has_first"]),
                    "eco_price": eco, "bus_price": bus, "fst_price": fst,
                    "eco_price_id": None, "bus_price_id": None, "fst_price_id": None,
                    "seats_available": min(b1["seats_available"] or 0, b2["seats_available"] or 0),
                    "total_bookings":  int(b1["total_bookings"]) + int(b2["total_bookings"]),
                    "is_direct": False, "stop_via": f"{via['city_name']} ({via['iata_code']})",
                })
            results.sort(key=lambda r: r["min_price"] or 9999)

        cur.close(); conn.close()
        return jsonify({"flights": results, "count": len(results)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ── BOOK A FLIGHT (triggers trg_update_seats) ────────────────
@app.route("/api/book", methods=["POST"])
def api_book():
    """
    Books a flight for a passenger.
    Inserts into booking table → fires trg_update_seats trigger
    which automatically decrements seats_available in flight_price.
    """
    data = request.get_json()
    passenger = data.get("passenger_name", "").strip()
    flight_id  = data.get("flight_id")
    price_id   = data.get("price_id")
    cabin      = data.get("cabin")
    price      = data.get("price")
    if not all([passenger, flight_id, price_id, cabin, price]):
        return jsonify({"error": "Missing required fields"}), 400
    try:
        conn = get_conn(); cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # Check seats before booking
        cur.execute("SELECT seats_available FROM flight_price WHERE price_id = %s", (price_id,))
        seat_row = cur.fetchone()
        if not seat_row:
            return jsonify({"error": "Price not found"}), 404
        if seat_row["seats_available"] <= 0:
            return jsonify({"error": "No seats available on this flight"}), 400

        # Find or create user — use ON CONFLICT to safely handle existing names
        email = f"{passenger.lower().replace(' ','.')}@skyroute.app"
        cur.execute("SELECT user_id FROM users WHERE LOWER(full_name) = LOWER(%s)", (passenger,))
        user = cur.fetchone()
        if not user:
            # Reset sequence to avoid collision with pre-loaded CSV data
            cur.execute("SELECT setval('users_user_id_seq', (SELECT MAX(user_id) FROM users))")
            cur.execute("""
                INSERT INTO users(full_name, email, created_at)
                VALUES (%s, %s, NOW())
                ON CONFLICT (email) DO UPDATE SET full_name = EXCLUDED.full_name
                RETURNING user_id
            """, (passenger, email))
            user = cur.fetchone()
        user_id = user["user_id"]

        # Insert booking — this fires trg_update_seats automatically
        seat_row_num = random.randint(1, 40)
        seat_col = random.choice(["A","B","C","D","E","F"])
        cur.execute("""
            INSERT INTO booking(user_id, flight_id, price_id, booking_date,
                                booking_status, seat_number, total_paid)
            VALUES (%s, %s, %s, NOW(), 'Confirmed', %s, %s)
            RETURNING booking_id
        """, (user_id, flight_id, price_id, f"{seat_row_num}{seat_col}", price))
        booking_id = cur.fetchone()["booking_id"]

        # Read updated seats (trigger already ran)
        cur.execute("SELECT seats_available FROM flight_price WHERE price_id = %s", (price_id,))
        new_seats = cur.fetchone()["seats_available"]

        conn.commit(); cur.close(); conn.close()
        return jsonify({
            "success":    True,
            "booking_id": booking_id,
            "reference":  booking_ref(),
            "passenger":  passenger,
            "cabin":      cabin,
            "seat":       f"{seat_row_num}{seat_col}",
            "total_paid": price,
            "seats_remaining": new_seats,
            "trigger_fired": "trg_update_seats decremented seats_available"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ── RECOMMENDATIONS (calls stored procedure) ─────────────────
@app.route("/api/recommend")
def api_recommend():
    """
    Calls the get_user_recommendations() stored procedure.
    Finds top-N routes not yet flown by this user,
    ranked by how often similar users booked them.
    """
    name  = request.args.get("name", "").strip()
    limit = int(request.args.get("limit", 5))
    if not name:
        return jsonify({"error": "name required"}), 400
    try:
        conn = get_conn(); cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT user_id, full_name FROM users WHERE LOWER(full_name) LIKE LOWER(%s) LIMIT 1",
                    (f"%{name}%",))
        user = cur.fetchone()
        if not user:
            return jsonify({"error": f"No user found matching '{name}'"}), 404

        # Call stored procedure
        cur.execute("SELECT * FROM get_user_recommendations(%s, %s)", (user["user_id"], limit))
        rows = cur.fetchall()

        # Get routes already flown for context
        cur.execute("""
            SELECT DISTINCT oc.city_name AS origin, dc.city_name AS destination
            FROM booking b
            JOIN flight f ON b.flight_id=f.flight_id
            JOIN city oc  ON f.origin_city_id=oc.city_id
            JOIN city dc  ON f.destination_city_id=dc.city_id
            WHERE b.user_id=%s AND b.booking_status<>'Cancelled'
        """, (user["user_id"],))
        already_flown = [{"origin": r["origin"], "destination": r["destination"]} for r in cur.fetchall()]

        recs = [{
            "flight_id":     r["flight_id"],
            "flight_number": r["flight_number"],
            "origin":        r["origin"],
            "destination":   r["destination"],
            "airline":       r["airline_name"],
            "popularity":    r["popularity"],
        } for r in rows]

        cur.close(); conn.close()
        return jsonify({
            "user_id":       user["user_id"],
            "user":          user["full_name"],
            "recommendations": recs,
            "already_flown": already_flown,
            "procedure_called": "get_user_recommendations()",
            "count": len(recs)
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ── CITY STATS ───────────────────────────────────────────────
@app.route("/api/city/<int:city_id>")
def api_city_stats(city_id):
    """Returns stats for a city: top routes, top airlines, total bookings."""
    try:
        conn = get_conn(); cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("SELECT city_name, country, iata_code FROM city WHERE city_id=%s", (city_id,))
        city = cur.fetchone()
        if not city:
            return jsonify({"error": "City not found"}), 404

        cur.execute("""
            SELECT dc.city_name AS to_city, a.airline_name,
                   COUNT(b.booking_id) AS bookings,
                   ROUND(AVG(b.total_paid)::numeric,2) AS avg_fare
            FROM flight f
            JOIN airline a ON f.airline_id=a.airline_id
            JOIN city dc   ON f.destination_city_id=dc.city_id
            LEFT JOIN booking b ON b.flight_id=f.flight_id AND b.booking_status<>'Cancelled'
            WHERE f.origin_city_id=%s
            GROUP BY dc.city_name, a.airline_name
            ORDER BY bookings DESC LIMIT 8
        """, (city_id,))
        outbound = [dict(r) for r in cur.fetchall()]

        cur.execute("""
            SELECT a.airline_name, COUNT(b.booking_id) AS bookings,
                   ROUND(SUM(b.total_paid)::numeric,2) AS revenue
            FROM flight f
            JOIN airline a ON f.airline_id=a.airline_id
            LEFT JOIN booking b ON b.flight_id=f.flight_id AND b.booking_status<>'Cancelled'
            WHERE f.origin_city_id=%s OR f.destination_city_id=%s
            GROUP BY a.airline_name ORDER BY bookings DESC LIMIT 5
        """, (city_id, city_id))
        top_airlines = [dict(r) for r in cur.fetchall()]

        cur.execute("""
            SELECT COUNT(b.booking_id) AS total_bookings,
                   ROUND(SUM(b.total_paid)::numeric,2) AS total_revenue
            FROM flight f
            LEFT JOIN booking b ON b.flight_id=f.flight_id AND b.booking_status<>'Cancelled'
            WHERE f.origin_city_id=%s OR f.destination_city_id=%s
        """, (city_id, city_id))
        totals = dict(cur.fetchone())
        cur.close(); conn.close()
        return jsonify({
            "city":         dict(city),
            "outbound":     outbound,
            "top_airlines": top_airlines,
            "total_bookings": totals["total_bookings"],
            "total_revenue":  float(totals["total_revenue"] or 0),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ── PRICE TRACKER ────────────────────────────────────────────
@app.route("/api/prices")
def api_prices():
    """Compare Economy vs Business vs First across all airlines on a route."""
    origin = request.args.get("origin")
    dest   = request.args.get("dest")
    if not origin or not dest:
        return jsonify({"error": "origin and dest required"}), 400
    try:
        conn = get_conn(); cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT a.airline_name, a.iata_code,
                   MIN(CASE WHEN fp.cabin_class='Economy'  THEN fp.base_price END) AS eco_min,
                   MAX(CASE WHEN fp.cabin_class='Economy'  THEN fp.base_price END) AS eco_max,
                   MIN(CASE WHEN fp.cabin_class='Business' THEN fp.base_price END) AS bus_min,
                   MAX(CASE WHEN fp.cabin_class='Business' THEN fp.base_price END) AS bus_max,
                   MIN(CASE WHEN fp.cabin_class='First'    THEN fp.base_price END) AS fst_min,
                   MAX(CASE WHEN fp.cabin_class='First'    THEN fp.base_price END) AS fst_max,
                   COUNT(DISTINCT b.booking_id) AS bookings
            FROM flight f
            JOIN airline a       ON f.airline_id=a.airline_id
            JOIN city    oc      ON f.origin_city_id=oc.city_id
            JOIN city    dc      ON f.destination_city_id=dc.city_id
            JOIN flight_price fp ON fp.flight_id=f.flight_id
            LEFT JOIN booking b  ON b.flight_id=f.flight_id AND b.booking_status<>'Cancelled'
            WHERE oc.city_id=%s AND dc.city_id=%s
            GROUP BY a.airline_name, a.iata_code
            ORDER BY eco_min ASC NULLS LAST
        """, (origin, dest))
        rows = cur.fetchall()

        cur.execute("SELECT city_name, iata_code FROM city WHERE city_id=%s", (origin,))
        o = cur.fetchone()
        cur.execute("SELECT city_name, iata_code FROM city WHERE city_id=%s", (dest,))
        d = cur.fetchone()
        cur.close(); conn.close()

        result = []
        for r in rows:
            result.append({
                "airline":   r["airline_name"],
                "iata_code": r["iata_code"],
                "economy":   {"min": float(r["eco_min"]) if r["eco_min"] else None,
                              "max": float(r["eco_max"]) if r["eco_max"] else None},
                "business":  {"min": float(r["bus_min"]) if r["bus_min"] else None,
                              "max": float(r["bus_max"]) if r["bus_max"] else None},
                "first":     {"min": float(r["fst_min"]) if r["fst_min"] else None,
                              "max": float(r["fst_max"]) if r["fst_max"] else None},
                "bookings":  r["bookings"],
            })
        return jsonify({
            "origin":      dict(o) if o else {},
            "destination": dict(d) if d else {},
            "airlines":    result,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ── ADMIN ROUTES ─────────────────────────────────────────────
@app.route("/api/admin/auth", methods=["POST"])
def api_admin_auth():
    data = request.get_json()
    if data and data.get("password") == ADMIN_PASSWORD:
        return jsonify({"ok": True})
    return jsonify({"ok": False}), 401

@app.route("/api/admin/summary")
def api_admin_summary():
    conn = get_conn(); cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT
            (SELECT COUNT(*) FROM booking WHERE booking_status<>'Cancelled') AS total_bookings,
            (SELECT ROUND(SUM(total_paid)::numeric,2) FROM booking WHERE booking_status<>'Cancelled') AS total_revenue,
            (SELECT COUNT(*) FROM users)   AS total_users,
            (SELECT COUNT(*) FROM flight)  AS total_flights,
            (SELECT COUNT(*) FROM airline) AS total_airlines,
            (SELECT COUNT(*) FROM city)    AS total_cities
    """)
    row = dict(cur.fetchone()); cur.close(); conn.close()
    return jsonify(row)

@app.route("/api/admin/top_routes")
def api_top_routes():
    conn = get_conn(); cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT oc.city_name AS origin, dc.city_name AS destination,
               oc.iata_code AS origin_iata, dc.iata_code AS dest_iata,
               COUNT(b.booking_id) AS bookings,
               ROUND(SUM(b.total_paid)::numeric,2) AS revenue,
               ROUND(AVG(b.total_paid)::numeric,2) AS avg_fare
        FROM booking b JOIN flight f ON b.flight_id=f.flight_id
        JOIN city oc ON f.origin_city_id=oc.city_id
        JOIN city dc ON f.destination_city_id=dc.city_id
        WHERE b.booking_status<>'Cancelled'
        GROUP BY oc.city_name,dc.city_name,oc.iata_code,dc.iata_code
        ORDER BY bookings DESC LIMIT 10
    """)
    rows = [dict(r) for r in cur.fetchall()]; cur.close(); conn.close()
    return jsonify(rows)

@app.route("/api/admin/airlines")
def api_admin_airlines():
    conn = get_conn(); cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT a.airline_name, a.iata_code, a.hub_city,
               COUNT(b.booking_id) AS bookings,
               ROUND(SUM(b.total_paid)::numeric,2) AS revenue,
               ROUND(AVG(b.total_paid)::numeric,2) AS avg_fare
        FROM airline a
        LEFT JOIN flight f ON f.airline_id=a.airline_id
        LEFT JOIN booking b ON b.flight_id=f.flight_id AND b.booking_status<>'Cancelled'
        GROUP BY a.airline_id,a.airline_name,a.iata_code,a.hub_city
        ORDER BY bookings DESC NULLS LAST
    """)
    rows = [dict(r) for r in cur.fetchall()]; cur.close(); conn.close()
    return jsonify(rows)

@app.route("/api/admin/monthly")
def api_admin_monthly():
    conn = get_conn(); cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT TO_CHAR(DATE_TRUNC('month',booking_date),'Mon YYYY') AS month,
               DATE_TRUNC('month',booking_date) AS month_date,
               COUNT(*) AS bookings, ROUND(SUM(total_paid)::numeric,2) AS revenue
        FROM booking WHERE booking_status<>'Cancelled'
        GROUP BY DATE_TRUNC('month',booking_date) ORDER BY month_date
    """)
    rows = [dict(r) for r in cur.fetchall()]
    for r in rows: r["month_date"] = str(r["month_date"])
    cur.close(); conn.close()
    return jsonify(rows)

@app.route("/api/admin/zero_routes")
def api_zero_routes():
    conn = get_conn(); cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT f.flight_number, a.airline_name, oc.city_name AS origin, dc.city_name AS destination
        FROM flight f JOIN airline a ON f.airline_id=a.airline_id
        JOIN city oc ON f.origin_city_id=oc.city_id
        JOIN city dc ON f.destination_city_id=dc.city_id
        WHERE NOT EXISTS (SELECT 1 FROM booking b WHERE b.flight_id=f.flight_id)
        ORDER BY a.airline_name
    """)
    rows = [dict(r) for r in cur.fetchall()]; cur.close(); conn.close()
    return jsonify(rows)

@app.route("/api/admin/cabin_mix")
def api_cabin_mix():
    conn = get_conn(); cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT fp.cabin_class, COUNT(*) AS bookings,
               ROUND(SUM(b.total_paid)::numeric,2) AS revenue
        FROM booking b JOIN flight_price fp ON b.price_id=fp.price_id
        WHERE b.booking_status<>'Cancelled'
        GROUP BY fp.cabin_class ORDER BY bookings DESC
    """)
    rows = [dict(r) for r in cur.fetchall()]; cur.close(); conn.close()
    return jsonify(rows)

@app.route("/api/admin/status_breakdown")
def api_status_breakdown():
    conn = get_conn(); cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT booking_status, COUNT(*) AS count FROM booking GROUP BY booking_status ORDER BY count DESC")
    rows = [dict(r) for r in cur.fetchall()]; cur.close(); conn.close()
    return jsonify(rows)

@app.route("/api/admin/top_nationalities")
def api_top_nationalities():
    conn = get_conn(); cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT u.nationality, COUNT(b.booking_id) AS bookings,
               ROUND(SUM(b.total_paid)::numeric,2) AS revenue
        FROM booking b JOIN users u ON b.user_id=u.user_id
        WHERE b.booking_status<>'Cancelled' AND u.nationality IS NOT NULL
        GROUP BY u.nationality ORDER BY bookings DESC LIMIT 10
    """)
    rows = [dict(r) for r in cur.fetchall()]; cur.close(); conn.close()
    return jsonify(rows)

@app.route("/")
def index():
    return render_template_string(UI)

# ── UI ────────────────────────────────────────────────────────
UI = r"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<title>SkyRoute</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<style>
:root{
  --maroon:#7B1535;--maroon-l:#A01D44;
  --gold:#C8A96E;--gold-l:#E8C98E;
  --bg:#07090F;--bg2:#0C1018;
  --glass:rgba(255,255,255,0.04);--gb:rgba(200,169,110,0.12);
  --txt:#E4E6F0;--muted:#7880A0;
  --green:#00E5A0;--red:#FF4D6A;--blue:#4DA6FF;--amber:#FFB347;--purple:#A78BFA;
}
*{box-sizing:border-box;margin:0;padding:0;}
body{font-family:'Segoe UI',Arial,sans-serif;background:var(--bg);color:var(--txt);min-height:100vh;}
body::before{content:'';position:fixed;inset:0;z-index:0;
  background-image:linear-gradient(rgba(200,169,110,.025) 1px,transparent 1px),
    linear-gradient(90deg,rgba(200,169,110,.025) 1px,transparent 1px);
  background-size:50px 50px;pointer-events:none;}
.glow{position:fixed;top:-300px;left:50%;transform:translateX(-50%);width:900px;height:700px;
  z-index:0;pointer-events:none;
  background:radial-gradient(ellipse,rgba(123,21,53,.2) 0%,transparent 65%);
  animation:gp 8s ease-in-out infinite;}
@keyframes gp{0%,100%{opacity:.5}50%{opacity:1}}

/* HEADER */
header{position:sticky;top:0;z-index:100;height:60px;
  background:rgba(7,9,15,.9);backdrop-filter:blur(24px);
  border-bottom:1px solid var(--gb);
  display:flex;align-items:center;justify-content:space-between;padding:0 28px;}
.logo{display:flex;align-items:center;gap:10px;cursor:pointer;}
.logo-mark{width:32px;height:32px;border-radius:7px;
  background:linear-gradient(135deg,var(--maroon),var(--gold));
  display:flex;align-items:center;justify-content:center;font-size:16px;}
.logo-name{font-size:18px;font-weight:800;
  background:linear-gradient(90deg,#fff,var(--gold));
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;}

/* NAV TABS */
.nav-tabs{display:flex;gap:2px;background:var(--glass);border:1px solid var(--gb);
  border-radius:10px;padding:3px;}
.nav-tab{padding:6px 16px;border:none;background:none;cursor:pointer;
  font-size:12px;font-weight:600;color:var(--muted);border-radius:7px;transition:all .2s;
  white-space:nowrap;}
.nav-tab.active{background:linear-gradient(135deg,var(--maroon),var(--maroon-l));color:#fff;}
.hdr-right{display:flex;align-items:center;gap:8px;font-size:12px;color:var(--muted);}
.dot{width:7px;height:7px;background:var(--green);border-radius:50%;
  box-shadow:0 0 6px var(--green);animation:blink 2s infinite;}
@keyframes blink{0%,100%{opacity:1}50%{opacity:.2}}

main{position:relative;z-index:1;max-width:1060px;margin:0 auto;padding:28px 20px;}
.panel{display:none;animation:fi .2s ease;}
.panel.active{display:block;}
@keyframes fi{from{opacity:0;transform:translateY(5px)}to{opacity:1;transform:none}}

/* SEARCH HERO */
.hero{text-align:center;padding:32px 0 24px;}
.hero h1{font-size:40px;font-weight:800;line-height:1.1;margin-bottom:8px;
  background:linear-gradient(135deg,#fff 20%,var(--gold));
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;}
.hero p{font-size:13px;color:var(--muted);}

/* SEARCH CARD */
.search-card{background:var(--glass);border:1px solid var(--gb);border-radius:16px;
  padding:20px;backdrop-filter:blur(16px);}
.sg{display:grid;grid-template-columns:1fr auto 1fr auto auto;gap:10px;align-items:end;}
.field{display:flex;flex-direction:column;gap:4px;}
.field label{font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:1px;font-weight:600;}
select,input{background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.09);
  border-radius:8px;padding:10px 12px;color:var(--txt);font-size:13px;outline:none;
  transition:border-color .2s;width:100%;}
select:focus,input:focus{border-color:var(--gold);}
select option{background:#0C1018;}
.swap-btn{background:var(--glass);border:1px solid var(--gb);border-radius:8px;
  padding:10px 14px;cursor:pointer;color:var(--gold);font-size:18px;align-self:flex-end;
  transition:all .2s;line-height:1;}
.swap-btn:hover{background:rgba(200,169,110,.1);transform:scale(1.1);}

/* BUTTONS */
.btn{padding:10px 20px;border-radius:8px;border:none;font-size:13px;
  font-weight:700;cursor:pointer;transition:all .2s;}
.btn-primary{background:linear-gradient(135deg,var(--maroon),var(--maroon-l));
  color:#fff;box-shadow:0 4px 16px rgba(123,21,53,.4);}
.btn-primary:hover{transform:translateY(-1px);box-shadow:0 6px 22px rgba(123,21,53,.6);}
.btn-ghost{background:var(--glass);border:1px solid var(--gb);color:var(--muted);}
.btn-ghost:hover{color:var(--gold);border-color:var(--gold);}
.btn-green{background:linear-gradient(135deg,#00b57a,var(--green));color:#001a0f;font-weight:800;}
.btn-green:hover{transform:translateY(-1px);}
.btn-gold{background:linear-gradient(135deg,var(--gold),var(--gold-l));color:#1a0900;font-weight:800;}

/* RESULT HEADER */
.result-header{display:flex;align-items:center;justify-content:space-between;margin:22px 0 12px;}
.result-title{font-size:13px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:1px;}
.result-sub{font-size:11px;color:var(--muted);margin-top:3px;}
.rc{font-size:11px;color:var(--muted);background:var(--glass);
  border:1px solid var(--gb);border-radius:12px;padding:2px 10px;}
.sort-row{display:flex;gap:5px;align-items:center;}
.sort-btn{padding:4px 11px;border-radius:6px;border:1px solid var(--gb);
  background:none;color:var(--muted);font-size:11px;cursor:pointer;transition:all .2s;}
.sort-btn.active{background:rgba(200,169,110,.08);color:var(--gold);border-color:var(--gold);}

/* FLIGHT RESULT CARD */
.fr{background:var(--glass);border:1px solid var(--gb);border-radius:13px;
  margin-bottom:10px;overflow:hidden;transition:all .25s;}
.fr:hover{border-color:rgba(200,169,110,.4);box-shadow:0 8px 28px rgba(0,0,0,.5);}
.fr-badges{display:flex;gap:6px;padding:8px 14px 0;min-height:24px;}
.badge-hot{background:rgba(0,229,160,.1);border:1px solid rgba(0,229,160,.25);
  color:var(--green);font-size:9px;font-weight:700;padding:2px 7px;border-radius:8px;
  text-transform:uppercase;letter-spacing:.5px;}
.badge-connect{background:rgba(77,166,255,.1);border:1px solid rgba(77,166,255,.25);
  color:var(--blue);font-size:9px;font-weight:700;padding:2px 7px;border-radius:8px;
  text-transform:uppercase;letter-spacing:.5px;}
.fr-main{display:grid;grid-template-columns:108px 1fr 75px 200px;align-items:center;}
.fr-airline{padding:12px 14px;border-right:1px solid var(--gb);text-align:center;}
.alc{font-size:19px;font-weight:900;color:var(--gold);letter-spacing:-.5px;}
.aln{font-size:9px;color:var(--muted);margin-top:1px;line-height:1.3;}
.fln{font-size:9px;color:rgba(200,169,110,.5);margin-top:2px;}
.fr-route{padding:12px 18px;display:flex;align-items:center;}
.frc{text-align:center;min-width:65px;}
.fri{font-size:24px;font-weight:900;letter-spacing:-1px;}
.frn{font-size:9px;color:var(--muted);margin-top:1px;}
.frt{font-size:11px;color:rgba(200,169,110,.7);margin-top:2px;font-weight:600;}
.fr-mid{flex:1;display:flex;flex-direction:column;align-items:center;padding:0 10px;gap:2px;}
.fr-line{display:flex;align-items:center;width:100%;gap:4px;}
.fl{flex:1;height:1px;background:linear-gradient(90deg,transparent,var(--gold),transparent);}
.pl{font-size:11px;}
.frd{font-size:9px;color:var(--muted);}
.frv{font-size:9px;color:var(--blue);}
.fra{font-size:8px;color:rgba(200,169,110,.4);}
.fr-pop{padding:12px 8px;border-left:1px solid var(--gb);text-align:center;}
.pn{font-size:17px;font-weight:800;color:var(--green);}
.pl2{font-size:8px;color:var(--muted);text-transform:uppercase;letter-spacing:1px;margin-top:1px;}
.fr-prices{padding:12px 14px;border-left:1px solid var(--gb);}
.pr{display:flex;justify-content:space-between;align-items:center;
  padding:2px 0;border-bottom:1px solid rgba(255,255,255,.04);}
.pr:last-child{border:none;}
.pc{font-size:9px;font-weight:700;letter-spacing:.5px;}
.pc-eco{color:var(--green)}.pc-bus{color:var(--blue)}.pc-fst{color:var(--gold)}
.pv{font-size:12px;font-weight:700;}
.book-btn-wrap{padding:8px 14px 12px;display:flex;gap:6px;flex-wrap:wrap;}
.book-btn{padding:5px 12px;border-radius:6px;border:none;font-size:11px;
  font-weight:700;cursor:pointer;transition:all .2s;}
.book-eco{background:rgba(0,229,160,.12);color:var(--green);border:1px solid rgba(0,229,160,.3);}
.book-eco:hover{background:rgba(0,229,160,.2);}
.book-bus{background:rgba(77,166,255,.12);color:var(--blue);border:1px solid rgba(77,166,255,.3);}
.book-bus:hover{background:rgba(77,166,255,.2);}
.book-fst{background:rgba(200,169,110,.12);color:var(--gold);border:1px solid rgba(200,169,110,.3);}
.book-fst:hover{background:rgba(200,169,110,.2);}

/* BOOKING MODAL */
.modal-bg{position:fixed;inset:0;z-index:200;background:rgba(0,0,0,.7);
  backdrop-filter:blur(8px);display:flex;align-items:center;justify-content:center;}
.modal{background:#0D1220;border:1px solid var(--gb);border-radius:16px;
  padding:28px;width:400px;max-width:90vw;}
.modal-title{font-size:17px;font-weight:800;margin-bottom:4px;}
.modal-sub{font-size:12px;color:var(--muted);margin-bottom:20px;}
.modal-field{margin-bottom:14px;}
.modal-field label{font-size:10px;color:var(--muted);text-transform:uppercase;
  letter-spacing:1px;display:block;margin-bottom:5px;}
.modal-summary{background:var(--glass);border:1px solid var(--gb);border-radius:10px;
  padding:14px;margin-bottom:16px;font-size:13px;}
.modal-summary .row{display:flex;justify-content:space-between;margin-bottom:6px;}
.modal-summary .row:last-child{margin:0;padding-top:8px;border-top:1px solid var(--gb);}
.modal-summary .label{color:var(--muted);font-size:11px;}
.modal-summary .val{font-weight:700;}
.modal-summary .val-gold{color:var(--gold);font-size:15px;font-weight:800;}
.modal-btns{display:flex;gap:8px;}

/* BOOKING CONFIRMATION */
.confirm-card{background:rgba(0,229,160,.05);border:1px solid rgba(0,229,160,.2);
  border-radius:12px;padding:20px;text-align:center;margin-top:16px;}
.confirm-icon{font-size:36px;margin-bottom:8px;}
.confirm-ref{font-size:22px;font-weight:800;color:var(--green);letter-spacing:2px;}
.confirm-sub{font-size:12px;color:var(--muted);margin-top:4px;}
.trigger-note{background:rgba(77,166,255,.06);border:1px solid rgba(77,166,255,.2);
  border-radius:8px;padding:10px 14px;margin-top:12px;font-size:11px;color:var(--blue);
  text-align:left;}

/* RECOMMENDATIONS PANEL */
.rec-search{background:var(--glass);border:1px solid var(--gb);border-radius:14px;
  padding:20px;margin-bottom:20px;}
.rec-row{display:flex;gap:10px;align-items:flex-end;}
.proc-note{background:rgba(167,139,250,.06);border:1px solid rgba(167,139,250,.2);
  border-radius:8px;padding:10px 14px;margin-top:14px;font-size:11px;color:var(--purple);}
.rec-card{background:var(--glass);border:1px solid var(--gb);border-radius:12px;
  padding:16px;margin-bottom:10px;display:grid;grid-template-columns:auto 1fr auto;
  gap:14px;align-items:center;transition:border-color .2s;}
.rec-card:hover{border-color:rgba(200,169,110,.3);}
.rec-rank{width:32px;height:32px;border-radius:50%;
  background:linear-gradient(135deg,var(--maroon),var(--gold));
  display:flex;align-items:center;justify-content:center;font-size:13px;font-weight:800;flex-shrink:0;}
.rec-route{font-size:15px;font-weight:700;}
.rec-meta{font-size:11px;color:var(--muted);margin-top:2px;}
.rec-pop{text-align:right;}
.rec-pop-num{font-size:18px;font-weight:800;color:var(--gold);}
.rec-pop-label{font-size:9px;color:var(--muted);text-transform:uppercase;}
.already-flown{margin-top:20px;}
.af-title{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:1px;margin-bottom:10px;}
.af-grid{display:flex;flex-wrap:wrap;gap:8px;}
.af-tag{background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.08);
  border-radius:6px;padding:4px 10px;font-size:11px;color:var(--muted);}

/* PRICE TRACKER */
.pt-search{background:var(--glass);border:1px solid var(--gb);border-radius:14px;
  padding:20px;margin-bottom:20px;}
.pt-grid{display:grid;grid-template-columns:1fr auto 1fr auto;gap:10px;align-items:end;}
.pt-card{background:var(--glass);border:1px solid var(--gb);border-radius:12px;
  margin-bottom:10px;overflow:hidden;}
.pt-header{padding:14px 16px;border-bottom:1px solid var(--gb);
  display:flex;justify-content:space-between;align-items:center;}
.pt-airline{font-size:14px;font-weight:700;}
.pt-iata{font-size:11px;color:var(--muted);}
.pt-bk{font-size:11px;color:var(--green);}
.pt-cabins{display:grid;grid-template-columns:repeat(3,1fr);gap:0;}
.pt-cabin{padding:12px 14px;text-align:center;border-right:1px solid var(--gb);}
.pt-cabin:last-child{border:none;}
.pt-cabin-name{font-size:9px;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;}
.pt-cabin-eco .pt-cabin-name{color:var(--green);}
.pt-cabin-bus .pt-cabin-name{color:var(--blue);}
.pt-cabin-fst .pt-cabin-name{color:var(--gold);}
.pt-price{font-size:15px;font-weight:800;}
.pt-range{font-size:9px;color:var(--muted);margin-top:1px;}
.pt-na{font-size:12px;color:rgba(255,255,255,.2);}

/* CITY STATS */
.city-select-row{display:flex;gap:10px;align-items:flex-end;margin-bottom:20px;}
.city-stat-grid{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:16px;}
.cs-card{background:var(--glass);border:1px solid var(--gb);border-radius:12px;padding:18px;}
.cs-title{font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:1px;margin-bottom:12px;}
.cs-kpi{font-size:28px;font-weight:800;color:var(--gold);}
.cs-kpi-label{font-size:11px;color:var(--muted);margin-top:2px;}
.cs-row{display:flex;justify-content:space-between;align-items:center;
  padding:7px 0;border-bottom:1px solid rgba(255,255,255,.04);font-size:12px;}
.cs-row:last-child{border:none;}

/* ADMIN */
.admin-grid-4{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:18px;}
.kpi{background:var(--glass);border:1px solid var(--gb);border-radius:12px;padding:16px;
  transition:border-color .2s;}
.kpi:hover{border-color:var(--gold);}
.kpi-val{font-size:24px;font-weight:800;}
.kpi-label{font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:1px;margin-top:3px;}
.kpi-gold .kpi-val{color:var(--gold);} .kpi-green .kpi-val{color:var(--green);}
.kpi-blue .kpi-val{color:var(--blue);} .kpi-amber .kpi-val{color:var(--amber);}
.kpi-red .kpi-val{color:var(--red);} .kpi-purple .kpi-val{color:var(--purple);}
.admin-row{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:14px;}
.admin-row-3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:14px;margin-bottom:14px;}
.card{background:var(--glass);border:1px solid var(--gb);border-radius:13px;padding:18px;}
.card-title{font-size:11px;font-weight:700;color:var(--muted);text-transform:uppercase;
  letter-spacing:1px;margin-bottom:14px;display:flex;align-items:center;gap:6px;}
.chart-wrap{position:relative;width:100%;}
.rt{width:100%;border-collapse:collapse;font-size:12px;}
.rt th{color:var(--muted);font-size:10px;text-transform:uppercase;letter-spacing:1px;
  padding:5px 9px;border-bottom:1px solid var(--gb);text-align:left;font-weight:600;}
.rt td{padding:8px 9px;border-bottom:1px solid rgba(255,255,255,.03);}
.rt tr:hover td{background:rgba(255,255,255,.02);}
.tag{display:inline-block;padding:2px 6px;border-radius:4px;font-size:10px;font-weight:700;}
.tag-gold{background:rgba(200,169,110,.1);color:var(--gold);border:1px solid rgba(200,169,110,.2);}
.tag-red{background:rgba(255,77,106,.1);color:var(--red);border:1px solid rgba(255,77,106,.2);}

/* LOCK */
.lock-screen{position:fixed;inset:0;z-index:200;background:rgba(7,9,15,.97);
  backdrop-filter:blur(20px);display:flex;align-items:center;justify-content:center;}
.lock-card{background:var(--glass);border:1px solid var(--gb);border-radius:18px;
  padding:36px;width:340px;text-align:center;}
.lock-icon{font-size:34px;margin-bottom:14px;}
.lock-title{font-size:19px;font-weight:800;margin-bottom:5px;}
.lock-sub{font-size:12px;color:var(--muted);margin-bottom:22px;}
.lock-err{color:var(--red);font-size:11px;margin-top:8px;min-height:16px;}

.loader{text-align:center;padding:40px;color:var(--muted);}
.spin{width:26px;height:26px;border:2px solid var(--gb);border-top-color:var(--gold);
  border-radius:50%;animation:spin .7s linear infinite;margin:0 auto 10px;}
@keyframes spin{to{transform:rotate(360deg)}}
.no-res{text-align:center;padding:48px 20px;color:var(--muted);}
.no-res .ic{font-size:44px;opacity:.3;margin-bottom:10px;}
.no-res h3{font-size:15px;margin-bottom:5px;color:var(--txt);}
::-webkit-scrollbar{width:5px;}
::-webkit-scrollbar-track{background:var(--bg);}
::-webkit-scrollbar-thumb{background:var(--gb);border-radius:3px;}
</style>
</head>
<body>
<div class="glow"></div>

<!-- BOOKING MODAL -->
<div class="modal-bg" id="modal_bg" style="display:none" onclick="closeModal(event)">
  <div class="modal" id="modal_box">
    <div class="modal-title">Book Flight</div>
    <div class="modal-sub" id="modal_sub"></div>
    <div class="modal-summary" id="modal_summary"></div>
    <div class="modal-field" id="modal_name_field">
      <label>Your Full Name</label>
      <input type="text" id="modal_name" placeholder="Enter your name"/>
    </div>
    <div id="modal_confirm_area"></div>
    <div class="modal-btns" id="modal_btns">
      <button class="btn btn-green" style="flex:1" onclick="confirmBooking()">Confirm Booking</button>
      <button class="btn btn-ghost" onclick="closeModal()">Cancel</button>
    </div>
  </div>
</div>

<!-- LOCK SCREEN -->
<div class="lock-screen" id="lock_screen" style="display:none">
  <div class="lock-card">
    <div class="lock-icon">🔒</div>
    <div class="lock-title">Admin Access</div>
    <div class="lock-sub">Enter the admin password to continue</div>
    <input type="password" id="lock_pw" placeholder="Password" style="margin-bottom:10px"
           onkeydown="if(event.key==='Enter')tryLogin()"/>
    <button class="btn btn-primary" style="width:100%" onclick="tryLogin()">Unlock Dashboard</button>
    <div class="lock-err" id="lock_err"></div>
    <button class="btn btn-ghost" style="width:100%;margin-top:8px" onclick="cancelAdmin()">Cancel</button>
  </div>
</div>

<header>
  <div class="logo" onclick="switchTab('search',document.querySelector('.nav-tab'))">
    <div class="logo-mark">✈</div>
    <div class="logo-name">SKYROUTE</div>
  </div>
  <div class="nav-tabs">
    <button class="nav-tab active" onclick="switchTab('search',this)">✈ Search</button>
    <button class="nav-tab" onclick="switchTab('recommend',this)">⚡ Recommend</button>
    <button class="nav-tab" onclick="switchTab('prices',this)">💰 Price Tracker</button>
    <button class="nav-tab" onclick="switchTab('cities',this)">🌍 City Stats</button>
    <button class="nav-tab" onclick="requestAdmin(this)">⚙ Admin</button>
  </div>
  <div class="hdr-right"><div class="dot"></div><span>skyroute · PostgreSQL 18.4</span></div>
</header>

<main>

<!-- SEARCH -->
<div class="panel active" id="panel-search">
  <div class="hero">
    <h1>Where do you want to fly?</h1>
    <p>Search 309 routes across 27 cities and 16 airlines · connecting flights included · book instantly</p>
  </div>
  <div class="search-card">
    <div class="sg">
      <div class="field"><label>From</label>
        <select id="s_origin"><option value="">Select origin...</option></select></div>
      <button class="swap-btn" onclick="swapCities()">⇄</button>
      <div class="field"><label>To</label>
        <select id="s_dest"><option value="">Select destination...</option></select></div>
      <div class="field"><label>Cabin</label>
        <select id="s_cabin">
          <option value="">Any cabin</option>
          <option value="Economy">Economy</option>
          <option value="Business">Business</option>
          <option value="First">First Class</option>
        </select></div>
      <button class="btn btn-primary" style="padding:10px 24px" onclick="doSearch()">Search</button>
    </div>
  </div>
  <div id="search_result"></div>
</div>

<!-- RECOMMENDATIONS -->
<div class="panel" id="panel-recommend">
  <div class="hero" style="padding-bottom:0">
    <h1>Your Recommendations</h1>
    <p>Powered by the <code style="color:var(--purple)">get_user_recommendations()</code> stored procedure</p>
  </div>
  <div class="rec-search" style="margin-top:20px">
    <div class="rec-row">
      <div class="field" style="flex:1"><label>Passenger Name</label>
        <input type="text" id="rec_name" placeholder="Type a passenger name e.g. Amina Hassan"/></div>
      <div class="field" style="width:80px"><label>Top N</label>
        <input type="number" id="rec_n" value="5" min="1" max="20"/></div>
      <button class="btn btn-primary" onclick="getRecommendations()">Get Recommendations</button>
    </div>
    <div class="proc-note" style="margin-top:12px">
      🔮 <strong>Stored Procedure:</strong> <code>SELECT * FROM get_user_recommendations(user_id, limit)</code>
      — finds routes not yet flown by this passenger, ranked by how many similar users booked them (collaborative filtering).
    </div>
  </div>
  <div id="rec_result"></div>
</div>

<!-- PRICE TRACKER -->
<div class="panel" id="panel-prices">
  <div class="hero" style="padding-bottom:0">
    <h1>Price Tracker</h1>
    <p>Compare Economy, Business and First Class prices across every airline on a route</p>
  </div>
  <div class="pt-search" style="margin-top:20px">
    <div class="pt-grid">
      <div class="field"><label>From</label>
        <select id="pt_origin"><option value="">Select origin...</option></select></div>
      <button class="swap-btn" onclick="swapPtCities()">⇄</button>
      <div class="field"><label>To</label>
        <select id="pt_dest"><option value="">Select destination...</option></select></div>
      <button class="btn btn-primary" onclick="getPrices()">Compare Prices</button>
    </div>
  </div>
  <div id="pt_result"></div>
</div>

<!-- CITY STATS -->
<div class="panel" id="panel-cities">
  <div class="hero" style="padding-bottom:0">
    <h1>City Statistics</h1>
    <p>Click any city to see its busiest routes, top airlines, and booking stats</p>
  </div>
  <div style="margin-top:20px">
    <div class="city-select-row">
      <div class="field" style="flex:1"><label>Select City</label>
        <select id="city_select" onchange="getCityStats(this.value)">
          <option value="">Choose a city...</option>
        </select></div>
    </div>
    <div id="city_result"></div>
  </div>
</div>

<!-- ADMIN -->
<div class="panel" id="panel-admin">
  <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:20px">
    <div>
      <div style="font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:1px;margin-bottom:3px">Admin Dashboard</div>
      <div style="font-size:24px;font-weight:800">Operations Overview</div>
    </div>
    <button class="btn btn-ghost" onclick="lockAdmin()">&#128274; Lock</button>
  </div>
  <div class="admin-grid-4" id="admin_kpis"><div class="loader"><div class="spin"></div></div></div>
  <div class="admin-row" style="margin-bottom:14px">
    <div class="card">
      <div class="card-title">&#128200; Monthly Bookings &amp; Revenue</div>
      <div style="position:relative;height:200px"><canvas id="chart_monthly"></canvas></div>
    </div>
    <div class="card">
      <div class="card-title">&#127915; Bookings by Cabin Class</div>
      <div style="position:relative;height:200px"><canvas id="chart_cabin"></canvas></div>
    </div>
  </div>
  <div class="admin-row" style="margin-bottom:14px">
    <div class="card">
      <div class="card-title">&#9992; Revenue by Airline</div>
      <div style="position:relative;height:220px"><canvas id="chart_airlines"></canvas></div>
    </div>
    <div class="card">
      <div class="card-title">&#128202; Booking Status Breakdown</div>
      <div style="position:relative;height:220px"><canvas id="chart_status"></canvas></div>
    </div>
  </div>
  <div class="admin-row" style="margin-bottom:14px">
    <div class="card">
      <div class="card-title">&#127758; Top Nationalities</div>
      <div style="position:relative;height:200px"><canvas id="chart_national"></canvas></div>
    </div>
    <div class="card">
      <div class="card-title">&#128293; Top 10 Routes</div>
      <div id="admin_routes"><div class="loader"><div class="spin"></div></div></div>
    </div>
  </div>
  <div class="card">
    <div class="card-title">&#9888; Zero-Booking Routes <span style="font-size:10px;color:var(--red);margin-left:6px">(Expansion Opportunities)</span></div>
    <div id="admin_zero"></div>
  </div>
</div>

</main>

<script>
let cities=[], sortKey='popular', lastResults=[], adminUnlocked=false;
let bookingFlight=null, bookingCabin=null, bookingPriceId=null, bookingPrice=null;

async function init(){
  const res=await fetch('/api/cities'); cities=await res.json();
  const opts=cities.map(c=>`<option value="${c.city_id}">${c.city_name} (${c.iata_code}) — ${c.country}</option>`).join('');
  ['s_origin','s_dest','pt_origin','pt_dest'].forEach((id,i)=>{
    document.getElementById(id).innerHTML=`<option value="">${i%2===0?'Select origin...':'Select destination...'}</option>`+opts;
  });
  document.getElementById('city_select').innerHTML=
    '<option value="">Choose a city...</option>'+
    cities.map(c=>`<option value="${c.city_id}">${c.city_name} (${c.iata_code})</option>`).join('');
}

function switchTab(name,btn){
  document.querySelectorAll('.panel').forEach(p=>p.classList.remove('active'));
  document.querySelectorAll('.nav-tab').forEach(b=>b.classList.remove('active'));
  document.getElementById('panel-'+name).classList.add('active');
  btn.classList.add('active');
  if(name==='admin') loadAdmin();
}

function requestAdmin(btn){
  if(adminUnlocked){ switchTab('admin',btn); return; }
  document.getElementById('lock_screen').style.display='flex';
  document.getElementById('lock_pw').value='';
  document.getElementById('lock_err').textContent='';
  setTimeout(()=>document.getElementById('lock_pw').focus(),100);
  window._adminBtn=btn;
}
async function tryLogin(){
  const pw=document.getElementById('lock_pw').value;
  const res=await fetch('/api/admin/auth',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({password:pw})});
  if(res.ok){
    adminUnlocked=true;
    document.getElementById('lock_screen').style.display='none';
    switchTab('admin',window._adminBtn);
  } else {
    document.getElementById('lock_err').textContent='Incorrect password. Try again.';
    document.getElementById('lock_pw').value=''; document.getElementById('lock_pw').focus();
  }
}
function cancelAdmin(){ document.getElementById('lock_screen').style.display='none'; }
function lockAdmin(){ adminUnlocked=false; switchTab('search',document.querySelector('.nav-tab')); }

function swapCities(){
  const o=document.getElementById('s_origin'),d=document.getElementById('s_dest');
  const t=o.value; o.value=d.value; d.value=t;
  if(lastResults.length) doSearch();
}
function swapPtCities(){
  const o=document.getElementById('pt_origin'),d=document.getElementById('pt_dest');
  const t=o.value; o.value=d.value; d.value=t;
}

// ── SEARCH ──
async function doSearch(){
  const origin=document.getElementById('s_origin').value;
  const dest=document.getElementById('s_dest').value;
  const cabin=document.getElementById('s_cabin').value;
  if(!origin||!dest){alert('Please select both an origin and a destination.');return;}
  if(origin===dest){alert('Origin and destination cannot be the same city.');return;}
  document.getElementById('search_result').innerHTML=`<div class="loader" style="margin-top:28px"><div class="spin"></div>Searching flights...</div>`;
  const res=await fetch(`/api/search?origin=${origin}&dest=${dest}${cabin?'&cabin='+cabin:''}`);
  const data=await res.json();
  if(data.error){document.getElementById('search_result').innerHTML=`<div class="no-res"><div class="ic">⚠</div><h3>${data.error}</h3></div>`;return;}
  lastResults=data.flights||[]; sortKey='popular'; renderResults();
}

function setSort(key){
  sortKey=key;
  document.querySelectorAll('.sort-btn').forEach(b=>b.classList.toggle('active',b.dataset.sort===key));
  renderResults();
}

function renderResults(){
  const div=document.getElementById('search_result');
  if(!lastResults.length){
    div.innerHTML=`<div class="no-res"><div class="ic">🔍</div><h3>No flights found</h3><p>Try a different route</p></div>`;return;
  }
  let flights=[...lastResults];
  if(sortKey==='price')    flights.sort((a,b)=>(a.min_price||999999)-(b.min_price||999999));
  if(sortKey==='popular')  flights.sort((a,b)=>b.total_bookings-a.total_bookings);
  if(sortKey==='duration') flights.sort((a,b)=>a.duration_minutes-b.duration_minutes);
  const maxPop=Math.max(...flights.map(f=>f.total_bookings));
  const dir=flights.filter(f=>f.is_direct).length, con=flights.filter(f=>!f.is_direct).length;
  const sub=dir&&con?`${dir} direct · ${con} via 1 stop`:dir?`${dir} direct flight${dir>1?'s':''}`:
    `No direct flights · ${con} connecting route${con>1?'s':''}`;

  let html=`<div class="result-header">
    <div><div class="result-title">${flights[0].origin} → ${flights[0].destination}</div>
    <div class="result-sub">${sub}</div></div>
    <div style="display:flex;align-items:center;gap:10px">
      <div class="rc">${flights.length} result${flights.length>1?'s':''}</div>
      <div class="sort-row">
        <span style="font-size:11px;color:var(--muted)">Sort:</span>
        <button class="sort-btn ${sortKey==='popular'?'active':''}" data-sort="popular" onclick="setSort('popular')">Popular</button>
        <button class="sort-btn ${sortKey==='price'?'active':''}" data-sort="price" onclick="setSort('price')">Cheapest</button>
        <button class="sort-btn ${sortKey==='duration'?'active':''}" data-sort="duration" onclick="setSort('duration')">Shortest</button>
      </div>
    </div>
  </div>`;

  flights.forEach(f=>{
    const isHot=f.is_direct&&f.total_bookings===maxPop&&maxPop>0;
    const hrs=Math.floor(f.duration_minutes/60), mins=f.duration_minutes%60;
    const dur=hrs>0?`${hrs}h ${mins}m`:`${mins}m`;
    const fid=f.flight_id, pid_eco=f.eco_price_id, pid_bus=f.bus_price_id, pid_fst=f.fst_price_id;

    html+=`<div class="fr">
      <div class="fr-badges">
        ${isHot?'<span class="badge-hot">⚡ Most Booked</span>':''}
        ${!f.is_direct?`<span class="badge-connect">🔗 1 Stop via ${f.stop_via}</span>`:''}
      </div>
      <div class="fr-main">
        <div class="fr-airline">
          <div class="alc">${f.airline_code}</div>
          <div class="aln">${f.airline}</div>
          <div class="fln">${f.flight_number}</div>
        </div>
        <div class="fr-route">
          <div class="frc">
            <div class="fri">${f.origin_iata}</div>
            <div class="frn">${f.origin}</div>
            <div class="frt">${f.departure_time}</div>
          </div>
          <div class="fr-mid">
            <div class="fr-line"><div class="fl"></div><div class="pl">✈</div><div class="fl"></div></div>
            <div class="frd">${f.is_direct?dur:dur+' total'}</div>
            ${f.stop_via?`<div class="frv">via ${f.stop_via}</div>`:''}
            ${f.aircraft_type?`<div class="fra">${f.aircraft_type}</div>`:''}
          </div>
          <div class="frc" style="text-align:right">
            <div class="fri">${f.dest_iata}</div>
            <div class="frn">${f.destination}</div>
            <div class="frt">${f.arrival_time}</div>
          </div>
        </div>
        <div class="fr-pop"><div class="pn">${f.total_bookings}</div><div class="pl2">Bookings</div></div>
        <div class="fr-prices">
          ${f.has_economy&&f.eco_price?`<div class="pr"><span class="pc pc-eco">Economy</span><span class="pv">$${Math.round(f.eco_price).toLocaleString()}</span></div>`:''}
          ${f.has_business&&f.bus_price?`<div class="pr"><span class="pc pc-bus">Business</span><span class="pv">$${Math.round(f.bus_price).toLocaleString()}</span></div>`:''}
          ${f.has_first&&f.fst_price?`<div class="pr"><span class="pc pc-fst">First</span><span class="pv">$${Math.round(f.fst_price).toLocaleString()}</span></div>`:''}
        </div>
      </div>
      ${f.is_direct?`<div class="book-btn-wrap">
        ${f.has_economy&&f.eco_price&&pid_eco?`<button class="book-btn book-eco" onclick="openBooking(${JSON.stringify(f).replace(/"/g,'&quot;')},'Economy',${pid_eco},${Math.round(f.eco_price)})">Book Economy · $${Math.round(f.eco_price).toLocaleString()}</button>`:''}
        ${f.has_business&&f.bus_price&&pid_bus?`<button class="book-btn book-bus" onclick="openBooking(${JSON.stringify(f).replace(/"/g,'&quot;')},'Business',${pid_bus},${Math.round(f.bus_price)})">Book Business · $${Math.round(f.bus_price).toLocaleString()}</button>`:''}
        ${f.has_first&&f.fst_price&&pid_fst?`<button class="book-btn book-fst" onclick="openBooking(${JSON.stringify(f).replace(/"/g,'&quot;')},'First',${pid_fst},${Math.round(f.fst_price)})">Book First · $${Math.round(f.fst_price).toLocaleString()}</button>`:''}
      </div>`:'<div style="padding:8px 14px 12px;font-size:11px;color:var(--muted)">Connecting route — book each leg separately</div>'}
    </div>`;
  });
  div.innerHTML=html;
}

// ── BOOKING MODAL ──
function openBooking(flight, cabin, priceId, price){
  bookingFlight=flight; bookingCabin=cabin; bookingPriceId=priceId; bookingPrice=price;
  document.getElementById('modal_sub').textContent=`${flight.origin} → ${flight.destination} · ${flight.airline}`;
  document.getElementById('modal_summary').innerHTML=`
    <div class="row"><span class="label">Flight</span><span class="val">${flight.flight_number}</span></div>
    <div class="row"><span class="label">Route</span><span class="val">${flight.origin_iata} → ${flight.dest_iata}</span></div>
    <div class="row"><span class="label">Cabin</span><span class="val">${cabin}</span></div>
    <div class="row"><span class="label">Departure</span><span class="val">${flight.departure_time}</span></div>
    <div class="row"><span class="label">Total Price</span><span class="val val-gold">$${price.toLocaleString()}</span></div>
  `;
  document.getElementById('modal_name').value='';
  document.getElementById('modal_name_field').style.display='block';
  document.getElementById('modal_confirm_area').innerHTML='';
  document.getElementById('modal_btns').style.display='flex';
  document.getElementById('modal_bg').style.display='flex';
}

function closeModal(e){
  if(!e||e.target===document.getElementById('modal_bg'))
    document.getElementById('modal_bg').style.display='none';
}

async function confirmBooking(){
  const name=document.getElementById('modal_name').value.trim();
  if(!name){alert('Please enter your name.');return;}
  const btn=document.querySelector('#modal_btns .btn-green');
  btn.textContent='Booking...'; btn.disabled=true;
  const res=await fetch('/api/book',{method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({passenger_name:name,flight_id:bookingFlight.flight_id,
      price_id:bookingPriceId,cabin:bookingCabin,price:bookingPrice})});
  const data=await res.json();
  btn.textContent='Confirm Booking'; btn.disabled=false;
  if(data.error){alert('Booking failed: '+data.error);return;}
  document.getElementById('modal_name_field').style.display='none';
  document.getElementById('modal_btns').style.display='none';
  document.getElementById('modal_confirm_area').innerHTML=`
    <div class="confirm-card">
      <div class="confirm-icon">✅</div>
      <div class="confirm-ref">${data.reference}</div>
      <div class="confirm-sub">${data.passenger} · Seat ${data.seat} · ${data.cabin}</div>
      <div class="trigger-note">
        🔁 <strong>Trigger fired:</strong> <code>trg_update_seats</code> automatically decremented
        <code>seats_available</code> in <code>flight_price</code>.
        Seats remaining: <strong>${data.seats_remaining}</strong>
      </div>
    </div>
    <button class="btn btn-ghost" style="width:100%;margin-top:12px" onclick="closeModal()">Close</button>
  `;
}

// ── RECOMMENDATIONS ──
async function getRecommendations(){
  const name=document.getElementById('rec_name').value.trim();
  const n=document.getElementById('rec_n').value;
  if(!name){alert('Please enter a passenger name.');return;}
  document.getElementById('rec_result').innerHTML=`<div class="loader"><div class="spin"></div>Calling stored procedure...</div>`;
  const res=await fetch(`/api/recommend?name=${encodeURIComponent(name)}&limit=${n}`);
  const data=await res.json();
  if(data.error){document.getElementById('rec_result').innerHTML=`<div class="no-res"><div class="ic">⚠</div><h3>${data.error}</h3></div>`;return;}
  const maxPop=Math.max(...data.recommendations.map(r=>r.popularity),1);
  let html=`<div style="background:rgba(167,139,250,.06);border:1px solid rgba(167,139,250,.2);border-radius:10px;padding:12px 16px;margin-bottom:16px;font-size:12px;color:var(--purple)">
    ✅ Stored procedure <code>get_user_recommendations(${data.user_id}, ${n})</code> returned <strong>${data.count}</strong> routes for <strong>${data.user}</strong>
  </div>`;
  if(!data.recommendations.length){
    html+=`<div class="no-res"><div class="ic">🔍</div><h3>No recommendations found</h3><p>This user may have booked all available routes</p></div>`;
  } else {
    data.recommendations.forEach((r,i)=>{
      const pct=Math.round((r.popularity/maxPop)*100);
      html+=`<div class="rec-card">
        <div class="rec-rank">${i+1}</div>
        <div>
          <div class="rec-route">${r.origin} → ${r.destination}</div>
          <div class="rec-meta">${r.airline} · ${r.flight_number}</div>
          <div style="height:3px;background:rgba(255,255,255,.06);border-radius:2px;margin-top:7px;overflow:hidden">
            <div style="height:100%;width:${pct}%;background:linear-gradient(90deg,var(--maroon),var(--gold));border-radius:2px"></div>
          </div>
        </div>
        <div class="rec-pop"><div class="rec-pop-num">${r.popularity}</div><div class="rec-pop-label">Bookings</div></div>
      </div>`;
    });
  }
  if(data.already_flown.length){
    html+=`<div class="already-flown">
      <div class="af-title">Routes already flown by ${data.user} (excluded from recommendations)</div>
      <div class="af-grid">${data.already_flown.map(r=>`<span class="af-tag">${r.origin} → ${r.destination}</span>`).join('')}</div>
    </div>`;
  }
  document.getElementById('rec_result').innerHTML=html;
}

// ── PRICE TRACKER ──
async function getPrices(){
  const origin=document.getElementById('pt_origin').value;
  const dest=document.getElementById('pt_dest').value;
  if(!origin||!dest){alert('Please select both cities.');return;}
  if(origin===dest){alert('Origin and destination cannot be the same.');return;}
  document.getElementById('pt_result').innerHTML=`<div class="loader"><div class="spin"></div>Loading prices...</div>`;
  const res=await fetch(`/api/prices?origin=${origin}&dest=${dest}`);
  const data=await res.json();
  if(data.error){document.getElementById('pt_result').innerHTML=`<div class="no-res"><div class="ic">⚠</div><h3>${data.error}</h3></div>`;return;}
  if(!data.airlines.length){
    document.getElementById('pt_result').innerHTML=`<div class="no-res"><div class="ic">✈</div><h3>No direct flights on this route</h3></div>`;return;
  }
  let html=`<div class="result-header">
    <div class="result-title">${data.origin.city_name} (${data.origin.iata_code}) → ${data.destination.city_name} (${data.destination.iata_code})</div>
    <div class="rc">${data.airlines.length} airline${data.airlines.length>1?'s':''}</div>
  </div>`;
  data.airlines.forEach(a=>{
    const p=v=>v!=null?`$${Math.round(v).toLocaleString()}`:'—';
    const r=v=>v&&v.min!=null&&v.max!=null&&v.min!==v.max?`<div class="pt-range">$${Math.round(v.min).toLocaleString()} – $${Math.round(v.max).toLocaleString()}</div>`:'';
    html+=`<div class="pt-card">
      <div class="pt-header">
        <div><div class="pt-airline">${a.airline_name}</div><div class="pt-iata">${a.iata_code}</div></div>
        <div class="pt-bk">${a.bookings} bookings</div>
      </div>
      <div class="pt-cabins">
        <div class="pt-cabin pt-cabin-eco">
          <div class="pt-cabin-name">Economy</div>
          ${a.economy.min!=null?`<div class="pt-price">${p(a.economy.min)}</div>${r(a.economy)}`:`<div class="pt-na">Not offered</div>`}
        </div>
        <div class="pt-cabin pt-cabin-bus">
          <div class="pt-cabin-name">Business</div>
          ${a.business.min!=null?`<div class="pt-price">${p(a.business.min)}</div>${r(a.business)}`:`<div class="pt-na">Not offered</div>`}
        </div>
        <div class="pt-cabin pt-cabin-fst">
          <div class="pt-cabin-name">First Class</div>
          ${a.first.min!=null?`<div class="pt-price">${p(a.first.min)}</div>${r(a.first)}`:`<div class="pt-na">Not offered</div>`}
        </div>
      </div>
    </div>`;
  });
  document.getElementById('pt_result').innerHTML=html;
}

// ── CITY STATS ──
async function getCityStats(cityId){
  if(!cityId){document.getElementById('city_result').innerHTML='';return;}
  document.getElementById('city_result').innerHTML=`<div class="loader"><div class="spin"></div>Loading city stats...</div>`;
  const res=await fetch(`/api/city/${cityId}`);
  const data=await res.json();
  if(data.error){document.getElementById('city_result').innerHTML=`<div class="no-res"><div class="ic">⚠</div><h3>${data.error}</h3></div>`;return;}
  let html=`<div class="city-stat-grid">
    <div class="cs-card">
      <div class="cs-title">Total Bookings (all routes)</div>
      <div class="cs-kpi">${Number(data.total_bookings||0).toLocaleString()}</div>
      <div class="cs-kpi-label">confirmed + completed bookings</div>
    </div>
    <div class="cs-card">
      <div class="cs-title">Total Revenue</div>
      <div class="cs-kpi">$${Number(data.total_revenue||0).toLocaleString('en',{maximumFractionDigits:0})}</div>
      <div class="cs-kpi-label">from all flights through ${data.city.city_name}</div>
    </div>
  </div>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px">
    <div class="cs-card">
      <div class="cs-title">Top Outbound Routes from ${data.city.city_name}</div>`;
  data.outbound.forEach(r=>{
    html+=`<div class="cs-row">
      <span>${r.to_city} <span style="font-size:10px;color:var(--muted)">via ${r.airline_name}</span></span>
      <span style="color:var(--gold);font-weight:700">${r.bookings} bk</span>
    </div>`;
  });
  html+=`</div><div class="cs-card">
    <div class="cs-title">Top Airlines at ${data.city.city_name}</div>`;
  data.top_airlines.forEach(a=>{
    html+=`<div class="cs-row">
      <span>${a.airline_name}</span>
      <span style="color:var(--green);font-weight:700">${a.bookings} bk</span>
    </div>`;
  });
  html+=`</div></div>`;
  document.getElementById('city_result').innerHTML=html;
}

// ── ADMIN ──
let adminCharts={};
function destroyCharts(){Object.values(adminCharts).forEach(c=>{if(c)c.destroy();});adminCharts={};}

function mkChart(id,cfg){
  const ctx=document.getElementById(id);
  if(!ctx)return null;
  if(adminCharts[id])adminCharts[id].destroy();
  adminCharts[id]=new Chart(ctx,cfg);
  return adminCharts[id];
}

const GOLD='#C8A96E',GREEN='#00E5A0',BLUE='#4DA6FF',RED='#FF4D6A',
      AMBER='#FFB347',PURPLE='#A78BFA',MAROON='#7B1535';
const GRID={color:'rgba(255,255,255,0.05)'};
const TICK={color:'#7880A0',font:{size:10}};
const baseOpts={responsive:true,maintainAspectRatio:false,
  plugins:{legend:{display:false},tooltip:{backgroundColor:'#0C1018',borderColor:'#C8A96E',
    borderWidth:1,titleColor:'#E4E6F0',bodyColor:'#7880A0',padding:10}}};

async function loadAdmin(){
  destroyCharts();
  const[summary,routes,airlines,monthly,zero,cabin,status,national]=await Promise.all([
    fetch('/api/admin/summary').then(r=>r.json()),
    fetch('/api/admin/top_routes').then(r=>r.json()),
    fetch('/api/admin/airlines').then(r=>r.json()),
    fetch('/api/admin/monthly').then(r=>r.json()),
    fetch('/api/admin/zero_routes').then(r=>r.json()),
    fetch('/api/admin/cabin_mix').then(r=>r.json()),
    fetch('/api/admin/status_breakdown').then(r=>r.json()),
    fetch('/api/admin/top_nationalities').then(r=>r.json()),
  ]);

  // KPIs
  document.getElementById('admin_kpis').innerHTML=`
    <div class="kpi kpi-gold"><div class="kpi-val">${Number(summary.total_bookings).toLocaleString()}</div><div class="kpi-label">Total Bookings</div></div>
    <div class="kpi kpi-green"><div class="kpi-val">$${Number(summary.total_revenue).toLocaleString('en',{maximumFractionDigits:0})}</div><div class="kpi-label">Revenue</div></div>
    <div class="kpi kpi-blue"><div class="kpi-val">${summary.total_users}</div><div class="kpi-label">Users</div></div>
    <div class="kpi kpi-amber"><div class="kpi-val">${summary.total_flights}</div><div class="kpi-label">Active Routes</div></div>`;

  // Monthly line + bar chart
  mkChart('chart_monthly',{type:'bar',
    data:{labels:monthly.map(m=>m.month.split(' ')[0]),
      datasets:[
        {label:'Revenue',data:monthly.map(m=>Number(m.revenue)),
          backgroundColor:'rgba(200,169,110,0.15)',borderColor:GOLD,borderWidth:2,
          borderRadius:4,yAxisID:'y1'},
        {label:'Bookings',data:monthly.map(m=>m.bookings),
          type:'line',borderColor:GREEN,backgroundColor:'rgba(0,229,160,0.1)',
          borderWidth:2,pointRadius:3,pointBackgroundColor:GREEN,tension:0.4,yAxisID:'y'}
      ]},
    options:{...baseOpts,scales:{
      x:{grid:GRID,ticks:TICK},
      y:{grid:GRID,ticks:{...TICK,callback:v=>v},position:'left'},
      y1:{grid:{display:false},ticks:{...TICK,callback:v=>'$'+Math.round(v/1000)+'k'},position:'right'}
    },plugins:{...baseOpts.plugins,legend:{display:true,labels:{color:'#7880A0',font:{size:10}}}}}
  });

  // Cabin donut
  const cColors=[GREEN,BLUE,GOLD];
  mkChart('chart_cabin',{type:'doughnut',
    data:{labels:cabin.map(c=>c.cabin_class),
      datasets:[{data:cabin.map(c=>c.bookings),backgroundColor:cColors,
        borderColor:'#07090F',borderWidth:3,hoverOffset:6}]},
    options:{...baseOpts,cutout:'65%',
      plugins:{...baseOpts.plugins,legend:{display:true,position:'bottom',
        labels:{color:'#7880A0',font:{size:10},padding:12}}}}
  });

  // Airlines horizontal bar
  const alNames=airlines.slice(0,10).map(a=>a.airline_name.replace(' Airways','').replace(' Airlines',''));
  const alRevs=airlines.slice(0,10).map(a=>Number(a.revenue||0));
  mkChart('chart_airlines',{type:'bar',
    data:{labels:alNames,
      datasets:[{label:'Revenue',data:alRevs,
        backgroundColor:alNames.map((_,i)=>i===0?GOLD:'rgba(200,169,110,0.3)'),
        borderRadius:4}]},
    options:{...baseOpts,indexAxis:'y',
      scales:{x:{grid:GRID,ticks:{...TICK,callback:v=>'$'+Math.round(v/1000)+'k'}},
        y:{grid:{display:false},ticks:TICK}}}
  });

  // Status doughnut
  const stColors={Confirmed:GREEN,Completed:BLUE,Cancelled:RED,Pending:AMBER};
  mkChart('chart_status',{type:'doughnut',
    data:{labels:status.map(s=>s.booking_status),
      datasets:[{data:status.map(s=>s.count),
        backgroundColor:status.map(s=>stColors[s.booking_status]||PURPLE),
        borderColor:'#07090F',borderWidth:3,hoverOffset:6}]},
    options:{...baseOpts,cutout:'65%',
      plugins:{...baseOpts.plugins,legend:{display:true,position:'bottom',
        labels:{color:'#7880A0',font:{size:10},padding:12}}}}
  });

  // Nationalities bar
  mkChart('chart_national',{type:'bar',
    data:{labels:national.map(n=>n.nationality),
      datasets:[{label:'Bookings',data:national.map(n=>n.bookings),
        backgroundColor:national.map((_,i)=>i===0?PURPLE:'rgba(167,139,250,0.3)'),
        borderRadius:4}]},
    options:{...baseOpts,
      scales:{x:{grid:{display:false},ticks:{...TICK,maxRotation:30}},
        y:{grid:GRID,ticks:TICK}}}
  });

  // Top routes table
  let rtH='<table class="rt"><thead><tr><th>Route</th><th>Bookings</th><th>Avg Fare</th><th>Revenue</th></tr></thead><tbody>';
  routes.forEach(r=>{rtH+=`<tr>
    <td><span class="tag tag-gold">${r.origin_iata}</span> → <span class="tag tag-gold">${r.dest_iata}</span>
      <div style="font-size:9px;color:var(--muted);margin-top:1px">${r.origin} → ${r.destination}</div></td>
    <td style="color:var(--green);font-weight:700">${r.bookings}</td>
    <td>$${Number(r.avg_fare).toFixed(0)}</td>
    <td style="color:var(--gold)">$${Number(r.revenue).toLocaleString('en',{maximumFractionDigits:0})}</td>
  </tr>`;});
  document.getElementById('admin_routes').innerHTML=rtH+'</tbody></table>';

  // Zero routes
  if(!zero.length){
    document.getElementById('admin_zero').innerHTML='<div style="color:var(--green);font-size:13px">All routes have at least one booking</div>';
  } else {
    let zH='<table class="rt"><thead><tr><th>Flight</th><th>Airline</th><th>Route</th></tr></thead><tbody>';
    zero.forEach(r=>{zH+=`<tr>
      <td style="font-weight:700;color:var(--gold)">${r.flight_number}</td>
      <td>${r.airline_name}</td>
      <td><span class="tag tag-red">${r.origin}</span> → <span class="tag tag-red">${r.destination}</span></td>
    </tr>`;});
    document.getElementById('admin_zero').innerHTML=zH+'</tbody></table>';
  }
}

init();
</script>
</body>
</html>
"""

if __name__ == "__main__":
    print(f"\n  SkyRoute → http://localhost:5000")
    print(f"  Admin password: {ADMIN_PASSWORD}\n")
    app.run(debug=True, port=5000)