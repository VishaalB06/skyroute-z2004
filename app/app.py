"""
SkyRoute — Flight Search & Admin Dashboard
Z2004 DBMS | Final Submission | AlaguVishaalBalaji | ZDA24B036
Run: python app.py
"""

from flask import Flask, jsonify, request, render_template_string
import psycopg2, psycopg2.extras

app = Flask(__name__)

DB_CONFIG = {
    "host": "localhost", "database": "skyroute",
    "user": "postgres", "password": "postgres123", "port": 5432
}

ADMIN_PASSWORD = "skyroute2026"

def get_conn():
    return psycopg2.connect(**DB_CONFIG)

def fmt_time(t):
    """Return HH:MM from a time object or string like '11:00:00'."""
    s = str(t)
    parts = s.split(":")
    return f"{parts[0]}:{parts[1]}" if len(parts) >= 2 else s

# ── API ROUTES ────────────────────────────────────────────────

@app.route("/api/cities")
def api_cities():
    conn = get_conn(); cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("SELECT city_id, city_name, country, iata_code FROM city ORDER BY city_name")
    rows = [dict(r) for r in cur.fetchall()]
    cur.close(); conn.close()
    return jsonify(rows)

@app.route("/api/search")
def api_search():
    """
    Search flights by origin and destination.
    Returns direct flights first, then 1-stop connecting flights if no direct exists.
    Prices are summed across legs for connecting flights.
    """
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
                SELECT
                    f.flight_id, f.flight_number,
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
                    COUNT(DISTINCT b.booking_id) AS total_bookings
                FROM flight f
                JOIN airline a      ON f.airline_id          = a.airline_id
                JOIN city    oc     ON f.origin_city_id      = oc.city_id
                JOIN city    dc     ON f.destination_city_id = dc.city_id
                JOIN flight_price fp ON fp.flight_id         = f.flight_id
                LEFT JOIN booking b ON b.flight_id           = f.flight_id
                                   AND b.booking_status <> 'Cancelled'
                WHERE oc.city_id = %s AND dc.city_id = %s
                {cabin_filter}
                GROUP BY f.flight_id, f.flight_number, a.airline_name, a.iata_code,
                         oc.city_name, oc.iata_code, dc.city_name, dc.iata_code,
                         f.departure_time, f.arrival_time, f.duration_minutes, f.aircraft_type
                ORDER BY total_bookings DESC, min_price ASC
            """, params)
            return cur.fetchall()

        # 1. Try direct flights
        direct = flight_query(origin, dest, cabin)

        def row_to_dict(r, stop_label=None):
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
                "total_bookings":  r["total_bookings"],
                "is_direct":       True,
                "stop_via":        None,
            }

        results = [row_to_dict(r) for r in direct]

        # 2. If no direct flights, find 1-stop connections
        if not results:
            # Find all cities that have a flight FROM origin AND a flight TO destination
            cur.execute("""
                SELECT DISTINCT c.city_id, c.city_name, c.iata_code
                FROM city c
                WHERE EXISTS (
                    SELECT 1 FROM flight f1
                    JOIN flight_price fp1 ON fp1.flight_id = f1.flight_id
                    WHERE f1.origin_city_id = %s AND f1.destination_city_id = c.city_id
                )
                AND EXISTS (
                    SELECT 1 FROM flight f2
                    JOIN flight_price fp2 ON fp2.flight_id = f2.flight_id
                    WHERE f2.origin_city_id = c.city_id AND f2.destination_city_id = %s
                )
                AND c.city_id <> %s AND c.city_id <> %s
            """, [origin, dest, origin, dest])
            via_cities = cur.fetchall()

            for via in via_cities:
                leg1 = flight_query(origin, via["city_id"], cabin)
                leg2 = flight_query(via["city_id"], dest, cabin)
                if not leg1 or not leg2:
                    continue
                # Pick best combo (cheapest leg1 + cheapest leg2)
                best_l1 = sorted(leg1, key=lambda r: float(r["min_price"] or 9999))[0]
                best_l2 = sorted(leg2, key=lambda r: float(r["min_price"] or 9999))[0]

                eco  = (float(best_l1["eco_price"] or 0) + float(best_l2["eco_price"] or 0)) or None
                bus  = (float(best_l1["bus_price"] or 0) + float(best_l2["bus_price"] or 0)) or None
                fst  = (float(best_l1["fst_price"] or 0) + float(best_l2["fst_price"] or 0)) or None
                # Apply cabin filter: only include if selected cabin is available on both legs
                if cabin == "Economy"  and not (best_l1["has_economy"]  and best_l2["has_economy"]):  continue
                if cabin == "Business" and not (best_l1["has_business"] and best_l2["has_business"]): continue
                if cabin == "First"    and not (best_l1["has_first"]    and best_l2["has_first"]):    continue

                results.append({
                    "flight_id":       f"{best_l1['flight_id']}-{best_l2['flight_id']}",
                    "flight_number":   f"{best_l1['flight_number']} + {best_l2['flight_number']}",
                    "airline":         f"{best_l1['airline_name']} / {best_l2['airline_name']}",
                    "airline_code":    f"{best_l1['airline_code']}+{best_l2['airline_code']}",
                    "origin":          best_l1["origin"],
                    "origin_iata":     best_l1["origin_iata"],
                    "destination":     best_l2["destination"],
                    "dest_iata":       best_l2["dest_iata"],
                    "departure_time":  fmt_time(best_l1["departure_time"]),
                    "arrival_time":    fmt_time(best_l2["arrival_time"]),
                    "duration_minutes":int(best_l1["duration_minutes"]) + int(best_l2["duration_minutes"]),
                    "aircraft_type":   f"{best_l1['aircraft_type'] or ''} / {best_l2['aircraft_type'] or ''}".strip(" /"),
                    "min_price":       float(best_l1["min_price"] or 0) + float(best_l2["min_price"] or 0),
                    "has_economy":     bool(best_l1["has_economy"])  and bool(best_l2["has_economy"]),
                    "has_business":    bool(best_l1["has_business"]) and bool(best_l2["has_business"]),
                    "has_first":       bool(best_l1["has_first"])    and bool(best_l2["has_first"]),
                    "eco_price":       eco,
                    "bus_price":       bus,
                    "fst_price":       fst,
                    "total_bookings":  int(best_l1["total_bookings"]) + int(best_l2["total_bookings"]),
                    "is_direct":       False,
                    "stop_via":        f"{via['city_name']} ({via['iata_code']})",
                })

            # Sort connecting by price
            results.sort(key=lambda r: r["min_price"] or 9999)

        cur.close(); conn.close()
        return jsonify({"flights": results, "count": len(results)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/admin/auth", methods=["POST"])
def api_admin_auth():
    data = request.get_json()
    if data and data.get("password") == ADMIN_PASSWORD:
        return jsonify({"ok": True})
    return jsonify({"ok": False}), 401

@app.route("/api/admin/top_routes")
def api_top_routes():
    conn = get_conn(); cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT oc.city_name AS origin, dc.city_name AS destination,
               oc.iata_code AS origin_iata, dc.iata_code AS dest_iata,
               COUNT(b.booking_id) AS bookings,
               ROUND(SUM(b.total_paid)::numeric,2) AS revenue,
               ROUND(AVG(b.total_paid)::numeric,2) AS avg_fare
        FROM booking b
        JOIN flight f  ON b.flight_id=f.flight_id
        JOIN city oc   ON f.origin_city_id=oc.city_id
        JOIN city dc   ON f.destination_city_id=dc.city_id
        WHERE b.booking_status <> 'Cancelled'
        GROUP BY oc.city_name,dc.city_name,oc.iata_code,dc.iata_code
        ORDER BY bookings DESC LIMIT 10
    """)
    rows = [dict(r) for r in cur.fetchall()]
    cur.close(); conn.close()
    return jsonify(rows)

@app.route("/api/admin/airlines")
def api_admin_airlines():
    conn = get_conn(); cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT a.airline_name, a.iata_code, a.hub_city,
               COUNT(b.booking_id) AS bookings,
               ROUND(SUM(b.total_paid)::numeric,2) AS revenue,
               ROUND(AVG(b.total_paid)::numeric,2) AS avg_fare,
               COUNT(DISTINCT f.flight_id) AS routes
        FROM airline a
        LEFT JOIN flight f  ON f.airline_id=a.airline_id
        LEFT JOIN booking b ON b.flight_id=f.flight_id AND b.booking_status<>'Cancelled'
        GROUP BY a.airline_id,a.airline_name,a.iata_code,a.hub_city
        ORDER BY bookings DESC NULLS LAST
    """)
    rows = [dict(r) for r in cur.fetchall()]
    cur.close(); conn.close()
    return jsonify(rows)

@app.route("/api/admin/monthly")
def api_admin_monthly():
    conn = get_conn(); cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT TO_CHAR(DATE_TRUNC('month',booking_date),'Mon YYYY') AS month,
               DATE_TRUNC('month',booking_date) AS month_date,
               COUNT(*) AS bookings,
               ROUND(SUM(total_paid)::numeric,2) AS revenue
        FROM booking WHERE booking_status <> 'Cancelled'
        GROUP BY DATE_TRUNC('month',booking_date)
        ORDER BY month_date
    """)
    rows = [dict(r) for r in cur.fetchall()]
    for r in rows: r["month_date"] = str(r["month_date"])
    cur.close(); conn.close()
    return jsonify(rows)

@app.route("/api/admin/zero_routes")
def api_zero_routes():
    conn = get_conn(); cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute("""
        SELECT f.flight_number,a.airline_name,oc.city_name AS origin,dc.city_name AS destination
        FROM flight f
        JOIN airline a ON f.airline_id=a.airline_id
        JOIN city oc   ON f.origin_city_id=oc.city_id
        JOIN city dc   ON f.destination_city_id=dc.city_id
        WHERE NOT EXISTS (SELECT 1 FROM booking b WHERE b.flight_id=f.flight_id)
        ORDER BY a.airline_name
    """)
    rows = [dict(r) for r in cur.fetchall()]
    cur.close(); conn.close()
    return jsonify(rows)

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
    row = dict(cur.fetchone())
    cur.close(); conn.close()
    return jsonify(row)

@app.route("/")
def index():
    return render_template_string(UI)

UI = r"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<title>SkyRoute</title>
<style>
:root{
  --maroon:#7B1535;--maroon-d:#3D0A1A;--maroon-l:#A01D44;
  --gold:#C8A96E;--gold-l:#E8C98E;
  --bg:#07090F;--bg2:#0C1018;--bg3:#11161F;
  --glass:rgba(255,255,255,0.04);--gb:rgba(200,169,110,0.12);
  --txt:#E4E6F0;--muted:#7880A0;
  --green:#00E5A0;--red:#FF4D6A;--blue:#4DA6FF;--amber:#FFB347;
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
  animation:gpulse 8s ease-in-out infinite;}
@keyframes gpulse{0%,100%{opacity:.5}50%{opacity:1}}

/* HEADER */
header{position:sticky;top:0;z-index:100;height:60px;
  background:rgba(7,9,15,.88);backdrop-filter:blur(24px);
  border-bottom:1px solid var(--gb);
  display:flex;align-items:center;justify-content:space-between;padding:0 32px;}
.logo{display:flex;align-items:center;gap:10px;cursor:pointer;}
.logo-mark{width:32px;height:32px;border-radius:7px;
  background:linear-gradient(135deg,var(--maroon),var(--gold));
  display:flex;align-items:center;justify-content:center;font-size:16px;}
.logo-name{font-size:18px;font-weight:800;letter-spacing:.5px;
  background:linear-gradient(90deg,#fff,var(--gold));
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;}
.mode-toggle{display:flex;background:var(--glass);border:1px solid var(--gb);
  border-radius:8px;overflow:hidden;}
.mode-btn{padding:7px 18px;border:none;background:none;cursor:pointer;
  font-size:12px;font-weight:600;color:var(--muted);transition:all .2s;letter-spacing:.5px;text-transform:uppercase;}
.mode-btn.active{background:linear-gradient(135deg,var(--maroon),var(--maroon-l));color:#fff;}
.hdr-right{display:flex;align-items:center;gap:8px;font-size:12px;color:var(--muted);}
.dot{width:7px;height:7px;background:var(--green);border-radius:50%;
  box-shadow:0 0 6px var(--green);animation:blink 2s infinite;}
@keyframes blink{0%,100%{opacity:1}50%{opacity:.2}}

main{position:relative;z-index:1;max-width:1060px;margin:0 auto;padding:32px 20px;}
.panel{display:none;animation:fadeIn .25s ease;}
.panel.active{display:block;}
@keyframes fadeIn{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:none}}

/* ── PASSENGER ── */
.search-hero{text-align:center;padding:36px 0 28px;}
.search-hero h1{font-size:42px;font-weight:800;line-height:1.1;margin-bottom:10px;
  background:linear-gradient(135deg,#fff 20%,var(--gold));
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;}
.search-hero p{font-size:14px;color:var(--muted);}
.search-card{background:var(--glass);border:1px solid var(--gb);border-radius:16px;
  padding:24px;backdrop-filter:blur(16px);}
.search-grid{display:grid;grid-template-columns:1fr auto 1fr auto auto;gap:12px;align-items:end;}
.field{display:flex;flex-direction:column;gap:5px;}
.field label{font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:1px;font-weight:600;}
select,input[type=text],input[type=password],input[type=number]{
  background:rgba(255,255,255,.05);border:1px solid rgba(255,255,255,.09);
  border-radius:8px;padding:10px 13px;color:var(--txt);font-size:13px;outline:none;
  transition:border-color .2s;width:100%;}
select:focus,input:focus{border-color:var(--gold);}
select option{background:#0C1018;}
.swap-btn{background:var(--glass);border:1px solid var(--gb);border-radius:8px;
  padding:10px 14px;cursor:pointer;color:var(--gold);font-size:18px;
  align-self:flex-end;transition:all .2s;line-height:1;}
.swap-btn:hover{background:rgba(200,169,110,.1);transform:scale(1.1);}

.btn{padding:10px 22px;border-radius:8px;border:none;font-size:13px;
  font-weight:700;cursor:pointer;transition:all .2s;letter-spacing:.3px;}
.btn-primary{background:linear-gradient(135deg,var(--maroon),var(--maroon-l));
  color:#fff;box-shadow:0 4px 18px rgba(123,21,53,.4);}
.btn-primary:hover{transform:translateY(-1px);box-shadow:0 6px 24px rgba(123,21,53,.6);}
.btn-ghost{background:var(--glass);border:1px solid var(--gb);color:var(--muted);}
.btn-ghost:hover{color:var(--gold);border-color:var(--gold);}
.btn-gold{background:linear-gradient(135deg,var(--gold),var(--gold-l));color:#1a0900;font-weight:800;}

/* RESULT HEADER */
.result-header{display:flex;align-items:center;justify-content:space-between;margin:24px 0 14px;}
.result-title{font-size:13px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:1px;}
.result-count{font-size:11px;color:var(--muted);background:var(--glass);
  border:1px solid var(--gb);border-radius:12px;padding:2px 10px;}
.sort-row{display:flex;gap:6px;align-items:center;}
.sort-btn{padding:4px 12px;border-radius:6px;border:1px solid var(--gb);
  background:none;color:var(--muted);font-size:11px;cursor:pointer;transition:all .2s;}
.sort-btn.active{background:rgba(200,169,110,.08);color:var(--gold);border-color:var(--gold);}

/* FLIGHT CARD */
.flight-result{background:var(--glass);border:1px solid var(--gb);border-radius:14px;
  margin-bottom:12px;overflow:hidden;transition:all .25s;}
.flight-result:hover{border-color:rgba(200,169,110,.4);box-shadow:0 8px 32px rgba(0,0,0,.5);}
.fr-top-badges{display:flex;gap:6px;padding:10px 16px 0;min-height:26px;}
.hot-badge{background:rgba(0,229,160,.1);border:1px solid rgba(0,229,160,.25);
  color:var(--green);font-size:9px;font-weight:700;padding:2px 8px;border-radius:10px;
  text-transform:uppercase;letter-spacing:.5px;display:inline-flex;align-items:center;gap:3px;}
.connect-badge{background:rgba(77,166,255,.1);border:1px solid rgba(77,166,255,.25);
  color:var(--blue);font-size:9px;font-weight:700;padding:2px 8px;border-radius:10px;
  text-transform:uppercase;letter-spacing:.5px;display:inline-flex;align-items:center;gap:3px;}
.fr-main{display:grid;grid-template-columns:110px 1fr 80px 160px;align-items:center;}
.fr-airline{padding:14px 16px;border-right:1px solid var(--gb);text-align:center;}
.airline-code-big{font-size:20px;font-weight:900;color:var(--gold);letter-spacing:-0.5px;}
.airline-name-sm{font-size:9px;color:var(--muted);margin-top:2px;line-height:1.3;}
.fn-sm{font-size:9px;color:rgba(200,169,110,.5);margin-top:3px;}
.fr-route{padding:14px 20px;display:flex;align-items:center;gap:0;}
.fr-city{text-align:center;min-width:70px;}
.fr-iata{font-size:26px;font-weight:900;letter-spacing:-1px;}
.fr-name{font-size:9px;color:var(--muted);margin-top:1px;}
.fr-time{font-size:11px;color:rgba(200,169,110,.7);margin-top:3px;font-weight:600;}
.fr-mid{flex:1;display:flex;flex-direction:column;align-items:center;padding:0 12px;gap:3px;}
.fr-line{display:flex;align-items:center;width:100%;gap:4px;}
.fl{flex:1;height:1px;background:linear-gradient(90deg,transparent,var(--gold),transparent);}
.pl{font-size:12px;}
.fr-dur{font-size:10px;color:var(--muted);}
.fr-via{font-size:9px;color:var(--blue);margin-top:1px;}
.fr-aircraft{font-size:9px;color:rgba(200,169,110,.4);margin-top:1px;}
.fr-pop{padding:14px 10px;border-left:1px solid var(--gb);text-align:center;}
.pop-num{font-size:18px;font-weight:800;color:var(--green);}
.pop-label{font-size:8px;color:var(--muted);text-transform:uppercase;letter-spacing:1px;margin-top:1px;}
.fr-prices{padding:14px 16px;border-left:1px solid var(--gb);}
.price-row{display:flex;justify-content:space-between;align-items:center;
  padding:3px 0;border-bottom:1px solid rgba(255,255,255,.04);}
.price-row:last-child{border-bottom:none;}
.price-cabin{font-size:9px;font-weight:700;letter-spacing:.5px;}
.price-eco{color:var(--green);}
.price-bus{color:var(--blue);}
.price-fst{color:var(--gold);}
.price-val{font-size:12px;font-weight:700;}

.no-results{text-align:center;padding:56px 20px;color:var(--muted);}
.no-results .icon{font-size:48px;opacity:.3;margin-bottom:12px;}
.no-results h3{font-size:16px;margin-bottom:6px;color:var(--txt);}

/* ── ADMIN LOCK SCREEN ── */
.lock-screen{position:fixed;inset:0;z-index:200;background:rgba(7,9,15,.97);
  backdrop-filter:blur(20px);display:flex;align-items:center;justify-content:center;}
.lock-card{background:var(--glass);border:1px solid var(--gb);border-radius:20px;
  padding:40px;width:360px;text-align:center;}
.lock-icon{font-size:36px;margin-bottom:16px;}
.lock-title{font-size:20px;font-weight:800;margin-bottom:6px;}
.lock-sub{font-size:13px;color:var(--muted);margin-bottom:24px;}
.lock-input{margin-bottom:12px;}
.lock-error{color:var(--red);font-size:12px;margin-top:8px;min-height:18px;}

/* ── ADMIN PANEL ── */
.admin-grid-4{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:20px;}
.kpi{background:var(--glass);border:1px solid var(--gb);border-radius:12px;padding:18px;}
.kpi-val{font-size:26px;font-weight:800;}
.kpi-label{font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:1px;margin-top:4px;}
.kpi-gold .kpi-val{color:var(--gold);}
.kpi-green .kpi-val{color:var(--green);}
.kpi-blue .kpi-val{color:var(--blue);}
.kpi-amber .kpi-val{color:var(--amber);}
.admin-row{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:16px;}
.admin-full{margin-bottom:16px;}
.card{background:var(--glass);border:1px solid var(--gb);border-radius:14px;padding:20px;}
.card-title{font-size:11px;font-weight:700;color:var(--muted);text-transform:uppercase;
  letter-spacing:1px;margin-bottom:16px;}
.bar-row{display:flex;align-items:center;gap:10px;margin-bottom:8px;}
.bar-label{font-size:11px;color:var(--txt);min-width:130px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.bar-track{flex:1;height:6px;background:rgba(255,255,255,.06);border-radius:3px;overflow:hidden;}
.bar-fill{height:100%;border-radius:3px;background:linear-gradient(90deg,var(--maroon),var(--gold));}
.bar-val{font-size:11px;color:var(--muted);min-width:60px;text-align:right;}
.rt{width:100%;border-collapse:collapse;font-size:12px;}
.rt th{color:var(--muted);font-size:10px;text-transform:uppercase;letter-spacing:1px;
  padding:6px 10px;border-bottom:1px solid var(--gb);text-align:left;font-weight:600;}
.rt td{padding:9px 10px;border-bottom:1px solid rgba(255,255,255,.03);}
.rt tr:hover td{background:rgba(255,255,255,.02);}
.tag{display:inline-block;padding:2px 7px;border-radius:4px;font-size:10px;font-weight:700;}
.tag-gold{background:rgba(200,169,110,.1);color:var(--gold);border:1px solid rgba(200,169,110,.2);}
.tag-red{background:rgba(255,77,106,.1);color:var(--red);border:1px solid rgba(255,77,106,.2);}
.month-chart{display:flex;align-items:flex-end;gap:6px;height:100px;margin-top:8px;}
.month-bar-wrap{flex:1;display:flex;flex-direction:column;align-items:center;gap:4px;}
.month-bar{width:100%;border-radius:3px 3px 0 0;background:linear-gradient(0deg,var(--maroon),var(--gold));min-height:4px;}
.month-label{font-size:9px;color:var(--muted);}
.loader{text-align:center;padding:48px;color:var(--muted);}
.spin{width:28px;height:28px;border:2px solid var(--gb);border-top-color:var(--gold);
  border-radius:50%;animation:spin .7s linear infinite;margin:0 auto 10px;}
@keyframes spin{to{transform:rotate(360deg)}}
::-webkit-scrollbar{width:5px;}
::-webkit-scrollbar-track{background:var(--bg);}
::-webkit-scrollbar-thumb{background:var(--gb);border-radius:3px;}
</style>
</head>
<body>
<div class="glow"></div>

<!-- ADMIN LOCK SCREEN -->
<div class="lock-screen" id="lock_screen" style="display:none">
  <div class="lock-card">
    <div class="lock-icon">🔒</div>
    <div class="lock-title">Admin Access</div>
    <div class="lock-sub">Enter the admin password to continue</div>
    <div class="lock-input">
      <input type="password" id="lock_pw" placeholder="Password" onkeydown="if(event.key==='Enter')tryLogin()"/>
    </div>
    <button class="btn btn-primary" style="width:100%" onclick="tryLogin()">Unlock Dashboard</button>
    <div class="lock-error" id="lock_err"></div>
    <button class="btn btn-ghost" style="width:100%;margin-top:10px" onclick="cancelAdmin()">Cancel</button>
  </div>
</div>

<header>
  <div class="logo" onclick="setMode('passenger')">
    <div class="logo-mark">✈</div>
    <div class="logo-name">SKYROUTE</div>
  </div>
  <div class="mode-toggle">
    <button class="mode-btn active" id="btn-passenger" onclick="setMode('passenger')">✈ Passenger</button>
    <button class="mode-btn" id="btn-admin" onclick="requestAdmin()">⚙ Admin</button>
  </div>
  <div class="hdr-right"><div class="dot"></div><span>skyroute · PostgreSQL 18.4</span></div>
</header>

<main>
<!-- PASSENGER -->
<div class="panel active" id="panel-passenger">
  <div class="search-hero">
    <h1>Where do you want to fly?</h1>
    <p>Search flights across 27 cities and 16 airlines · connecting flights included · ranked by popularity and price</p>
  </div>
  <div class="search-card">
    <div class="search-grid">
      <div class="field"><label>From</label>
        <select id="s_origin"><option value="">Select origin city...</option></select></div>
      <button class="swap-btn" onclick="swapCities()" title="Swap cities">⇄</button>
      <div class="field"><label>To</label>
        <select id="s_dest"><option value="">Select destination city...</option></select></div>
      <div class="field"><label>Cabin class</label>
        <select id="s_cabin">
          <option value="">Any cabin</option>
          <option value="Economy">Economy</option>
          <option value="Business">Business</option>
          <option value="First">First Class</option>
        </select></div>
      <button class="btn btn-primary" style="padding:10px 28px" onclick="doSearch()">Search Flights</button>
    </div>
  </div>
  <div id="search_result"></div>
</div>

<!-- ADMIN -->
<div class="panel" id="panel-admin">
  <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:24px">
    <div>
      <div style="font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:1px;margin-bottom:4px">Admin Dashboard</div>
      <div style="font-size:26px;font-weight:800">Operations Overview</div>
    </div>
    <button class="btn btn-ghost" onclick="lockAdmin()">🔒 Lock</button>
  </div>
  <div class="admin-grid-4" id="admin_kpis"><div class="loader"><div class="spin"></div></div></div>
  <div class="admin-row">
    <div class="card"><div class="card-title">🔥 Top Routes by Bookings</div><div id="admin_routes"><div class="loader"><div class="spin"></div></div></div></div>
    <div class="card"><div class="card-title">✈ Revenue by Airline</div><div id="admin_airlines"><div class="loader"><div class="spin"></div></div></div></div>
  </div>
  <div class="admin-full card"><div class="card-title">📈 Monthly Bookings Trend</div><div id="admin_monthly"></div></div>
  <div class="admin-full card">
    <div class="card-title">⚠ Routes with Zero Bookings <span style="font-size:10px;color:var(--red);margin-left:6px">(Expansion Opportunities)</span></div>
    <div id="admin_zero"></div>
  </div>
</div>
</main>

<script>
let cities = [], sortKey = 'popular', lastResults = [], adminUnlocked = false;

async function init() {
  const res = await fetch('/api/cities');
  cities = await res.json();
  ['s_origin','s_dest'].forEach((id,i) => {
    const sel = document.getElementById(id);
    sel.innerHTML = `<option value="">${i===0?'Select origin...':'Select destination...'}</option>`
      + cities.map(c=>`<option value="${c.city_id}">${c.city_name} (${c.iata_code}) — ${c.country}</option>`).join('');
  });
}

function setMode(mode) {
  document.getElementById('panel-passenger').classList.toggle('active', mode==='passenger');
  document.getElementById('panel-admin').classList.toggle('active', mode==='admin');
  document.getElementById('btn-passenger').classList.toggle('active', mode==='passenger');
  document.getElementById('btn-admin').classList.toggle('active', mode==='admin');
}

function requestAdmin() {
  if (adminUnlocked) { setMode('admin'); return; }
  document.getElementById('lock_screen').style.display = 'flex';
  document.getElementById('lock_pw').value = '';
  document.getElementById('lock_err').textContent = '';
  setTimeout(() => document.getElementById('lock_pw').focus(), 100);
}

async function tryLogin() {
  const pw = document.getElementById('lock_pw').value;
  const res = await fetch('/api/admin/auth', {
    method: 'POST', headers: {'Content-Type':'application/json'},
    body: JSON.stringify({password: pw})
  });
  if (res.ok) {
    adminUnlocked = true;
    document.getElementById('lock_screen').style.display = 'none';
    setMode('admin');
    loadAdmin();
  } else {
    document.getElementById('lock_err').textContent = 'Incorrect password. Try again.';
    document.getElementById('lock_pw').value = '';
    document.getElementById('lock_pw').focus();
  }
}

function cancelAdmin() {
  document.getElementById('lock_screen').style.display = 'none';
}

function lockAdmin() {
  adminUnlocked = false;
  setMode('passenger');
}

function swapCities() {
  const o = document.getElementById('s_origin'), d = document.getElementById('s_dest');
  const tmp = o.value; o.value = d.value; d.value = tmp;
  if (lastResults.length) doSearch();
}

async function doSearch() {
  const origin = document.getElementById('s_origin').value;
  const dest   = document.getElementById('s_dest').value;
  const cabin  = document.getElementById('s_cabin').value;
  if (!origin || !dest) { alert('Please select both an origin and a destination.'); return; }
  if (origin === dest)  { alert('Origin and destination cannot be the same city.'); return; }
  document.getElementById('search_result').innerHTML =
    `<div class="loader" style="margin-top:32px"><div class="spin"></div>Searching flights...</div>`;
  const res  = await fetch(`/api/search?origin=${origin}&dest=${dest}${cabin?'&cabin='+cabin:''}`);
  const data = await res.json();
  if (data.error) {
    document.getElementById('search_result').innerHTML =
      `<div class="no-results"><div class="icon">⚠</div><h3>${data.error}</h3></div>`; return;
  }
  lastResults = data.flights || [];
  sortKey = 'popular';
  renderResults();
}

function setSort(key) {
  sortKey = key;
  document.querySelectorAll('.sort-btn').forEach(b => b.classList.toggle('active', b.dataset.sort===key));
  renderResults();
}

function renderResults() {
  const div = document.getElementById('search_result');
  if (!lastResults.length) {
    div.innerHTML = `<div class="no-results"><div class="icon">🔍</div>
      <h3>No flights found on this route</h3><p>Try a different origin or destination</p></div>`; return;
  }
  let flights = [...lastResults];
  if (sortKey==='price')    flights.sort((a,b)=>(a.min_price||999999)-(b.min_price||999999));
  if (sortKey==='popular')  flights.sort((a,b)=>b.total_bookings-a.total_bookings);
  if (sortKey==='duration') flights.sort((a,b)=>a.duration_minutes-b.duration_minutes);
  const maxPop = Math.max(...flights.map(f=>f.total_bookings));
  const directs    = flights.filter(f=>f.is_direct).length;
  const connecting = flights.filter(f=>!f.is_direct).length;
  let label = `${flights[0].origin} → ${flights[0].destination}`;
  let sub = '';
  if (directs && connecting) sub = `${directs} direct · ${connecting} via 1 stop`;
  else if (directs)          sub = `${directs} direct flight${directs>1?'s':''}`;
  else                       sub = `No direct flights · showing ${connecting} connecting route${connecting>1?'s':''}`;

  let html = `<div class="result-header">
    <div>
      <div class="result-title">${label}</div>
      <div style="font-size:11px;color:var(--muted);margin-top:3px">${sub}</div>
    </div>
    <div style="display:flex;align-items:center;gap:12px">
      <div class="result-count">${flights.length} result${flights.length>1?'s':''}</div>
      <div class="sort-row">
        <span style="font-size:11px;color:var(--muted)">Sort:</span>
        <button class="sort-btn ${sortKey==='popular'?'active':''}" data-sort="popular" onclick="setSort('popular')">Popular</button>
        <button class="sort-btn ${sortKey==='price'?'active':''}" data-sort="price" onclick="setSort('price')">Cheapest</button>
        <button class="sort-btn ${sortKey==='duration'?'active':''}" data-sort="duration" onclick="setSort('duration')">Shortest</button>
      </div>
    </div>
  </div>`;

  flights.forEach(f => {
    const isHot  = f.is_direct && f.total_bookings === maxPop && maxPop > 0;
    const hrs  = Math.floor(f.duration_minutes/60);
    const mins = f.duration_minutes % 60;
    const dur  = hrs>0 ? `${hrs}h ${mins}m` : `${mins}m`;
    const totalDur = f.is_direct ? dur : `${dur} total`;

    html += `<div class="flight-result">
      <div class="fr-top-badges">
        ${isHot ? '<span class="hot-badge">⚡ Most Booked</span>' : ''}
        ${!f.is_direct ? `<span class="connect-badge">🔗 1 Stop via ${f.stop_via}</span>` : ''}
      </div>
      <div class="fr-main">
        <div class="fr-airline">
          <div class="airline-code-big">${f.airline_code}</div>
          <div class="airline-name-sm">${f.airline}</div>
          <div class="fn-sm">${f.flight_number}</div>
        </div>
        <div class="fr-route">
          <div class="fr-city">
            <div class="fr-iata">${f.origin_iata}</div>
            <div class="fr-name">${f.origin}</div>
            <div class="fr-time">${f.departure_time}</div>
          </div>
          <div class="fr-mid">
            <div class="fr-line"><div class="fl"></div><div class="pl">✈</div><div class="fl"></div></div>
            <div class="fr-dur">${totalDur}</div>
            ${f.stop_via ? `<div class="fr-via">via ${f.stop_via}</div>` : ''}
            ${f.aircraft_type ? `<div class="fr-aircraft">${f.aircraft_type}</div>` : ''}
          </div>
          <div class="fr-city" style="text-align:right">
            <div class="fr-iata">${f.dest_iata}</div>
            <div class="fr-name">${f.destination}</div>
            <div class="fr-time">${f.arrival_time}</div>
          </div>
        </div>
        <div class="fr-pop">
          <div class="pop-num">${f.total_bookings}</div>
          <div class="pop-label">Bookings</div>
        </div>
        <div class="fr-prices">
          ${f.has_economy  && f.eco_price ? `<div class="price-row"><span class="price-cabin price-eco">Economy</span><span class="price-val">$${Math.round(f.eco_price).toLocaleString()}</span></div>` : ''}
          ${f.has_business && f.bus_price ? `<div class="price-row"><span class="price-cabin price-bus">Business</span><span class="price-val">$${Math.round(f.bus_price).toLocaleString()}</span></div>` : ''}
          ${f.has_first    && f.fst_price ? `<div class="price-row"><span class="price-cabin price-fst">First</span><span class="price-val">$${Math.round(f.fst_price).toLocaleString()}</span></div>` : ''}
        </div>
      </div>
    </div>`;
  });
  div.innerHTML = html;
}

async function loadAdmin() {
  const [summary,routes,airlines,monthly,zero] = await Promise.all([
    fetch('/api/admin/summary').then(r=>r.json()),
    fetch('/api/admin/top_routes').then(r=>r.json()),
    fetch('/api/admin/airlines').then(r=>r.json()),
    fetch('/api/admin/monthly').then(r=>r.json()),
    fetch('/api/admin/zero_routes').then(r=>r.json()),
  ]);
  document.getElementById('admin_kpis').innerHTML = `
    <div class="kpi kpi-gold"><div class="kpi-val">${Number(summary.total_bookings).toLocaleString()}</div><div class="kpi-label">Total Bookings</div></div>
    <div class="kpi kpi-green"><div class="kpi-val">$${Number(summary.total_revenue).toLocaleString('en',{maximumFractionDigits:0})}</div><div class="kpi-label">Total Revenue</div></div>
    <div class="kpi kpi-blue"><div class="kpi-val">${summary.total_users}</div><div class="kpi-label">Registered Users</div></div>
    <div class="kpi kpi-amber"><div class="kpi-val">${summary.total_flights}</div><div class="kpi-label">Active Routes</div></div>`;
  let rtHtml = `<table class="rt"><thead><tr><th>Route</th><th>Bookings</th><th>Avg Fare</th><th>Revenue</th></tr></thead><tbody>`;
  routes.forEach(r=>{
    rtHtml+=`<tr>
      <td><span class="tag tag-gold">${r.origin_iata}</span> → <span class="tag tag-gold">${r.dest_iata}</span>
        <div style="font-size:9px;color:var(--muted);margin-top:1px">${r.origin} → ${r.destination}</div></td>
      <td style="color:var(--green);font-weight:700">${r.bookings}</td>
      <td>$${Number(r.avg_fare).toFixed(0)}</td>
      <td style="color:var(--gold)">$${Number(r.revenue).toLocaleString('en',{maximumFractionDigits:0})}</td>
    </tr>`;
  });
  document.getElementById('admin_routes').innerHTML = rtHtml+'</tbody></table>';
  const maxRev = Math.max(...airlines.map(a=>Number(a.revenue)||0));
  let alHtml='';
  airlines.slice(0,10).forEach(a=>{
    const pct = maxRev>0?Math.round((Number(a.revenue||0)/maxRev)*100):0;
    alHtml+=`<div class="bar-row">
      <div class="bar-label" title="${a.airline_name}">${a.airline_name}</div>
      <div class="bar-track"><div class="bar-fill" style="width:${pct}%"></div></div>
      <div class="bar-val">$${Number(a.revenue||0).toLocaleString('en',{maximumFractionDigits:0})}</div>
    </div>`;
  });
  document.getElementById('admin_airlines').innerHTML = alHtml;
  const maxBk = Math.max(...monthly.map(m=>m.bookings));
  let mHtml='<div class="month-chart">';
  monthly.forEach(m=>{
    const h=Math.round((m.bookings/maxBk)*100);
    mHtml+=`<div class="month-bar-wrap">
      <div class="month-bar" style="height:${h}px" title="${m.bookings} bookings"></div>
      <div class="month-label">${m.month.split(' ')[0]}</div>
    </div>`;
  });
  document.getElementById('admin_monthly').innerHTML = mHtml+'</div>';
  if (!zero.length) {
    document.getElementById('admin_zero').innerHTML=`<div style="color:var(--green);font-size:13px">✓ All routes have at least one booking</div>`;
  } else {
    let zHtml=`<table class="rt"><thead><tr><th>Flight</th><th>Airline</th><th>Route</th></tr></thead><tbody>`;
    zero.forEach(r=>{
      zHtml+=`<tr>
        <td style="font-weight:700;color:var(--gold)">${r.flight_number}</td>
        <td>${r.airline_name}</td>
        <td><span class="tag tag-red">${r.origin}</span> → <span class="tag tag-red">${r.destination}</span></td>
      </tr>`;
    });
    document.getElementById('admin_zero').innerHTML=zHtml+'</tbody></table>';
  }
}

init();
</script>
</body>
</html>
"""

if __name__ == "__main__":
    print("\n  SkyRoute → http://localhost:5000")
    print(f"  Admin password: {ADMIN_PASSWORD}\n")
    app.run(debug=True, port=5000)
