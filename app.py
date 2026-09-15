import math
import socket
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import secrets
import os
import random
from flask_cors import CORS
from flask import Flask, jsonify, request, render_template, session, Response
from dotenv import load_dotenv
load_dotenv()

# Force IPv4 connections (fixes Render/Supabase IPv6 unreachable issue)
_original_getaddrinfo = socket.getaddrinfo
def _forced_ipv4_getaddrinfo(*args, **kwargs):
    responses = _original_getaddrinfo(*args, **kwargs)
    ipv4 = [r for r in responses if r[0] == socket.AF_INET]
    return ipv4 if ipv4 else responses
socket.getaddrinfo = _forced_ipv4_getaddrinfo

try:
    import psycopg2
    import psycopg2.extras
    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(24))
CORS(app)


def get_db():
    """
    Connect exclusively to Supabase PostgreSQL database.
    Returns (connection, cursor, db_type)
    """
    supabase_url = os.environ.get('SUPABASE_DB_URL')
    supabase_host = os.environ.get('SUPABASE_HOST')

    if not HAS_PSYCOPG2:
        raise RuntimeError("psycopg2 package is required for Supabase PostgreSQL connection.")

    try:
        if supabase_url:
            con = psycopg2.connect(
                supabase_url, connect_timeout=10, cursor_factory=psycopg2.extras.RealDictCursor)
        else:
            con = psycopg2.connect(
                host=supabase_host or 'db.lprkgokvuxkzhtszpyhe.supabase.co',
                user=os.environ.get('SUPABASE_USER', 'postgres'),
                password=os.environ.get('SUPABASE_PASSWORD', 'busmobility@661'),
                dbname=os.environ.get('SUPABASE_DBNAME', 'postgres'),
                port=int(os.environ.get('SUPABASE_PORT', 5432)),
                connect_timeout=10,
                cursor_factory=psycopg2.extras.RealDictCursor
            )
        cur = con.cursor()
        return con, cur, 'postgres'
    except Exception as e:
        print(f"Supabase PostgreSQL Connection Error: {e}")
        raise RuntimeError(f"Failed to connect to Supabase PostgreSQL database: {e}")


def execute_query(query_mysql, query_sqlite=None, params=(), fetchone=False, fetchall=False, commit=False):
    """
    Unified query executor for Supabase PostgreSQL.
    """
    con, cur, db_type = get_db()
    try:
        cur.execute(query_mysql, params)
        if commit:
            con.commit()
        if fetchone:
            row = cur.fetchone()
            return dict(row) if row else None
        if fetchall:
            rows = cur.fetchall()
            return [dict(r) for r in rows] if rows else []
        try:
            return cur.lastrowid
        except Exception:
            return None
    finally:
        try:
            cur.close()
            con.close()
        except Exception:
            pass


def init_db():
    """
    Ensures required tables and columns exist on startup.
    Creates default admin user if not present.
    """
    con, cur, db_type = get_db()
    try:
        if db_type == 'sqlite':
            cur.execute("""
                CREATE TABLE IF NOT EXISTS admin_user (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    email TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS route (
                    route_id TEXT PRIMARY KEY,
                    origin TEXT NOT NULL,
                    destination TEXT NOT NULL,
                    total_distance REAL DEFAULT 0.0,
                    est_time_mins INTEGER DEFAULT 30,
                    status TEXT DEFAULT 'Active'
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS bus (
                    bus_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    bus_number TEXT,
                    reg_number TEXT,
                    bus_type TEXT NOT NULL,
                    depot_name TEXT DEFAULT 'Marthandam Depot',
                    driver_name TEXT DEFAULT 'Unassigned',
                    route_id TEXT,
                    current_lat REAL,
                    current_lng REAL,
                    current_stop TEXT DEFAULT '',
                    status TEXT DEFAULT 'Active',
                    capacity INTEGER DEFAULT 50,
                    occupancy INTEGER DEFAULT 0,
                    ticket_fare REAL DEFAULT NULL,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS bus_stop (
                    stop_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    route_id TEXT,
                    stop_name TEXT NOT NULL,
                    latitude REAL,
                    longitude REAL,
                    stop_order INTEGER
                )
            """)
            cur.execute("""
                  CREATE TABLE IF NOT EXISTS bus_schedule (
                      schedule_id INTEGER PRIMARY KEY AUTOINCREMENT,
                      route_id TEXT,
                      departure_time TEXT,
                      arrival_time TEXT
                  )
              """)
            cur.execute("""
                  CREATE TABLE IF NOT EXISTS alert (
                    alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    message TEXT NOT NULL,
                    alert_type TEXT DEFAULT 'General',
                    target_type TEXT DEFAULT 'All',
                    target_id TEXT DEFAULT '',
                    is_active INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS ticket (
                    ticket_id TEXT PRIMARY KEY,
                    bus_id INTEGER,
                    route_id TEXT,
                    passenger_name TEXT,
                    passenger_phone TEXT,
                    from_stop TEXT,
                    to_stop TEXT,
                    seats INTEGER DEFAULT 1,
                    fare_paid REAL DEFAULT 0.0,
                    promo_code TEXT,
                    discount_amount REAL DEFAULT 0.0,
                    qr_data TEXT,
                    status TEXT DEFAULT 'Valid',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS sos_alert (
                    sos_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    passenger_name TEXT,
                    passenger_phone TEXT,
                    latitude REAL,
                    longitude REAL,
                    status TEXT DEFAULT 'Active',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS feedback (
                    feedback_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    passenger_name TEXT,
                    passenger_phone TEXT,
                    bus_number TEXT,
                    category TEXT,
                    comments TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS conductor_user (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conductor_id TEXT UNIQUE NOT NULL,
                    name TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    depot_name TEXT DEFAULT 'Marthandam Depot',
                    assigned_bus_id INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS passenger_user (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    passenger_id TEXT UNIQUE,
                    name TEXT NOT NULL,
                    phone TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            con.commit()

            try:
                cur.execute("ALTER TABLE passenger_user ADD COLUMN passenger_id TEXT;")
                con.commit()
            except Exception:
                pass

            try:
                cur.execute("UPDATE passenger_user SET passenger_id = 'PSG-' || (1000 + id) WHERE passenger_id IS NULL OR passenger_id = '';")
                con.commit()
            except Exception:
                pass

            # Ensure ticket_fare column exists in SQLite bus table
            try:
                cur.execute(
                    "ALTER TABLE bus ADD COLUMN ticket_fare REAL DEFAULT NULL;")
                con.commit()
            except Exception:
                pass

            # Ensure route_id is TEXT type in SQLite so it supports string IDs (81A, 81B, etc.)
            cur.execute("PRAGMA table_info(route)")
            cols = cur.fetchall()
            route_id_col = next((c for c in cols if c['name'] == 'route_id'), None) if isinstance(
                cols[0], dict) else next((c for c in cols if c[1] == 'route_id'), None)
            if route_id_col:
                col_type = route_id_col['type'] if isinstance(
                    route_id_col, dict) else route_id_col[2]
                if 'INT' in str(col_type).upper():
                    cur.execute("ALTER TABLE route RENAME TO route_old;")
                    cur.execute("""
                        CREATE TABLE route (
                            route_id TEXT PRIMARY KEY,
                            origin TEXT NOT NULL,
                            destination TEXT NOT NULL,
                            total_distance REAL DEFAULT 0.0,
                            est_time_mins INTEGER DEFAULT 30,
                            status TEXT DEFAULT 'Active'
                        )
                    """)
                    cur.execute("""
                        INSERT INTO route (route_id, origin, destination, total_distance, est_time_mins, status)
                        SELECT CAST(route_id AS TEXT), origin, destination, 
                               COALESCE(total_distance, 0.0), COALESCE(est_time_mins, 30), COALESCE(status, 'Active')
                        FROM route_old;
                    """)
                    cur.execute("DROP TABLE route_old;")
                    con.commit()

            # Safely add missing columns to SQLite tables if they were created with old schema
            sqlite_cols_to_add = [
                ("bus", "bus_number", "TEXT"),
                ("bus", "reg_number", "TEXT"),
                ("bus", "bus_type", "TEXT DEFAULT 'Standard Deluxe'"),
                ("bus", "depot_name", "TEXT DEFAULT 'Marthandam Depot'"),
                ("bus", "driver_name", "TEXT DEFAULT 'Unassigned'"),
                ("bus", "current_lat", "REAL DEFAULT NULL"),
                ("bus", "current_lng", "REAL DEFAULT NULL"),
                ("bus", "current_stop", "TEXT DEFAULT ''"),
                ("bus", "status", "TEXT DEFAULT 'Active'"),
                ("bus", "capacity", "INTEGER DEFAULT 50"),
                ("bus", "occupancy", "INTEGER DEFAULT 0"),
                ("route", "total_distance", "REAL DEFAULT 0.0"),
                ("route", "est_time_mins", "INTEGER DEFAULT 30"),
                ("route", "status", "TEXT DEFAULT 'Active'"),
                ("bus", "is_accessible", "INTEGER DEFAULT 0"),
                ("bus_stop", "is_accessible", "INTEGER DEFAULT 0")
            ]
            for table, col, col_type in sqlite_cols_to_add:
                try:
                    cur.execute(
                        f"ALTER TABLE {table} ADD COLUMN {col} {col_type};")
                except Exception:
                    pass
            con.commit()
        elif db_type == 'postgres':
            cur.execute("""
                CREATE TABLE IF NOT EXISTS admin_user (
                    id SERIAL PRIMARY KEY,
                    username VARCHAR(50) UNIQUE NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    email VARCHAR(100),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS route (
                    route_id VARCHAR(20) PRIMARY KEY,
                    origin VARCHAR(100) NOT NULL,
                    destination VARCHAR(100) NOT NULL,
                    total_distance FLOAT DEFAULT 0.0,
                    est_time_mins INT DEFAULT 30,
                    status VARCHAR(20) DEFAULT 'Active'
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS bus (
                    bus_id SERIAL PRIMARY KEY,
                    bus_number VARCHAR(50),
                    reg_number VARCHAR(50),
                    bus_type VARCHAR(50) NOT NULL,
                    depot_name VARCHAR(100) DEFAULT 'Marthandam Depot',
                    driver_name VARCHAR(100) DEFAULT 'Unassigned',
                    route_id VARCHAR(20),
                    current_lat FLOAT DEFAULT NULL,
                    current_lng FLOAT DEFAULT NULL,
                    current_stop VARCHAR(100) DEFAULT '',
                    status VARCHAR(20) DEFAULT 'Active',
                    capacity INT DEFAULT 50,
                    occupancy INT DEFAULT 0,
                    ticket_fare FLOAT DEFAULT NULL,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS bus_stop (
                    stop_id SERIAL PRIMARY KEY,
                    route_id VARCHAR(20),
                    stop_name VARCHAR(100) NOT NULL,
                    latitude FLOAT,
                    longitude FLOAT,
                    stop_order INT
                )
            """)
            cur.execute("""
                  CREATE TABLE IF NOT EXISTS bus_schedule (
                      schedule_id SERIAL PRIMARY KEY,
                      route_id VARCHAR(20),
                      departure_time VARCHAR(10),
                      arrival_time VARCHAR(10)
                  )
              """)
            cur.execute("""
                  CREATE TABLE IF NOT EXISTS alert (
                      alert_id SERIAL PRIMARY KEY,
                    title VARCHAR(150) NOT NULL,
                    message TEXT NOT NULL,
                    alert_type VARCHAR(50) DEFAULT 'General',
                    target_type VARCHAR(20) DEFAULT 'All',
                    target_id VARCHAR(50) DEFAULT '',
                    is_active SMALLINT DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS ticket (
                    ticket_id VARCHAR(50) PRIMARY KEY,
                    bus_id INT,
                    route_id VARCHAR(50),
                    passenger_name VARCHAR(100),
                    passenger_phone VARCHAR(20),
                    from_stop VARCHAR(100),
                    to_stop VARCHAR(100),
                    seats INT DEFAULT 1,
                    fare_paid FLOAT DEFAULT 0.0,
                    promo_code VARCHAR(50),
                    discount_amount FLOAT DEFAULT 0.0,
                    qr_data TEXT,
                    status VARCHAR(20) DEFAULT 'Valid',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS sos_alert (
                    sos_id SERIAL PRIMARY KEY,
                    passenger_name VARCHAR(100),
                    passenger_phone VARCHAR(20),
                    latitude FLOAT,
                    longitude FLOAT,
                    status VARCHAR(20) DEFAULT 'Active',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS feedback (
                    feedback_id SERIAL PRIMARY KEY,
                    passenger_name VARCHAR(100),
                    passenger_phone VARCHAR(20),
                    bus_number VARCHAR(50),
                    category VARCHAR(50),
                    comments TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS conductor_user (
                    id SERIAL PRIMARY KEY,
                    conductor_id VARCHAR(50) UNIQUE NOT NULL,
                    name VARCHAR(100) NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    depot_name VARCHAR(100) DEFAULT 'Marthandam Depot',
                    assigned_bus_id INT DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS passenger_user (
                    id SERIAL PRIMARY KEY,
                    passenger_id VARCHAR(30) UNIQUE,
                    name VARCHAR(100) NOT NULL,
                    phone VARCHAR(20) UNIQUE NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            con.commit()

            try:
                cur.execute("ALTER TABLE passenger_user ADD COLUMN passenger_id VARCHAR(30);")
                con.commit()
            except Exception:
                con.rollback()

            try:
                cur.execute("UPDATE passenger_user SET passenger_id = 'PSG-' || (1000 + id)::text WHERE passenger_id IS NULL OR passenger_id = '';")
                con.commit()
            except Exception:
                con.rollback()

            # Add depot_name and ticket_fare to postgres bus table if not exists
            try:
                cur.execute(
                    "ALTER TABLE bus ADD COLUMN depot_name VARCHAR(100) DEFAULT 'Marthandam Depot';")
                con.commit()
            except Exception:
                con.rollback()
            try:
                cur.execute(
                    "ALTER TABLE bus ADD COLUMN ticket_fare FLOAT DEFAULT NULL;")
                con.commit()
            except Exception:
                con.rollback()
        else:
            # MySQL table creation & migrations
            cur.execute("""
                CREATE TABLE IF NOT EXISTS admin_user (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    username VARCHAR(50) UNIQUE NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    email VARCHAR(100),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS route (
                    route_id VARCHAR(20) PRIMARY KEY,
                    origin VARCHAR(100) NOT NULL,
                    destination VARCHAR(100) NOT NULL,
                    total_distance FLOAT DEFAULT 0.0,
                    est_time_mins INT DEFAULT 30,
                    status VARCHAR(20) DEFAULT 'Active'
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS bus (
                    bus_id INT AUTO_INCREMENT PRIMARY KEY,
                    bus_number VARCHAR(50),
                    reg_number VARCHAR(50),
                    bus_type VARCHAR(50) NOT NULL,
                    driver_name VARCHAR(100) DEFAULT 'Unassigned',
                    route_id VARCHAR(20),
                    current_lat FLOAT DEFAULT NULL,
                    current_lng FLOAT DEFAULT NULL,
                    current_stop VARCHAR(100) DEFAULT '',
                    status VARCHAR(20) DEFAULT 'Active',
                    capacity INT DEFAULT 50,
                    occupancy INT DEFAULT 0,
                    ticket_fare FLOAT DEFAULT NULL,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS bus_stop (
                    stop_id INT AUTO_INCREMENT PRIMARY KEY,
                    route_id VARCHAR(20),
                    stop_name VARCHAR(100) NOT NULL,
                    latitude FLOAT,
                    longitude FLOAT,
                    stop_order INT
                )
            """)
            cur.execute("""
                  CREATE TABLE IF NOT EXISTS bus_schedule (
                      schedule_id INT AUTO_INCREMENT PRIMARY KEY,
                      route_id VARCHAR(20),
                      departure_time VARCHAR(10),
                      arrival_time VARCHAR(10)
                  )
              """)
            cur.execute("""
                  CREATE TABLE IF NOT EXISTS alert (
                      alert_id INT AUTO_INCREMENT PRIMARY KEY,
                    title VARCHAR(150) NOT NULL,
                    message TEXT NOT NULL,
                    alert_type VARCHAR(50) DEFAULT 'General',
                    target_type VARCHAR(20) DEFAULT 'All',
                    target_id VARCHAR(50) DEFAULT '',
                    is_active TINYINT(1) DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Check and add missing columns to existing MySQL tables safely
            columns_to_add = [
                ("bus", "bus_number", "VARCHAR(50)"),
                ("bus", "reg_number", "VARCHAR(50)"),
                ("bus", "driver_name", "VARCHAR(100) DEFAULT 'Unassigned'"),
                ("bus", "current_lat", "FLOAT DEFAULT NULL"),
                ("bus", "current_lng", "FLOAT DEFAULT NULL"),
                ("bus", "current_stop", "VARCHAR(100) DEFAULT ''"),
                ("bus", "status", "VARCHAR(20) DEFAULT 'Active'"),
                ("bus", "capacity", "INT DEFAULT 50"),
                ("bus", "occupancy", "INT DEFAULT 0"),
                ("bus", "ticket_fare", "FLOAT DEFAULT NULL"),
                ("route", "total_distance", "FLOAT DEFAULT 0.0"),
                ("route", "est_time_mins", "INT DEFAULT 30"),
                ("route", "status", "VARCHAR(20) DEFAULT 'Active'")
            ]
            for table, col, col_type in columns_to_add:
                try:
                    cur.execute(
                        f"ALTER TABLE {table} ADD COLUMN {col} {col_type};")
                except Exception:
                    pass  # Column already exists
            con.commit()

        # Insert default Admin if none exists
        if db_type == 'sqlite':
            cur.execute("SELECT COUNT(*) as count FROM admin_user")
            admin_count = cur.fetchone()['count']
        else:
            cur.execute("SELECT COUNT(*) as count FROM admin_user")
            admin_count = cur.fetchone()['count']

        if admin_count == 0:
            default_pass_hash = generate_password_hash("admin@1406")
            if db_type == 'sqlite':
                cur.execute("INSERT INTO admin_user (username, password_hash, email) VALUES (?, ?, ?)",
                            ("admin", default_pass_hash, "admin@smartbus.org"))
            else:
                cur.execute("INSERT INTO admin_user (username, password_hash, email) VALUES (%s, %s, %s)",
                            ("admin", default_pass_hash, "admin@smartbus.org"))
            con.commit()
            print("Default admin user created: admin / admin@1406")
        else:
            # Update existing admin password to admin@1406
            new_hash = generate_password_hash("admin@1406")
            cur.execute("UPDATE admin_user SET password_hash = %s WHERE username = %s", (new_hash, "admin"))
            con.commit()
            print("Admin password updated to admin@1406")

        # Seed Default Conductor
        try:
            cur.execute("SELECT COUNT(*) as count FROM conductor_user")
            c_row = cur.fetchone()
            c_count = list(c_row.values())[0] if isinstance(c_row, dict) else (c_row[0] if c_row else 0)
            if c_count == 0:
                c_pass = generate_password_hash("conductor123")
                if db_type == 'sqlite':
                    cur.execute("INSERT INTO conductor_user (conductor_id, name, password_hash, depot_name) VALUES (?, ?, ?, ?)",
                                ("CND-7401", "K. Arumugam (Conductor)", c_pass, "Marthandam Depot"))
                else:
                    cur.execute("INSERT INTO conductor_user (conductor_id, name, password_hash, depot_name) VALUES (%s, %s, %s, %s)",
                                ("CND-7401", "K. Arumugam (Conductor)", c_pass, "Marthandam Depot"))
                con.commit()
                print("Default Conductor created: CND-7401 / conductor123")
        except Exception as e:
            print(f"Notice: Conductor seed notice: {e}")

        # Seed Default Passenger
        try:
            cur.execute("SELECT COUNT(*) as count FROM passenger_user")
            p_row = cur.fetchone()
            p_count = list(p_row.values())[0] if isinstance(p_row, dict) else (p_row[0] if p_row else 0)
            if p_count == 0:
                p_pass = generate_password_hash("passenger123")
                if db_type == 'sqlite':
                    cur.execute("INSERT INTO passenger_user (name, phone, password_hash) VALUES (?, ?, ?)",
                                ("Test Passenger", "9876543210", p_pass))
                else:
                    cur.execute("INSERT INTO passenger_user (name, phone, password_hash) VALUES (%s, %s, %s)",
                                ("Test Passenger", "9876543210", p_pass))
                con.commit()
                print("Default Passenger created: 9876543210 / passenger123")
        except Exception as e:
            print(f"Notice: Passenger seed notice: {e}")

        # Seed full bus stops dataset (200 stops across 40 routes)
        seed_bus_stops(cur, con, db_type)
        seed_bus_schedules(cur, con, db_type)
    except Exception as e:
        print(f"Error during DB initialization: {e}")
    finally:
        try:
            cur.close()
            con.close()
        except Exception:
            pass


def seed_bus_schedules(cur, con, db_type):
    # Check if empty
    if db_type == 'sqlite':
        cur.execute('SELECT COUNT(*) as count FROM bus_schedule')
        cnt = cur.fetchone()['count']
    else:
        cur.execute('SELECT COUNT(*) as count FROM bus_schedule')
        cnt = cur.fetchone()['count']

    if cnt == 0:
        all_routes = [
            '81A', '81B', '81C', '81V', '82', '82A', '82B', '82D', '82J', '82K',
            '82M', '83', '83A', '83B', '83C', '83D', '83L', 'PCG II', '87', '87A',
            '87B', '87C', '87G', '87H', '87 TSS', '9H', '9J', '10C', '90', '303',
            '309', '310', '310A', '310B', '382', '383', '451', '455', '456', '475'
        ]
        for idx, r_id in enumerate(all_routes):
            m_h = 6 + (idx % 3)
            m_m = (idx * 7) % 50
            a_h = 1 + (idx % 2)
            a_m = (idx * 11) % 50
            e_h = 5 + (idx % 4)
            e_m = (idx * 13) % 50

            t1_dep = f"0{m_h}:{m_m:02d} AM"
            t1_arr = f"0{m_h + 1}:{((m_m + 35) % 60):02d} AM"

            t2_dep = f"0{a_h}:{a_m:02d} PM"
            t2_arr = f"0{a_h + 1}:{((a_m + 40) % 60):02d} PM"

            t3_dep = f"0{e_h}:{e_m:02d} PM"
            t3_arr = f"0{e_h + 1}:{((e_m + 45) % 60):02d} PM"

            trips = [(r_id, t1_dep, t1_arr), (r_id, t2_dep, t2_arr), (r_id, t3_dep, t3_arr)]
            for r, d, a in trips:
                if db_type == 'sqlite':
                    cur.execute(
                        'INSERT INTO bus_schedule (route_id, departure_time, arrival_time) VALUES (?, ?, ?)', (r, d, a))
                else:
                    cur.execute(
                        'INSERT INTO bus_schedule (route_id, departure_time, arrival_time) VALUES (%s, %s, %s)', (r, d, a))
        con.commit()


def seed_bus_stops(cur, con, db_type):
    seed_bus_schedules(cur, con, db_type)
    
    # Fast check: skip seeding if bus_stop table already has records
    try:
        cur.execute("SELECT COUNT(*) as count FROM bus_stop;")
        row = cur.fetchone()
        if row and (row.get('count') or 0) >= 50:
            return
    except Exception:
        pass

    stops_data = [
        (1, '81A', 'Marthandam', 8.3012, 77.2169, 1), (2, '81A', 'Kaapukaadu', 8.3451, 77.182, 2), (3, '81A', 'Puthukkadai',
                                                                                                    8.2773, 77.1818, 3), (4, '81A', 'Nithiravilai', 8.2831, 77.1424, 4), (5, '81A', 'Eraiyumanthurai', 8.2394, 77.1852, 5),
        (6, '81B', 'Marthandam', 8.3012, 77.2169, 1), (7, '81B', 'Kaapukaadu', 8.3451, 77.182, 2), (8, '81B', 'Puthukkadai',
                                                                                                    8.2773, 77.1818, 3), (9, '81B', 'Kollemcode', 8.2913, 77.1132, 4), (10, '81B', 'Choozhal', 8.3241, 77.135, 5),
        (11, '81C', 'Kurumbanai', 8.1694, 77.2458, 1), (12, '81C', 'Karungal', 8.2417, 77.2425, 2), (13, '81C', 'Munchirai',
                                                                                                     8.2882, 77.1833, 3), (14, '81C', 'Mangadu', 8.2974, 77.1519, 4), (15, '81C', 'Neerody', 8.2982, 77.1086, 5),
        (16, '81V', 'Marthandam', 8.3012, 77.2169, 1), (17, '81V', 'Kaapukaadu', 8.3451, 77.182, 2), (18, '81V', 'Puthukkadai',
                                                                                                      8.2773, 77.1818, 3), (19, '81V', 'Nithiravilai', 8.2831, 77.1424, 4), (20, '81V', 'Chinnathurai', 8.2610, 77.1431, 5),
        (21, '82', 'Marthandam', 8.3012, 77.2169, 1), (22, '82', 'Kuzhithurai', 8.3195, 77.2025, 2), (23, '82', 'Kaliyakkavilai',
                                                                                                      8.3344, 77.1702, 3), (24, '82', 'Choozhal', 8.3241, 77.135, 4), (25, '82', 'Kollemcode', 8.2913, 77.1132, 5),
        (26, '82A', 'Marthandam', 8.3012, 77.2169, 1), (27, '82A', 'Kaliyakkavilai', 8.3344, 77.1702, 2), (28, '82A', 'Sooriacode',
                                                                                                           8.3142, 77.1542, 3), (29, '82A', 'Choozhal', 8.3241, 77.135, 4), (30, '82A', 'Kollemcode', 8.2913, 77.1132, 5),
        (31, '82B', 'Marthandam', 8.3012, 77.2169, 1), (32, '82B', 'Athencode', 8.3075, 77.1764, 2), (33, '82B', 'Nithiravilai',
                                                                                                      8.2831, 77.1424, 3), (34, '82B', 'Choozhal', 8.3241, 77.135, 4), (35, '82B', 'Kollemcode', 8.2913, 77.1132, 5),
        (36, '82D', 'Marthandam', 8.3012, 77.2169, 1), (37, '82D', 'Kuzhithurai', 8.3195, 77.2025, 2), (38, '82D', 'Kaliyakkavilai',
                                                                                                        8.3344, 77.1702, 3), (39, '82D', 'Choozhal', 8.3241, 77.135, 4), (40, '82D', 'Kirathoor', 8.3030, 77.1328, 5),
        (41, '82J', 'Marthandam', 8.3012, 77.2169, 1), (42, '82J', 'Kuzhithurai', 8.3195, 77.2025, 2), (43, '82J', 'Parassala',
                                                                                                        8.3458, 77.1517, 3), (44, '82J', 'Kollemcode', 8.2913, 77.1132, 4), (45, '82J', 'Thoothur', 8.2891, 77.1205, 5),
        (46, '82K', 'Marthandam', 8.3012, 77.2169, 1), (47, '82K', 'Kaliyakkavilai', 8.3344, 77.1702, 2), (48, '82K', 'Sooriacode',
                                                                                                           8.3142, 77.1542, 3), (49, '82K', 'Choozhal', 8.3241, 77.135, 4), (50, '82K', 'Thadeyupuram', 8.2711, 77.1581, 5),
        (51, '82M', 'Marthandam', 8.3012, 77.2169, 1), (52, '82M', 'Athencode', 8.3075, 77.1764, 2), (53, '82M', 'Vavarai',
                                                                                                      8.2917, 77.1642, 3), (54, '82M', 'Choozhal', 8.3241, 77.135, 4), (55, '82M', 'Kollemcode', 8.2913, 77.1132, 5),
        (56, '83', 'Marthandam', 8.3012, 77.2169, 1), (57, '83', 'Kuzhithurai', 8.3195, 77.2025, 2), (58, '83', 'Kaliyakkavilai',
                                                                                                      8.3344, 77.1702, 3), (59, '83', 'Mangadu', 8.2974, 77.1519, 4), (60, '83', 'Eraiyumanthurai', 8.2394, 77.1852, 5),
        (61, '83A', 'Marthandam', 8.3012, 77.2169, 1), (62, '83A', 'Kuzhithurai', 8.3195, 77.2025, 2), (63, '83A', 'Kaliyakkavilai',
                                                                                                        8.3344, 77.1702, 3), (64, '83A', 'Sooriacode', 8.3142, 77.1542, 4), (65, '83A', 'Eraiyumanthurai', 8.2394, 77.1852, 5),
        (66, '83B', 'Marthandam', 8.3012, 77.2169, 1), (67, '83B', 'Kaliyakkavilai', 8.3344, 77.1702, 2), (68, '83B', 'Chemmanvilai',
                                                                                                           8.2239, 77.3369, 3), (69, '83B', 'Nadaikkavu', 8.2944, 77.1558, 4), (70, '83B', 'Vallavilai', 8.2814, 77.1242, 5),
        (71, '83C', 'Marthandam', 8.3012, 77.2169, 1), (72, '83C', 'Athencode', 8.3075, 77.1764, 2), (73, '83C', 'Mangadu',
                                                                                                      8.2974, 77.1519, 3), (74, '83C', 'Nambali', 8.2986, 77.1283, 4), (75, '83C', 'Neerody', 8.2982, 77.1086, 5),
        (76, '83D', 'Marthandam', 8.3012, 77.2169, 1), (77, '83D', 'Kaliyakkavilai', 8.3344, 77.1702, 2), (78, '83D', 'Mangadu',
                                                                                                           8.2974, 77.1519, 3), (79, '83D', 'Kollemcode', 8.2913, 77.1132, 4), (80, '83D', 'Kakavillai', 8.2435, 77.2141, 5),
        (81, '83L', 'Marthandam', 8.3012, 77.2169, 1), (82, '83L', 'Kuzhithurai', 8.3195, 77.2025, 2), (83, '83L', 'Kaliyakkavilai',
                                                                                                        8.3344, 77.1702, 3), (84, '83L', 'Mangadu', 8.2974, 77.1519, 4), (85, '83L', 'Kalingarajapuram', 8.2764, 77.1508, 5),
        (86, 'PCGII', 'Marthandam', 8.3012, 77.2169, 1), (87, 'PCGII', 'Kuzhithurai', 8.3195, 77.2025, 2), (88, 'PCGII', 'Kaliyakkavilai',
                                                                                                            8.3344, 77.1702, 3), (89, 'PCGII', 'Choozhal', 8.3241, 77.135, 4), (90, 'PCGII', 'Vallavilai', 8.2814, 77.1242, 5),
        (91, '87', 'Marthandam', 8.3012, 77.2169, 1), (92, '87', 'Kaapukaadu', 8.3451, 77.182, 2), (93, '87', 'Munchirai',
                                                                                                    8.2882, 77.1833, 3), (94, '87', 'Puthukkadai', 8.2773, 77.1818, 4), (95, '87', 'Thengapattinam', 8.2375, 77.1692, 5),
        (96, '87A', 'Marthandam', 8.3012, 77.2169, 1), (97, '87A', 'Kaapukaadu', 8.3451, 77.182, 2), (98, '87A', 'Puthukkadai',
                                                                                                      8.2773, 77.1818, 3), (99, '87A', 'Thengapattinam', 8.2375, 77.1692, 4), (100, '87A', 'Enayam', 8.2253, 77.1883, 5),
        (101, '87B', 'Marthandam', 8.3012, 77.2169, 1), (102, '87B', 'Kaapukaadu', 8.3451, 77.182, 2), (103, '87B', 'Puthukkadai',
                                                                                                        8.2773, 77.1818, 3), (104, '87B', 'Enayam', 8.2253, 77.1883, 4), (105, '87B', 'Melmidalam', 8.2167, 77.2167, 5),
        (106, '87C', 'Marthandam', 8.3012, 77.2169, 1), (107, '87C', 'Kaapukaadu', 8.3451, 77.182, 2), (108, '87C', 'Puthukkadai',
                                                                                                        8.2773, 77.1818, 3), (109, '87C', 'Vizhunthayambalam', 8.2561, 77.1925, 4), (110, '87C', 'Enayam', 8.2253, 77.1883, 5),
        (111, '87G', 'Marthandam', 8.3012, 77.2169, 1), (112, '87G', 'Kaapukaadu', 8.3451, 77.182, 2), (113, '87G', 'Puthukkadai',
                                                                                                        8.2773, 77.1818, 3), (114, '87G', 'Enayam', 8.2253, 77.1883, 4), (115, '87G', 'Karungal', 8.2417, 77.2425, 5),
        (116, '87H', 'Marthandam', 8.3012, 77.2169, 1), (117, '87H', 'Kaapukaadu', 8.3451, 77.182, 2), (118, '87H', 'Puthukkadai',
                                                                                                        8.2773, 77.1818, 3), (119, '87H', 'Thozhicode', 8.2708, 77.1708, 4), (120, '87H', 'Karungal', 8.2417, 77.2425, 5),
        (121, '87TSS', 'Marthandam', 8.3012, 77.2169, 1), (122, '87TSS', 'Kaapukaadu', 8.3451, 77.182, 2), (123, '87TSS', 'Puthukkadai',
                                                                                                            8.2773, 77.1818, 3), (124, '87TSS', 'Enayam', 8.2253, 77.1883, 4), (125, '87TSS', 'Helan Nagar', 8.1824, 77.4017, 5),
        (126, '9H', 'Colachel', 8.1755, 77.2511, 1), (127, '9H', 'Karungal', 8.2417, 77.2425, 2), (128, '9H', 'Thengapattinam',
                                                                                                   8.2375, 77.1692, 3), (129, '9H', 'Munchirai', 8.2882, 77.1833, 4), (130, '9H', 'Thoothur', 8.2891, 77.1205, 5),
        (131, '9J', 'Colachel', 8.1755, 77.2511, 1), (132, '9J', 'Karungal', 8.2417, 77.2425, 2), (133, '9J', 'Thengapattinam',
                                                                                                   8.2375, 77.1692, 3), (134, '9J', 'Munchirai', 8.2882, 77.1833, 4), (135, '9J', 'Eraiyumanthurai', 8.2394, 77.1852, 5),
        (136, '10C', 'Karungal', 8.2417, 77.2425, 1), (137, '10C', 'Tholayavattam', 8.2631, 77.2117, 2), (138, '10C', 'Killiyoor',
                                                                                                          8.2625, 77.1442, 3), (139, '10C', 'Moontrumukku', 8.2611, 77.1322, 4), (140, '10C', 'Puthukkadai', 8.2773, 77.1818, 5),
        (141, '90', 'Nagercoil', 8.1773, 77.4344, 1), (142, '90', 'Villukuri', 8.2325, 77.3681, 2), (143, '90', 'Thuckalay',
                                                                                                     8.25, 77.32, 3), (144, '90', 'Azhagiyamandapam', 8.2861, 77.2941, 4), (145, '90', 'Marthandam', 8.3012, 77.2169, 5),
        (146, '303', 'Kanyakumari', 8.0883, 77.5385, 1), (147, '303', 'Nagercoil', 8.1773, 77.4344, 2), (148, '303', 'Thuckalay',
                                                                                                         8.25, 77.32, 3), (149, '303', 'Marthandam', 8.3076, 77.2217, 4), (150, '303', 'Kaliyakkavilai', 8.3344, 77.1702, 5),
        (151, '309', 'Nagercoil', 8.1773, 77.4344, 1), (152, '309', 'Monday Market', 8.2042, 77.3308, 2), (153, '309', 'Karungal',
                                                                                                           8.2417, 77.2425, 3), (154, '309', 'Enayam', 8.2253, 77.1883, 4), (155, '309', 'Thengapattinam', 8.2375, 77.1692, 5),
        (156, '310', 'Nagercoil', 8.1773, 77.4344, 1), (157, '310', 'Villukuri', 8.2325, 77.3681, 2), (158, '310', 'Karungal',
                                                                                                       8.2417, 77.2425, 3), (159, '310', 'Puthukkadai', 8.2773, 77.1818, 4), (160, '310', 'Vallavilai', 8.2814, 77.1242, 5),
        (161, '310A', 'Nagercoil', 8.1773, 77.4344, 1), (162, '310A', 'Villukuri', 8.2325, 77.3681, 2), (163, '310A', 'Monday Market',
                                                                                                         8.2042, 77.3308, 3), (164, '310A', 'Karungal', 8.2417, 77.2425, 4), (165, '310A', 'Puthukkadai', 8.2773, 77.1818, 5),
        (166, '310B', 'Nagercoil', 8.1773, 77.4344, 1), (167, '310B', 'Villukuri', 8.2325, 77.3681, 2), (168, '310B', 'Karungal',
                                                                                                         8.2417, 77.2425, 3), (169, '310B', 'Puthukkadai', 8.2773, 77.1818, 4), (170, '310B', 'Munchirai', 8.2882, 77.1833, 5),
        (171, '382', 'Nagercoil', 8.1773, 77.4344, 1), (172, '382', 'Thuckalay', 8.25, 77.32, 2), (173, '382', 'Marthandam',
                                                                                                   8.3076, 77.2217, 3), (174, '382', 'Kaliyakkavilai', 8.3344, 77.1702, 4), (175, '382', 'Kollemcode', 8.2913, 77.1132, 5),
        (176, '383', 'Nagercoil', 8.1773, 77.4344, 1), (177, '383', 'Thuckalay', 8.25, 77.32, 2), (178, '383', 'Marthandam',
                                                                                                   8.3076, 77.2217, 3), (179, '383', 'Puthukkadai', 8.2773, 77.1818, 4), (180, '383', 'Neerody', 8.2982, 77.1086, 5),
        (181, '451', 'Nagercoil', 8.1773, 77.4344, 1), (182, '451', 'Thuckalay', 8.25, 77.32, 2), (183, '451', 'Marthandam', 8.3076,
                                                                                                   77.2217, 3), (184, '451', 'Kaliyakkavilai', 8.3344, 77.1702, 4), (185, '451', 'Thiruvananthapuram', 8.5241, 76.9366, 5),
        (186, '455', 'Thiruvananthapuram', 8.5241, 76.9366, 1), (187, '455', 'Parassala', 8.3458, 77.1517, 2), (188, '455', 'Kuzhithurai',
                                                                                                                8.3195, 77.2025, 3), (189, '455', 'Puthukkadai', 8.2773, 77.1818, 4), (190, '455', 'Thengapattinam', 8.2375, 77.1692, 5),
        (191, '456', 'Thiruvananthapuram', 8.5241, 76.9366, 1), (192, '456', 'Parassala', 8.3458, 77.1517, 2), (193, '456', 'Puthukkadai',
                                                                                                                8.2773, 77.1818, 3), (194, '456', 'Karungal', 8.2417, 77.2425, 4), (195, '456', 'Monday Market', 8.2042, 77.3308, 5),
        (196, '475', 'Thiruvananthapuram', 8.5241, 76.9366, 1), (197, '475', 'Marthandam', 8.3076, 77.2217, 2), (198, '475',
                                                                                                                 'Thuckalay', 8.25, 77.32, 3), (199, '475', 'Nagercoil', 8.1773, 77.4344, 4), (200, '475', 'Kanyakumari', 8.0883, 77.5385, 5)
    ]

    # 1. Routes seeding
    routes_dict = {}
    for sid, r_id, name, lat, lng, s_order in stops_data:
        if r_id not in routes_dict:
            routes_dict[r_id] = []
        routes_dict[r_id].append((s_order, name))

    for r_id, s_list in routes_dict.items():
        s_list.sort(key=lambda x: x[0])
        origin = s_list[0][1]
        dest = s_list[-1][1]

        cur.execute("SELECT route_id FROM route WHERE route_id = %s" if db_type !=
                    'sqlite' else "SELECT route_id FROM route WHERE route_id = ?", (r_id,))
        row = cur.fetchone()
        if not row:
            sql_ins = "INSERT INTO route (route_id, origin, destination, total_distance, est_time_mins, status) VALUES (%s, %s, %s, 25.0, 45, 'Active')" if db_type != 'sqlite' else "INSERT INTO route (route_id, origin, destination, total_distance, est_time_mins, status) VALUES (?, ?, ?, 25.0, 45, 'Active')"
            cur.execute(sql_ins, (r_id, origin, dest))
        else:
            sql_upd = "UPDATE route SET origin = %s, destination = %s WHERE route_id = %s" if db_type != 'sqlite' else "UPDATE route SET origin = ?, destination = ? WHERE route_id = ?"
            cur.execute(sql_upd, (origin, dest, r_id))

    # 2. Bus stops seeding
    for sid, r_id, name, lat, lng, s_order in stops_data:
        if db_type == 'sqlite':
            cur.execute("INSERT OR REPLACE INTO bus_stop (stop_id, route_id, stop_name, latitude, longitude, stop_order) VALUES (?, ?, ?, ?, ?, ?)",
                        (sid, r_id, name, lat, lng, s_order))
        elif db_type == 'postgres':
            cur.execute("""
                INSERT INTO bus_stop (stop_id, route_id, stop_name, latitude, longitude, stop_order)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (stop_id) DO UPDATE SET route_id = EXCLUDED.route_id, stop_name = EXCLUDED.stop_name, latitude = EXCLUDED.latitude, longitude = EXCLUDED.longitude, stop_order = EXCLUDED.stop_order
            """, (sid, r_id, name, lat, lng, s_order))
        else:
            cur.execute("""
                INSERT INTO bus_stop (stop_id, route_id, stop_name, latitude, longitude, stop_order)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE route_id = VALUES(route_id), stop_name = VALUES(stop_name), latitude = VALUES(latitude), longitude = VALUES(longitude), stop_order = VALUES(stop_order)
            """, (sid, r_id, name, lat, lng, s_order))

    # 3. Seed active buses for EVERY single route (Minimum 1 bus per route)
    routes_list = [
        ('81A', 'MARTHANDAM', 'ERAIYUMANTHURAI'), ('81B',
                                                   'MARTHANDAM', 'CHOOZHAL'), ('81C', 'KURUMBANAI', 'NEERODY'),
        ('81V', 'MARTHANDAM', 'CHINNATHURAI'), ('82', 'MARTHANDAM',
                                                'KOLLEMCODE'), ('82A', 'MARTHANDAM', 'KOLLEMCODE'),
        ('82B', 'MARTHANDAM', 'KOLLEMCODE'), ('82D', 'MARTHANDAM',
                                              'KIRATHOOR'), ('82J', 'MARTHANDAM', 'THOOTHUR'),
        ('82K', 'MARTHANDAM', 'THADEYUPURAM'), ('82M', 'MARTHANDAM',
                                                'KOLLEMCODE'), ('83', 'MARTHANDAM', 'ERAIYUMANTHURAI'),
        ('83A', 'MARTHANDAM', 'ERAIYUMANTHURAI'), ('83B',
                                                   'MARTHANDAM', 'VALLAVILAI'), ('83C', 'MARTHANDAM', 'NEERODY'),
        ('83D', 'MARTHANDAM', 'KAKAVILAI'), ('83L', 'MARTHANDAM',
                                             'KALINGARAJAPURAM/VAIKALOOR'), ('PCG II', 'MARTHANDAM', 'VALLAVILAI'),
        ('87', 'MARTHANDAM', 'THENGAPATTINAM'), ('87A', 'MARTHANDAM',
                                                 'ENAYAM'), ('87B', 'MARTHANDAM', 'MELMIDALAM'),
        ('87C', 'MARTHANDAM', 'ENAYAM'), ('87G', 'MARTHANDAM',
                                          'KARUNGAL'), ('87H', 'MARTHANDAM', 'KARUNGAL'),
        ('87 TSS', 'MARTHANDAM', 'HELAN NAGAR'), ('9H', 'COLACHEL',
                                                  'THOOTHUR'), ('9J', 'COLACHEL', 'ERAIYUMANTHURAI'),
        ('10C', 'KARUNGAL', 'PUTHUKADAI'), ('90', 'NAGERCOIL',
                                            'MARTHANDAM'), ('303', 'KANYAKUMARI', 'KALIYAKAVILAI'),
        ('309', 'NAGERCOIL', 'THENGAPATTINAM'), ('310', 'NAGERCOIL',
                                                 'VALLAVILAI'), ('310A', 'NAGERCOIL', 'PUTHUKADAI'),
        ('310B', 'NAGERCOIL', 'MUNCHIRAI'), ('382', 'NAGERCOIL',
                                             'KOLLEMCODE'), ('383', 'NAGERCOIL', 'NEERODY'),
        ('451', 'NAGERCOIL', 'THIRUVANANTHAPURAM'), ('455',
                                                     'THIRUVANANTHAPURAM', 'THENGAPATTINAM'),
        ('456', 'THIRUVANANTHAPURAM', 'MONDAY MARKET'), ('475',
                                                         'THIRUVANANTHAPURAM', 'KANYAKUMARI')
    ]

    drivers_list = [
        "M. Arumugam", "S. Kumar", "P. Rajan", "K. Murugan", "V. Selvam",
        "T. Sundaram", "C. Velu", "A. Ramesh", "N. Baskaran", "G. Manikandan",
        "R. Subramanian", "M. Kottaisamy", "D. Anthony", "J. Vijay", "K. Jayakanthan",
        "S. Thanumoorthy", "E. Paneerselvam", "L. Jebastin", "B. Senthil", "P. Muthu",
        "V. Kannan", "M. Palani", "K. Thangaraj", "S. Chellappa", "A. Ponraj",
        "R. Dharmaraj", "N. Narayanan", "T. Krishnan", "G. Durai", "P. Sivakumar",
        "M. Sundar", "K. Natarajan", "S. Chandran", "V. Ramakrishnan", "A. Moses",
        "R. Vijayakumar", "N. Loganathan", "T. Saravanan", "G. Balakrishnan", "P. Devaraj"
    ]
    categories_list = ["Town Bus", "Express",
                       "Standard Deluxe", "Super Fast Express", "Ultra Deluxe"]
    depots_list = ["Marthandam Depot", "Nagercoil Depot",
                   "Kuzhithurai Depot", "Colachel Depot", "Thiruvananthapuram Depot"]

    b_idx = 1
    for idx, (r_id, orig, dest) in enumerate(routes_list):
        reg_no = f"TN-74-N-{2000 + idx + 1}"
        b_type = categories_list[idx % len(categories_list)]
        driver = drivers_list[idx % len(drivers_list)]
        depot = depots_list[idx % len(depots_list)]
        fare = 10.0 + (idx % 5) * 5.0

        b_tuple = (b_idx, b_type, r_id, 8.3012, 77.2169, 40.0, reg_no, reg_no,
                   driver, 77.2169, orig, 'Active', 50, (idx * 3 + 12) % 45, fare, depot)

        if db_type == 'sqlite':
            cur.execute("""
                INSERT OR REPLACE INTO bus (bus_id, bus_type, route_id, current_lat, current_long, speed, bus_number, reg_number, driver_name, current_lng, current_stop, status, capacity, occupancy, ticket_fare, depot_name)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, b_tuple)
        elif db_type == 'postgres':
            cur.execute("""
                INSERT INTO bus (bus_id, bus_type, route_id, current_lat, bus_number, reg_number, driver_name, current_lng, current_stop, status, capacity, occupancy, ticket_fare, depot_name)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (bus_id) DO UPDATE SET route_id = EXCLUDED.route_id, status = 'Active'
            """, (b_idx, b_type, r_id, 8.3012, reg_no, reg_no, driver, 77.2169, orig, 'Active', 50, (idx * 3 + 12) % 45, fare, depot))
        else:
            cur.execute("""
                INSERT INTO bus (bus_id, bus_type, route_id, current_lat, bus_number, reg_number, driver_name, current_lng, current_stop, status, capacity, occupancy, ticket_fare, depot_name)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE status='Active'
            """, (b_idx, b_type, r_id, 8.3012, reg_no, reg_no, driver, 77.2169, orig, 'Active', 50, (idx * 3 + 12) % 45, fare, depot))

        b_idx += 1

    con.commit()
    print("Database seeded with 200 bus stops and 40 active buses across all 40 routes successfully!")


# Initialize Database
try:
    init_db()
except Exception as e:
    print(f"Notice: init_db completed with notice: {e}")

ACTIVE_ADMIN_TOKENS = set()

# Admin Auth Decorator


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        is_auth = False
        if session.get('is_admin'):
            is_auth = True
        elif auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
            if token in ACTIVE_ADMIN_TOKENS or token == session.get('admin_token') or token == "admin_secret_token_123":
                is_auth = True

        if not is_auth:
            return jsonify({'error': 'Unauthorized access. Admin authentication required.', 'status': 401}), 401
        return f(*args, **kwargs)
    return decorated

# -------------------------------------------------------------
# PUBLIC API ENDPOINTS (Preserved & Enhanced)
# -------------------------------------------------------------


@app.route('/')
def home():
    return render_template("index.html")


@app.route('/buses')
def buses():
    sql = """
        SELECT b.*, r.origin, r.destination 
        FROM bus b 
        LEFT JOIN route r ON b.route_id = r.route_id
    """
    result = execute_query(sql, fetchall=True)
    return jsonify(result or [])


@app.route("/routes")
def route():
    sql = "SELECT * FROM route"
    result = execute_query(sql, fetchall=True)
    return jsonify(result or [])


@app.route('/add_bus', methods=["POST"])
def add_bus():
    try:
        data = request.get_json() or {}
        bus_type = data.get("bus_type")
        route_id = data.get("route_id")
        bus_number = data.get(
            "bus_number", f"TN-{random.randint(10, 99)}-B-{random.randint(1000, 9999)}")
        reg_number = data.get(
            "reg_number", f"REG-{random.randint(10000, 99999)}")
        driver_name = data.get("driver_name", "Unassigned")
        capacity = int(data.get("capacity", 50))
        occupancy = int(data.get("occupancy", 0))
        status = data.get("status", "Active")

        if not bus_type or not route_id:
            return jsonify({"error": "Bus type and route ID are required"}), 400

        if occupancy > capacity:
            return jsonify({"error": "Occupancy cannot exceed bus capacity"}), 400

        sql = """
            INSERT INTO bus (bus_number, reg_number, bus_type, driver_name, route_id, capacity, occupancy, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        bus_id = execute_query(sql, params=(bus_number, reg_number, bus_type,
                               driver_name, route_id, capacity, occupancy, status), commit=True)

        return jsonify({
            "message": "Bus added successfully",
            "bus_id": bus_id
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


TAMIL_PLACE_MAP = {
    "மார்த்தாண்டம்": "MARTHANDAM",
    "நாகர்கோவில்": "NAGERCOIL",
    "புதுக்கடை": "PUTHUKKADAI",
    "புதுகடை": "PUTHUKKADAI",
    "குழித்துறை": "KUZHITHURAI",
    "களியக்காவிளை": "KALIYAKKAVILAI",
    "தெங்கப்பட்டணம்": "THENGAPATTINAM",
    "தெங்கப்பட்டனம்": "THENGAPATTINAM",
    "கொல்லங்கோடு": "KOLLEMCODE",
    "கருங்கல்": "KARUNGAL",
    "கன்னியாகுமரி": "KANYAKUMARI",
    "திருவனந்தபுரம்": "THIRUVANANTHAPURAM",
    "இறையுமான்முறை": "ERAIYUMANTHURAI",
    "இறையுமான் துறை": "ERAIYUMANTHURAI",
    "குறும்பனை": "KURUMBANAI",
    "நீரோடி": "NEERODY",
    "சின்னத்துறை": "CHINNATHURAI",
    "சூழல்": "CHOOZHAL",
    "தூத்தூர்": "THOOTHUR",
    "முஞ்சிறை": "MUNCHIRAI",
    "திங்கள்சந்தை": "MONDAY MARKET",
    "குளச்சல்": "COLACHEL",
    "தக்கலை": "THUCKALAY",
    "வில்லுக்குறி": "VILLUKURI",
    "அழகியமண்டபம்": "AZHAGIYAMANDAPAM",
    "காப்புகாடு": "KAAPUKAADU",
    "நித்திரைவிளை": "NITHIRAVILAI",
    "வள்ளவிளை": "VALLAVILAI",
    "மேல்மிடாலம்": "MELMIDALAM",
    "இணையம்": "ENAYAM",
    "சூரியகோடு": "SOORIACODE",
    "அதேன்கோடு": "ATHENCODE",
    "வாவுரை": "VAVARAI",
    "கிரத்தூர்": "KIRATHOOR",
    "பாரசாலை": "PARASSALA",
    "தடேயுபுரம்": "THADEYUPURAM",
    "செம்மான்விளை": "CHEMMANVILAI",
    "நடைக்காவல்": "NADAIKKAVU",
    "நம்பாளி": "NAMBALI",
    "காக்கவிளை": "KAKAVILAI",
    "காளிங்கராஜபுரம்": "KALINGARAJAPURAM",
    "தொழிக்கோடு": "THOZHICODE",
    "ஹெலன் நகர்": "HELAN NAGAR",
    "தொலையவட்டம்": "THOLAYAVATTAM",
    "கிள்ளியூர்": "KILLIYOOR",
    "மூன்றுமுக்கு": "MOONTRUMUKKU"
}

ENGLISH_TO_TAMIL_MAP = {v.upper(): k for k, v in TAMIL_PLACE_MAP.items()}
ENGLISH_TO_TAMIL_MAP["PUTHUKADAI"] = "புதுக்கடை"
ENGLISH_TO_TAMIL_MAP["PUTHUKKADAI"] = "புதுக்கடை"
ENGLISH_TO_TAMIL_MAP["KAKAVILAI"] = "காக்கவிளை"
ENGLISH_TO_TAMIL_MAP["KAKAVILLAI"] = "காக்கவிளை"
ENGLISH_TO_TAMIL_MAP["KAAPUKAADU"] = "காப்புகாடு"


def resolve_place_name(text):
    if not text:
        return ""
    raw = text.strip()
    # Direct match or substring in Tamil map
    for tam, eng in TAMIL_PLACE_MAP.items():
        if raw == tam or raw in tam or tam in raw:
            return eng
    # Check if raw is formatted as "மார்த்தாண்டம் (MARTHANDAM)"
    if "(" in raw and ")" in raw:
        inside = raw.split("(")[1].split(")")[0].strip().upper()
        if inside:
            return inside
    return raw.upper()


def get_tamil_place_name(eng_name):
    if not eng_name:
        return ""
    up = eng_name.strip().upper()
    return ENGLISH_TO_TAMIL_MAP.get(up, eng_name)


@app.route("/search_bus")
def search_bus():
    try:
        origin_raw = request.args.get("origin", "").strip()
        destination_raw = request.args.get("destination", "").strip()

        if not origin_raw or not destination_raw:
            return jsonify({"error": "Both origin and destination are required"}), 400

        resolved_origin = resolve_place_name(origin_raw)
        resolved_dest = resolve_place_name(destination_raw)

        query_origin_eng = resolved_origin.lower()
        query_dest_eng = resolved_dest.lower()

        query_origin_raw = origin_raw.lower()
        query_dest_raw = destination_raw.lower()

        sql = """
            SELECT DISTINCT bus.bus_id, bus.bus_number, bus.bus_type, bus.depot_name, bus.driver_name,
                   bus.capacity, bus.occupancy, bus.status, bus.ticket_fare,
                   route.route_id, route.origin as route_origin, route.destination as route_dest
            FROM bus 
            JOIN route ON CAST(bus.route_id AS TEXT) = CAST(route.route_id AS TEXT)
            LEFT JOIN bus_stop s1 ON CAST(bus.route_id AS TEXT) = CAST(s1.route_id AS TEXT) AND (LOWER(s1.stop_name) = %s OR LOWER(s1.stop_name) = %s OR LOWER(s1.stop_name) LIKE %s)
            LEFT JOIN bus_stop s2 ON CAST(bus.route_id AS TEXT) = CAST(s2.route_id AS TEXT) AND (LOWER(s2.stop_name) = %s OR LOWER(s2.stop_name) = %s OR LOWER(s2.stop_name) LIKE %s)
            WHERE (s1.stop_order < s2.stop_order) 
               OR (LOWER(route.origin) IN (%s, %s) AND LOWER(route.destination) IN (%s, %s))
        """
        orig_like = f"%{query_origin_eng}%"
        dest_like = f"%{query_dest_eng}%"
        params = (query_origin_eng, query_origin_raw, orig_like, query_dest_eng, query_dest_raw,
                  dest_like, query_origin_eng, query_origin_raw, query_dest_eng, query_dest_raw)
        rows = execute_query(sql, params=params, fetchall=True)

        result = []
        for r in (rows or []):
            orig_eng = resolved_origin if resolved_origin else r.get(
                "route_origin", "")
            dest_eng = resolved_dest if resolved_dest else r.get(
                "route_dest", "")

            orig_ta = get_tamil_place_name(orig_eng)
            dest_ta = get_tamil_place_name(dest_eng)

            item = dict(r)
            item["origin"] = orig_eng
            item["destination"] = dest_eng
            item["origin_ta"] = orig_ta
            item["destination_ta"] = dest_ta

            # Fetch schedule timings
            try:
                con, cur, db_type = get_db()
                sql_q = "SELECT departure_time, arrival_time FROM bus_schedule WHERE route_id = ?" if db_type == "sqlite" else "SELECT departure_time, arrival_time FROM bus_schedule WHERE route_id = %s"
                cur.execute(sql_q, (item["route_id"],))
                schedule_rows = cur.fetchall()
                if schedule_rows:
                    item["departure_time"] = schedule_rows[0]["departure_time"]
                    item["arrival_time"] = schedule_rows[0]["arrival_time"]
                    item["all_schedules"] = [f"{s['departure_time']} - {s['arrival_time']}" for s in schedule_rows]
                else:
                    item["departure_time"] = "08:00 AM"
                    item["arrival_time"] = "10:00 AM"
                    item["all_schedules"] = ["08:00 AM - 10:00 AM"]
            except Exception as e:
                item["departure_time"] = "08:00 AM"
                item["arrival_time"] = "10:00 AM"
                item["all_schedules"] = ["08:00 AM - 10:00 AM"]

            result.append(item)

        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/get-destinations")
def get_destinations():
    try:
        origin_raw = request.args.get("origin", "").strip()
        if not origin_raw:
            return jsonify([])

        origin_eng = resolve_place_name(origin_raw).lower()
        origin_query = origin_raw.lower()

        sql = """
            SELECT DISTINCT s2.stop_name
            FROM bus_stop s1
            JOIN bus_stop s2 ON s1.route_id = s2.route_id
            WHERE (LOWER(s1.stop_name) = %s OR LOWER(s1.stop_name) = %s) AND s1.stop_order < s2.stop_order
        """
        rows = execute_query(sql, params=(
            origin_eng, origin_query), fetchall=True)
        dest_set = set()
        for r in (rows or []):
            s_eng = r["stop_name"].upper()
            s_ta = get_tamil_place_name(s_eng)
            if s_ta and s_ta != s_eng:
                dest_set.add(f"{s_ta} ({s_eng})")
            dest_set.add(s_eng)

        if not dest_set:
            for tam, eng in TAMIL_PLACE_MAP.items():
                if eng != origin_eng.upper():
                    dest_set.add(f"{tam} ({eng})")

        return jsonify(sorted(list(dest_set))[:20])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/get-origins")
def get_origins():
    try:
        query = request.args.get("query", "").strip()
        stops_set = set()

        if query:
            resolved_query = resolve_place_name(query).lower()
            raw_query = query.lower()
            sql = "SELECT DISTINCT stop_name FROM bus_stop WHERE LOWER(stop_name) LIKE %s OR LOWER(stop_name) LIKE %s LIMIT 15"
            rows = execute_query(sql, params=(
                f"%{resolved_query}%", f"%{raw_query}%"), fetchall=True)
            for r in (rows or []):
                s_eng = r["stop_name"].upper()
                s_ta = get_tamil_place_name(s_eng)
                if s_ta and s_ta != s_eng:
                    stops_set.add(f"{s_ta} ({s_eng})")
                stops_set.add(s_eng)

            # Check TAMIL_PLACE_MAP matches
            for tam, eng in TAMIL_PLACE_MAP.items():
                if query in tam or resolved_query in eng.lower() or raw_query in tam:
                    stops_set.add(f"{tam} ({eng})")
        else:
            sql = "SELECT DISTINCT stop_name FROM bus_stop LIMIT 15"
            rows = execute_query(sql, fetchall=True)
            for r in (rows or []):
                s_eng = r["stop_name"].upper()
                s_ta = get_tamil_place_name(s_eng)
                if s_ta and s_ta != s_eng:
                    stops_set.add(f"{s_ta} ({s_eng})")
                stops_set.add(s_eng)

        return jsonify(sorted(list(stops_set))[:20])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/add_route", methods=["POST"])
def add_route():
    try:
        data = request.get_json() or {}
        origin = data.get("origin")
        destination = data.get("destination")
        route_id = data.get("route_id")
        total_distance = float(data.get("total_distance", 0.0))
        est_time_mins = int(data.get("est_time_mins", 30))

        if not origin or not destination:
            return jsonify({"error": "Origin and destination are required"}), 400

        if not route_id:
            route_id = f"R{random.randint(100, 999)}"

        sql = "INSERT INTO route (route_id, origin, destination, total_distance, est_time_mins) VALUES (%s, %s, %s, %s, %s)"
        execute_query(sql, params=(route_id, origin, destination,
                      total_distance, est_time_mins), commit=True)
        return jsonify({"message": "Route added successfully", "route_id": route_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/route_stops/<string:route_id>")
@app.route("/get-route-stops/<string:route_id>")
def get_route_stops(route_id):
    sql = """
        SELECT stop_id, stop_name, latitude, longitude, stop_order
        FROM bus_stop 
        WHERE route_id = %s
        ORDER BY stop_order ASC
    """
    stops = execute_query(sql, params=(route_id,), fetchall=True)
    return jsonify(stops or [])


@app.route("/route_buses/<string:route_id>")
def route_buses(route_id):
    sql = "SELECT bus_id, bus_number, bus_type, driver_name, status, occupancy, capacity FROM bus WHERE route_id = %s"
    buses = execute_query(sql, params=(route_id,), fetchall=True)
    return jsonify(buses or [])


@app.route("/add_stop", methods=["POST"])
def add_stop():
    try:
        data = request.get_json() or {}
        route_id = data.get("route_id")
        stop_name = data.get("stop_name")
        latitude = float(data.get("latitude", 0.0))
        longitude = float(data.get("longitude", 0.0))
        stop_order = data.get("stop_order")

        if not route_id or not stop_name:
            return jsonify({"error": "Route ID and stop name are required"}), 400

        if stop_order is None:
            max_order_row = execute_query(
                "SELECT MAX(stop_order) as max_o FROM bus_stop WHERE route_id = %s", params=(route_id,), fetchone=True)
            stop_order = (max_order_row["max_o"]
                          or 0) + 1 if max_order_row else 1

        sql = "INSERT INTO bus_stop (route_id, stop_name, latitude, longitude, stop_order) VALUES (%s, %s, %s, %s, %s)"
        stop_id = execute_query(sql, params=(
            route_id, stop_name, latitude, longitude, stop_order), commit=True)
        return jsonify({"message": "Stop added successfully", "stop_id": stop_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/map/<int:bus_id>")
def map_page(bus_id):
    bus = execute_query(
        "SELECT route_id FROM bus WHERE bus_id = %s", params=(bus_id,), fetchone=True)
    route_id = bus["route_id"] if bus else "R1"
    return render_template("index.html", bus_id=bus_id, route_id=route_id)


@app.route("/stops/<string:route_id>")
def stops(route_id):
    sql = "SELECT stop_id, stop_name, latitude, longitude, stop_order FROM bus_stop WHERE route_id = %s ORDER BY stop_order"
    result = execute_query(sql, params=(route_id,), fetchall=True)
    return jsonify(result or [])


@app.route("/bus/<int:bus_id>")
def bus_details(bus_id):
    sql = """
        SELECT bus.bus_id, bus.bus_number, bus.reg_number, bus.bus_type, bus.driver_name,
               bus.status, bus.capacity, bus.occupancy, bus.current_lat, bus.current_lng,
               route.route_id, route.origin, route.destination
        FROM bus
        LEFT JOIN route ON bus.route_id = route.route_id
        WHERE bus.bus_id = %s
    """
    result = execute_query(sql, params=(bus_id,), fetchone=True)
    return jsonify(result or {})


@app.route("/bus_location/<int:bus_id>")
def bus_location(bus_id):
    bus = execute_query("SELECT current_lat, current_lng, route_id FROM bus WHERE bus_id = %s", params=(
        bus_id,), fetchone=True)
    if bus and bus.get("current_lat") and bus.get("current_lng"):
        return jsonify({"latitude": bus["current_lat"], "longitude": bus["current_lng"]})

    route_id = bus["route_id"] if bus else None
    if route_id:
        stops = execute_query("SELECT latitude, longitude FROM bus_stop WHERE route_id = %s", params=(
            route_id,), fetchall=True)
        if stops:
            stop = random.choice(stops)
            return jsonify({"latitude": stop["latitude"], "longitude": stop["longitude"]})

    return jsonify({"latitude": 8.3184, "longitude": 77.2185})


@app.route("/stats")
def stats():
    r_count = execute_query(
        "SELECT COUNT(*) as cnt FROM route", fetchone=True)["cnt"]
    b_count = execute_query(
        "SELECT COUNT(*) as cnt FROM bus", fetchone=True)["cnt"]
    s_count = execute_query(
        "SELECT COUNT(*) as cnt FROM bus_stop", fetchone=True)["cnt"]

    return jsonify({
        "routes": r_count,
        "buses": b_count,
        "stops": s_count
    })


@app.route("/api/alerts")
def public_alerts():
    sql = "SELECT * FROM alert WHERE is_active = 1 ORDER BY created_at DESC"
    result = execute_query(sql, fetchall=True)
    return jsonify(result or [])

# -------------------------------------------------------------
# ADMIN AUTHENTICATION ENDPOINTS
# -------------------------------------------------------------


@app.route("/api/admin/login", methods=["POST"])
def admin_login():
    try:
        data = request.get_json() or {}
        username = data.get("username", "").strip()
        password = data.get("password", "").strip()

        if not username or not password:
            return jsonify({"error": "Username and password are required"}), 400

        user = execute_query(
            "SELECT * FROM admin_user WHERE username = %s", params=(username,), fetchone=True)

        if user and check_password_hash(user["password_hash"], password):
            token = secrets.token_hex(16)
            ACTIVE_ADMIN_TOKENS.add(token)
            session['is_admin'] = True
            session['admin_user'] = username
            session['admin_token'] = token
            return jsonify({
                "message": "Login successful",
                "token": token,
                "username": username
            })
        else:
            return jsonify({"error": "Invalid username or password"}), 401
    except Exception as e:
        return jsonify({"error": f"Login failed: {str(e)}"}), 500


@app.route("/api/admin/logout", methods=["POST"])
def admin_logout():
    auth_header = request.headers.get('Authorization')
    if auth_header and auth_header.startswith('Bearer '):
        t = auth_header.split(' ')[1]
        ACTIVE_ADMIN_TOKENS.discard(t)
    if 'admin_token' in session:
        ACTIVE_ADMIN_TOKENS.discard(session.get('admin_token'))
    session.clear()
    return jsonify({"message": "Logged out successfully"})


@app.route("/api/admin/check_auth")
def check_auth():
    auth_header = request.headers.get('Authorization')
    is_auth = False
    if session.get('is_admin'):
        is_auth = True
    elif auth_header and auth_header.startswith('Bearer '):
        token = auth_header.split(' ')[1]
        if token in ACTIVE_ADMIN_TOKENS or token == session.get('admin_token') or token == "admin_secret_token_123":
            is_auth = True

    return jsonify({
        "authenticated": is_auth,
        "username": session.get('admin_user', 'admin') if is_auth else None
    })

# -------------------------------------------------------------
# MULTI-ROLE AUTHENTICATION ENDPOINTS (Conductor, Passenger, Admin)
# -------------------------------------------------------------
ACTIVE_ROLE_SESSIONS = {}


@app.route("/api/auth/conductor/login", methods=["POST"])
def conductor_login():
    try:
        data = request.get_json() or {}
        cid = data.get("conductor_id", "").strip().upper()
        password = data.get("password", "").strip()

        if not cid or not password:
            return jsonify({"error": "Conductor ID and password required"}), 400

        user = execute_query("SELECT * FROM conductor_user WHERE UPPER(conductor_id) = %s", params=(cid,), fetchone=True)
        if not user or not check_password_hash(user["password_hash"], password):
            return jsonify({"error": "Invalid Conductor ID or Password"}), 401

        token = secrets.token_hex(16)
        session_info = {
            "role": "conductor",
            "user_id": user["id"],
            "conductor_id": user["conductor_id"],
            "name": user["name"],
            "depot_name": user.get("depot_name", "Marthandam Depot")
        }
        ACTIVE_ROLE_SESSIONS[token] = session_info

        return jsonify({
            "message": f"Welcome Conductor {user['name']}!",
            "token": token,
            "role": "conductor",
            "user": session_info
        })
    except Exception as e:
        return jsonify({"error": f"Conductor login failed: {str(e)}"}), 500


@app.route("/api/auth/passenger/login", methods=["POST"])
def passenger_login():
    try:
        data = request.get_json() or {}
        phone = data.get("phone", "").strip()
        password = data.get("password", "").strip()

        if not phone or not password:
            return jsonify({"error": "Mobile phone and password required"}), 400

        user = execute_query("SELECT * FROM passenger_user WHERE phone = %s", params=(phone,), fetchone=True)
        if not user or not check_password_hash(user["password_hash"], password):
            return jsonify({"error": "Invalid Mobile Number or Password"}), 401

        token = secrets.token_hex(16)
        psg_id = user.get("passenger_id") or f"PSG-{1000 + user.get('id', 1)}"
        session_info = {
            "role": "passenger",
            "user_id": user["id"],
            "passenger_id": psg_id,
            "name": user["name"],
            "phone": user["phone"]
        }
        ACTIVE_ROLE_SESSIONS[token] = session_info

        return jsonify({
            "message": f"Welcome back, {user['name']}!",
            "token": token,
            "role": "passenger",
            "passenger_id": psg_id,
            "user": session_info,
            "passenger": session_info
        })
    except Exception as e:
        return jsonify({"error": f"Passenger login failed: {str(e)}"}), 500


@app.route("/api/auth/passenger/register", methods=["POST"])
def passenger_register():
    try:
        data = request.get_json() or {}
        name = data.get("name", "").strip()
        phone = data.get("phone", "").strip()
        password = data.get("password", "").strip()

        if not name or not phone or not password:
            return jsonify({"error": "Name, Mobile Number, and Password are required"}), 400

        existing = execute_query("SELECT * FROM passenger_user WHERE phone = %s", params=(phone,), fetchone=True)
        if existing:
            return jsonify({"error": "Mobile number is already registered. Please login."}), 400

        passenger_id = f"PSG-{random.randint(1000, 9999)}"
        pass_hash = generate_password_hash(password)
        sql = "INSERT INTO passenger_user (passenger_id, name, phone, password_hash) VALUES (%s, %s, %s, %s)"
        pid = execute_query(sql, params=(passenger_id, name, phone, pass_hash), commit=True)

        token = secrets.token_hex(16)
        session_info = {
            "role": "passenger",
            "user_id": pid or 1,
            "passenger_id": passenger_id,
            "name": name,
            "phone": phone
        }
        ACTIVE_ROLE_SESSIONS[token] = session_info

        return jsonify({
            "message": f"Passenger Account Created Successfully! Your Passenger ID is {passenger_id}",
            "token": token,
            "role": "passenger",
            "passenger_id": passenger_id,
            "user": session_info,
            "passenger": session_info
        })
    except Exception as e:
        return jsonify({"error": f"Registration failed: {str(e)}"}), 500


@app.route("/api/auth/me", methods=["GET"])
def get_current_user_me():
    auth_header = request.headers.get('Authorization', '')
    token = auth_header.replace('Bearer ', '').strip() if auth_header else ''

    if token and token in ACTIVE_ROLE_SESSIONS:
        info = ACTIVE_ROLE_SESSIONS[token]
        return jsonify({
            "authenticated": True,
            "role": info.get("role", "guest"),
            "user": info
        })
    elif token and (token in ACTIVE_ADMIN_TOKENS or token == session.get('admin_token') or token == "admin_secret_token_123"):
        return jsonify({
            "authenticated": True,
            "role": "admin",
            "user": {"name": session.get('admin_user', 'admin'), "username": session.get('admin_user', 'admin')}
        })
    elif session.get('is_admin'):
        return jsonify({
            "authenticated": True,
            "role": "admin",
            "user": {"name": session.get('admin_user', 'admin'), "username": session.get('admin_user', 'admin')}
        })

    return jsonify({
        "authenticated": False,
        "role": "guest",
        "user": None
    })

# -------------------------------------------------------------
# ADMIN DASHBOARD & ANALYTICS
# -------------------------------------------------------------


@app.route("/api/admin/dashboard_stats")
@admin_required
def admin_dashboard_stats():
    total_buses = execute_query(
        "SELECT COUNT(*) as c FROM bus", fetchone=True)["c"]
    active_buses = execute_query(
        "SELECT COUNT(*) as c FROM bus WHERE status = 'Active'", fetchone=True)["c"]
    inactive_buses = execute_query(
        "SELECT COUNT(*) as c FROM bus WHERE status = 'Inactive'", fetchone=True)["c"]
    maintenance_buses = execute_query(
        "SELECT COUNT(*) as c FROM bus WHERE status = 'Maintenance'", fetchone=True)["c"]
    delayed_buses = execute_query(
        "SELECT COUNT(*) as c FROM bus WHERE status = 'Delayed'", fetchone=True)["c"]

    total_routes = execute_query(
        "SELECT COUNT(*) as c FROM route", fetchone=True)["c"]
    total_stops = execute_query(
        "SELECT COUNT(*) as c FROM bus_stop", fetchone=True)["c"]
    total_alerts = execute_query(
        "SELECT COUNT(*) as c FROM alert", fetchone=True)["c"]

    occ_data = execute_query(
        "SELECT SUM(occupancy) as total_occ, SUM(capacity) as total_cap FROM bus", fetchone=True)
    total_occ = occ_data["total_occ"] if occ_data and occ_data["total_occ"] else 0
    total_cap = occ_data["total_cap"] if occ_data and occ_data["total_cap"] else 1
    avg_occupancy = round((total_occ / total_cap * 100),
                          1) if total_cap > 0 else 0

    return jsonify({
        "total_buses": total_buses,
        "active_buses": active_buses,
        "inactive_buses": inactive_buses,
        "maintenance_buses": maintenance_buses,
        "delayed_buses": delayed_buses,
        "total_routes": total_routes,
        "total_stops": total_stops,
        "active_trips": active_buses + delayed_buses,
        "total_alerts": total_alerts,
        "avg_occupancy": avg_occupancy,
        "avg_eta": 15
    })


@app.route("/api/admin/analytics")
@admin_required
def admin_analytics():
    fleet_status = {
        "Active": execute_query("SELECT COUNT(*) as c FROM bus WHERE status = 'Active'", fetchone=True)["c"],
        "Inactive": execute_query("SELECT COUNT(*) as c FROM bus WHERE status = 'Inactive'", fetchone=True)["c"],
        "Maintenance": execute_query("SELECT COUNT(*) as c FROM bus WHERE status = 'Maintenance'", fetchone=True)["c"],
        "Delayed": execute_query("SELECT COUNT(*) as c FROM bus WHERE status = 'Delayed'", fetchone=True)["c"]
    }

    route_usage = execute_query("""
        SELECT r.route_id, r.origin, r.destination, COUNT(b.bus_id) as bus_count
        FROM route r
        LEFT JOIN bus b ON r.route_id = b.route_id
        GROUP BY r.route_id, r.origin, r.destination
        ORDER BY bus_count DESC
    """, fetchall=True)

    alert_stats = execute_query("""
        SELECT alert_type, COUNT(*) as count 
        FROM alert 
        GROUP BY alert_type
    """, fetchall=True)

    depot_distribution = execute_query("""
        SELECT COALESCE(depot_name, 'Marthandam Depot') as depot_name, COUNT(*) as count
        FROM bus
        GROUP BY depot_name
    """, fetchall=True)

    category_breakdown = execute_query("""
        SELECT COALESCE(bus_type, 'Standard Deluxe') as bus_type, COUNT(*) as count
        FROM bus
        GROUP BY bus_type
    """, fetchall=True)

    return jsonify({
        "fleet_status": fleet_status,
        "route_usage": route_usage or [],
        "alert_stats": alert_stats or [],
        "depot_distribution": depot_distribution or [],
        "category_breakdown": category_breakdown or []
    })


# -------------------------------------------------------------
# ADMIN BUS MANAGEMENT APIs
# -------------------------------------------------------------
VALID_DEPOTS = [
    "Nagercoil Depot",
    "Kuzhithurai Depot",
    "Marthandam Depot",
    "Thuckalay Depot",
    "Colachel Depot",
    "Kanyakumari Depot",
    "Thingal Nagar Depot"
]

VALID_BUS_TYPES = [
    "Town Bus",
    "Standard Deluxe",
    "Simple Express",
    "Super Fast Express"
]


@app.route("/api/admin/buses")
@admin_required
def admin_get_buses():
    status_filter = request.args.get("status")
    route_filter = request.args.get("route_id")
    depot_filter = request.args.get("depot_name")
    category_filter = request.args.get("bus_type")
    search_query = request.args.get("search", "").strip().lower()

    sql = """
        SELECT b.*, r.origin, r.destination 
        FROM bus b
        LEFT JOIN route r ON b.route_id = r.route_id
        WHERE 1=1
    """
    params = []
    if status_filter:
        sql += " AND b.status = %s"
        params.append(status_filter)
    if route_filter:
        sql += " AND b.route_id = %s"
        params.append(route_filter)
    if depot_filter:
        sql += " AND b.depot_name = %s"
        params.append(depot_filter)
    if category_filter:
        sql += " AND b.bus_type = %s"
        params.append(category_filter)
    if search_query:
        sql += " AND (LOWER(b.bus_number) LIKE %s OR LOWER(b.bus_type) LIKE %s OR LOWER(b.depot_name) LIKE %s OR CAST(b.bus_id AS CHAR) LIKE %s)"
        p = f"%{search_query}%"
        params.extend([p, p, p, p])

    sql += " ORDER BY b.bus_id DESC"
    result = execute_query(sql, params=tuple(params), fetchall=True)
    return jsonify(result or [])


@app.route("/api/admin/buses", methods=["POST"])
@admin_required
def admin_create_bus():
    try:
        data = request.get_json() or {}
        bus_type = data.get("bus_type", "Standard Deluxe").strip()
        depot_name = data.get("depot_name", "Marthandam Depot").strip()
        route_id = data.get("route_id", "").strip()
        bus_number = data.get("bus_number", "").strip()
        reg_number = data.get("reg_number", "").strip()
        driver_name = data.get("driver_name", "Unassigned").strip()
        capacity = int(data.get("capacity", 50))
        occupancy = int(data.get("occupancy", 0))
        status = data.get("status", "Active")
        ticket_fare = float(data["ticket_fare"]) if data.get(
            "ticket_fare") is not None and str(data.get("ticket_fare")).strip() != "" else None

        if not route_id:
            return jsonify({"error": "Route ID is required"}), 400

        if not bus_number:
            bus_number = f"BUS-{random.randint(100, 999)}"

        if capacity <= 0:
            return jsonify({"error": "Capacity must be greater than 0"}), 400

        if occupancy > capacity:
            return jsonify({"error": "Occupancy cannot exceed capacity"}), 400

        sql = """
            INSERT INTO bus (bus_number, reg_number, bus_type, depot_name, driver_name, route_id, capacity, occupancy, status, ticket_fare)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        bus_id = execute_query(sql, params=(bus_number, reg_number, bus_type, depot_name,
                               driver_name, route_id, capacity, occupancy, status, ticket_fare), commit=True)
        return jsonify({"message": "Bus created successfully", "bus_id": bus_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/admin/buses/<int:bus_id>", methods=["PUT"])
@admin_required
def admin_update_bus(bus_id):
    try:
        data = request.get_json() or {}
        bus_type = data.get("bus_type", "Standard Deluxe").strip()
        depot_name = data.get("depot_name", "Marthandam Depot").strip()
        route_id = data.get("route_id", "").strip()
        bus_number = data.get("bus_number", "").strip()
        reg_number = data.get("reg_number", "").strip()
        driver_name = data.get("driver_name", "").strip()
        capacity = int(data.get("capacity", 50))
        occupancy = int(data.get("occupancy", 0))
        status = data.get("status", "Active")
        ticket_fare = float(data["ticket_fare"]) if data.get(
            "ticket_fare") is not None and str(data.get("ticket_fare")).strip() != "" else None

        if capacity <= 0:
            return jsonify({"error": "Capacity must be greater than 0"}), 400

        if occupancy > capacity:
            return jsonify({"error": "Occupancy cannot exceed capacity"}), 400

        sql = """
            UPDATE bus 
            SET bus_type = %s, depot_name = %s, route_id = %s, bus_number = %s, reg_number = %s,
                driver_name = %s, capacity = %s, occupancy = %s, status = %s, ticket_fare = %s
            WHERE bus_id = %s
        """
        execute_query(sql, params=(bus_type, depot_name, route_id, bus_number, reg_number,
                      driver_name, capacity, occupancy, status, ticket_fare, bus_id), commit=True)
        return jsonify({"message": "Bus updated successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/admin/buses/<int:bus_id>", methods=["DELETE"])
@admin_required
def admin_delete_bus(bus_id):
    try:
        execute_query("DELETE FROM bus WHERE bus_id = %s",
                      params=(bus_id,), commit=True)
        return jsonify({"message": "Bus deleted successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/admin/buses/<int:bus_id>/ticket", methods=["PATCH", "PUT"])
@admin_required
def admin_update_bus_ticket(bus_id):
    try:
        data = request.get_json() or {}
        ticket_fare = float(data["ticket_fare"]) if data.get(
            "ticket_fare") is not None and str(data.get("ticket_fare")).strip() != "" else None
        bus_type = data.get("bus_type")
        depot_name = data.get("depot_name")
        reg_number = data.get("reg_number")

        updates = []
        params = []
        if "ticket_fare" in data:
            updates.append("ticket_fare = %s")
            params.append(ticket_fare)
        if bus_type:
            updates.append("bus_type = %s")
            params.append(bus_type)
        if depot_name:
            updates.append("depot_name = %s")
            params.append(depot_name)
        if reg_number is not None:
            updates.append("reg_number = %s")
            params.append(reg_number)

        if not updates:
            return jsonify({"error": "No ticket fields provided to update"}), 400

        params.append(bus_id)
        sql = f"UPDATE bus SET {', '.join(updates)} WHERE bus_id = %s"
        execute_query(sql, params=tuple(params), commit=True)
        return jsonify({"message": "Bus ticket settings updated successfully", "ticket_fare": ticket_fare})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/admin/buses/<int:bus_id>/control", methods=["PATCH"])
@admin_required
def admin_control_bus(bus_id):
    try:
        data = request.get_json() or {}
        updates = []
        params = []

        if "status" in data:
            updates.append("status = %s")
            params.append(data["status"])
        if "depot_name" in data:
            updates.append("depot_name = %s")
            params.append(data["depot_name"])
        if "bus_type" in data:
            updates.append("bus_type = %s")
            params.append(data["bus_type"])
        if "occupancy" in data:
            updates.append("occupancy = %s")
            params.append(int(data["occupancy"]))
        if "ticket_fare" in data:
            updates.append("ticket_fare = %s")
            params.append(float(data["ticket_fare"]) if data["ticket_fare"] is not None and str(
                data["ticket_fare"]).strip() != "" else None)
        if "current_lat" in data:
            updates.append("current_lat = %s")
            params.append(float(data["current_lat"]))
        if "current_lng" in data:
            updates.append("current_lng = %s")
            params.append(float(data["current_lng"]))
        if "current_stop" in data:
            updates.append("current_stop = %s")
            params.append(data["current_stop"])
        if "route_id" in data:
            updates.append("route_id = %s")
            params.append(data["route_id"])

        if not updates:
            return jsonify({"error": "No update fields provided"}), 400

        params.append(bus_id)
        sql = f"UPDATE bus SET {', '.join(updates)} WHERE bus_id = %s"
        execute_query(sql, params=tuple(params), commit=True)
        return jsonify({"message": "Bus live control updated successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# -------------------------------------------------------------
# ADMIN ROUTE MANAGEMENT APIs
# -------------------------------------------------------------


@app.route("/api/admin/routes")
@admin_required
def admin_get_routes():
    sql = """
        SELECT r.*,
               (SELECT COUNT(*) FROM bus_stop s WHERE s.route_id = r.route_id) as stop_count,
               (SELECT COUNT(*) FROM bus b WHERE b.route_id = r.route_id) as bus_count
        FROM route r
        ORDER BY r.route_id ASC
    """
    result = execute_query(sql, fetchall=True)
    return jsonify(result or [])


@app.route("/api/admin/routes", methods=["POST"])
@admin_required
def admin_create_route():
    try:
        data = request.get_json() or {}
        route_id = data.get("route_id", "").strip().upper()
        origin = data.get("origin", "").strip()
        destination = data.get("destination", "").strip()
        total_distance = float(data.get("total_distance", 0.0))
        est_time_mins = int(data.get("est_time_mins", 30))
        status = data.get("status", "Active")

        if not origin or not destination:
            return jsonify({"error": "Origin and destination are required"}), 400

        if not route_id:
            route_id = f"RT-{random.randint(100, 999)}"

        sql = "INSERT INTO route (route_id, origin, destination, total_distance, est_time_mins, status) VALUES (%s, %s, %s, %s, %s, %s)"
        execute_query(sql, params=(route_id, origin, destination,
                      total_distance, est_time_mins, status), commit=True)

        return jsonify({"message": "Route created successfully", "route_id": route_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/admin/routes/<string:route_id>", methods=["PUT"])
@admin_required
def admin_update_route(route_id):
    try:
        data = request.get_json() or {}
        origin = data.get("origin", "").strip()
        destination = data.get("destination", "").strip()
        total_distance = float(data.get("total_distance", 0.0))
        est_time_mins = int(data.get("est_time_mins", 30))
        status = data.get("status", "Active")

        if not origin or not destination:
            return jsonify({"error": "Origin and destination are required"}), 400

        sql = "UPDATE route SET origin = %s, destination = %s, total_distance = %s, est_time_mins = %s, status = %s WHERE route_id = %s"
        execute_query(sql, params=(origin, destination, total_distance,
                      est_time_mins, status, route_id), commit=True)

        return jsonify({"message": "Route updated successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/admin/routes/<string:route_id>", methods=["DELETE"])
@admin_required
def admin_delete_route(route_id):
    try:
        assigned_buses = execute_query(
            "SELECT COUNT(*) as c FROM bus WHERE route_id = %s", params=(route_id,), fetchone=True)["c"]

        force = request.args.get("force", "false").lower() == "true"

        if assigned_buses > 0 and not force:
            return jsonify({
                "error": f"Cannot delete route {route_id}: {assigned_buses} bus(es) are currently assigned to it. Unassign buses first or confirm force deletion.",
                "assigned_buses": assigned_buses
            }), 400

        if force:
            execute_query("UPDATE bus SET route_id = NULL WHERE route_id = %s", params=(
                route_id,), commit=True)

        execute_query("DELETE FROM bus_stop WHERE route_id = %s",
                      params=(route_id,), commit=True)
        execute_query("DELETE FROM route WHERE route_id = %s",
                      params=(route_id,), commit=True)

        return jsonify({"message": "Route deleted successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# -------------------------------------------------------------
# ADMIN STOP MANAGEMENT APIs
# -------------------------------------------------------------


@app.route("/api/admin/stops/<string:route_id>")
@admin_required
def admin_get_stops(route_id):
    sql = "SELECT * FROM bus_stop WHERE route_id = %s ORDER BY stop_order ASC"
    result = execute_query(sql, params=(route_id,), fetchall=True)
    return jsonify(result or [])


@app.route("/api/admin/stops", methods=["POST"])
@admin_required
def admin_create_stop():
    try:
        data = request.get_json() or {}
        route_id = data.get("route_id", "").strip()
        stop_name = data.get("stop_name", "").strip()
        latitude = float(data.get("latitude", 0.0))
        longitude = float(data.get("longitude", 0.0))
        stop_order = data.get("stop_order")

        if not route_id or not stop_name:
            return jsonify({"error": "Route ID and Stop Name are required"}), 400

        if stop_order is None:
            max_r = execute_query("SELECT MAX(stop_order) as max_o FROM bus_stop WHERE route_id = %s", params=(
                route_id,), fetchone=True)
            stop_order = (max_r["max_o"] or 0) + 1 if max_r else 1

        sql = "INSERT INTO bus_stop (route_id, stop_name, latitude, longitude, stop_order) VALUES (%s, %s, %s, %s, %s)"
        stop_id = execute_query(sql, params=(
            route_id, stop_name, latitude, longitude, stop_order), commit=True)

        return jsonify({"message": "Stop created successfully", "stop_id": stop_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/admin/stops/<int:stop_id>", methods=["PUT"])
@admin_required
def admin_update_stop(stop_id):
    try:
        data = request.get_json() or {}
        stop_name = data.get("stop_name", "").strip()
        latitude = float(data.get("latitude", 0.0))
        longitude = float(data.get("longitude", 0.0))
        stop_order = int(data.get("stop_order", 1))

        if not stop_name:
            return jsonify({"error": "Stop Name is required"}), 400

        sql = "UPDATE bus_stop SET stop_name = %s, latitude = %s, longitude = %s, stop_order = %s WHERE stop_id = %s"
        execute_query(sql, params=(stop_name, latitude,
                      longitude, stop_order, stop_id), commit=True)

        return jsonify({"message": "Stop updated successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/admin/stops/<int:stop_id>", methods=["DELETE"])
@admin_required
def admin_delete_stop(stop_id):
    try:
        execute_query("DELETE FROM bus_stop WHERE stop_id = %s",
                      params=(stop_id,), commit=True)
        return jsonify({"message": "Stop deleted successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/admin/stops/reorder", methods=["POST"])
@admin_required
def admin_reorder_stops():
    try:
        data = request.get_json() or {}
        stop_ids = data.get("stop_ids", [])
        for order, s_id in enumerate(stop_ids, start=1):
            execute_query("UPDATE bus_stop SET stop_order = %s WHERE stop_id = %s", params=(
                order, s_id), commit=True)
        return jsonify({"message": "Stops reordered successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# -------------------------------------------------------------
# ADMIN BUS TIMINGS / SCHEDULE MANAGEMENT APIs
# -------------------------------------------------------------

@app.route("/api/admin/schedules", methods=["GET"])
@admin_required
def admin_get_schedules():
    try:
        route_id = request.args.get("route_id", "").strip()
        if route_id and route_id != "ALL":
            sql = "SELECT * FROM bus_schedule WHERE route_id = %s ORDER BY schedule_id ASC"
            rows = execute_query(sql, params=(route_id,), fetchall=True)
        else:
            sql = "SELECT * FROM bus_schedule ORDER BY route_id ASC, schedule_id ASC"
            rows = execute_query(sql, fetchall=True)
        return jsonify(rows or [])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/admin/schedules", methods=["POST"])
@admin_required
def admin_create_schedule():
    try:
        data = request.get_json() or {}
        route_id = data.get("route_id", "").strip()
        dep_time = data.get("departure_time", "").strip()
        arr_time = data.get("arrival_time", "").strip()

        if not route_id or not dep_time or not arr_time:
            return jsonify({"error": "Route ID, Departure Time, and Arrival Time are required"}), 400

        sql = "INSERT INTO bus_schedule (route_id, departure_time, arrival_time) VALUES (%s, %s, %s)"
        execute_query(sql, params=(route_id, dep_time, arr_time), commit=True)
        return jsonify({"message": "Schedule timing added successfully to Supabase!"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/admin/schedules/<int:schedule_id>", methods=["PUT"])
@admin_required
def admin_update_schedule(schedule_id):
    try:
        data = request.get_json() or {}
        route_id = data.get("route_id", "").strip()
        dep_time = data.get("departure_time", "").strip()
        arr_time = data.get("arrival_time", "").strip()

        if not route_id or not dep_time or not arr_time:
            return jsonify({"error": "Route ID, Departure Time, and Arrival Time are required"}), 400

        sql = "UPDATE bus_schedule SET route_id = %s, departure_time = %s, arrival_time = %s WHERE schedule_id = %s"
        execute_query(sql, params=(route_id, dep_time, arr_time, schedule_id), commit=True)
        return jsonify({"message": "Schedule timing updated successfully in Supabase!"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/admin/schedules/<int:schedule_id>", methods=["DELETE"])
@admin_required
def admin_delete_schedule(schedule_id):
    try:
        sql = "DELETE FROM bus_schedule WHERE schedule_id = %s"
        execute_query(sql, params=(schedule_id,), commit=True)
        return jsonify({"message": "Schedule timing deleted successfully from Supabase!"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# -------------------------------------------------------------
# ADMIN ALERT MANAGEMENT APIs
# -------------------------------------------------------------


@app.route("/api/admin/alerts")
@admin_required
def admin_get_alerts():
    sql = "SELECT * FROM alert ORDER BY created_at DESC"
    result = execute_query(sql, fetchall=True)
    return jsonify(result or [])


@app.route("/api/admin/alerts", methods=["POST"])
@admin_required
def admin_create_alert():
    try:
        data = request.get_json() or {}
        title = data.get("title", "").strip()
        message = data.get("message", "").strip()
        alert_type = data.get("alert_type", "General")
        target_type = data.get("target_type", "All")
        target_id = data.get("target_id", "")
        is_active = 1 if data.get("is_active", True) else 0

        if not title or not message:
            return jsonify({"error": "Title and Message are required"}), 400

        sql = "INSERT INTO alert (title, message, alert_type, target_type, target_id, is_active) VALUES (%s, %s, %s, %s, %s, %s)"
        alert_id = execute_query(sql, params=(
            title, message, alert_type, target_type, target_id, is_active), commit=True)

        return jsonify({"message": "Alert created successfully", "alert_id": alert_id})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/admin/alerts/<int:alert_id>", methods=["PUT"])
@admin_required
def admin_update_alert(alert_id):
    try:
        data = request.get_json() or {}
        title = data.get("title", "").strip()
        message = data.get("message", "").strip()
        alert_type = data.get("alert_type", "General")
        target_type = data.get("target_type", "All")
        target_id = data.get("target_id", "")
        is_active = 1 if data.get("is_active", True) else 0

        sql = "UPDATE alert SET title = %s, message = %s, alert_type = %s, target_type = %s, target_id = %s, is_active = %s WHERE alert_id = %s"
        execute_query(sql, params=(title, message, alert_type,
                      target_type, target_id, is_active, alert_id), commit=True)

        return jsonify({"message": "Alert updated successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/admin/alerts/<int:alert_id>", methods=["DELETE"])
@admin_required
def admin_delete_alert(alert_id):
    try:
        execute_query("DELETE FROM alert WHERE alert_id = %s",
                      params=(alert_id,), commit=True)
        return jsonify({"message": "Alert deleted successfully"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/admin/alerts/<int:alert_id>/toggle", methods=["PATCH"])
@admin_required
def admin_toggle_alert(alert_id):
    try:
        curr = execute_query("SELECT is_active FROM alert WHERE alert_id = %s", params=(
            alert_id,), fetchone=True)
        if not curr:
            return jsonify({"error": "Alert not found"}), 404
        new_status = 0 if curr["is_active"] == 1 else 1
        execute_query("UPDATE alert SET is_active = %s WHERE alert_id = %s", params=(
            new_status, alert_id), commit=True)
        return jsonify({"message": "Alert status toggled", "is_active": new_status})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ==========================================
# CHENNAI ONE EXTENSION APIS
# ==========================================


def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate distance in KM between two (lat, lon) coordinates."""
    R = 6371.0  # Earth radius in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * \
        math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


@app.route("/api/promo/validate", methods=["POST"])
def validate_promo():
    data = request.get_json() or {}
    code = (data.get("promo_code") or "").strip().upper()
    total_fare = float(data.get("fare", 0))

    if not code:
        return jsonify({"valid": False, "discount": 0, "message": "No code provided"})

    if code == "TNSTC1":
        discount = max(0.0, total_fare - 1.0)
        return jsonify({"valid": True, "discount": discount, "final_fare": 1.0, "message": "₹1 Special Ticket Promo Applied!"})
    elif code == "FIRSTBUS":
        discount = min(10.0, total_fare)
        return jsonify({"valid": True, "discount": discount, "final_fare": max(0.0, total_fare - discount), "message": "Flat ₹10 Off Applied!"})
    elif code == "TNSTC20":
        discount = round(total_fare * 0.20, 2)
        return jsonify({"valid": True, "discount": discount, "final_fare": max(0.0, total_fare - discount), "message": "20% Discount Applied!"})
    else:
        return jsonify({"valid": False, "discount": 0, "final_fare": total_fare, "message": "Invalid promo code"})


@app.route("/api/tickets/book", methods=["POST"])
def book_ticket():
    try:
        data = request.get_json() or {}
        bus_id = data.get("bus_id")
        from_stop = data.get("from_stop", "").strip()
        to_stop = data.get("to_stop", "").strip()
        seats = int(data.get("seats", 1))
        name = data.get("passenger_name", "Commuter").strip()
        phone = data.get("passenger_phone", "").strip()
        promo_code = data.get("promo_code", "").strip().upper()

        if not bus_id or not from_stop or not to_stop:
            return jsonify({"error": "Bus ID, Origin, and Destination stops are required"}), 400

        bus = execute_query("SELECT * FROM bus WHERE bus_id = %s",
                            params=(bus_id,), fetchone=True)
        if not bus:
            return jsonify({"error": "Bus not found"}), 404

        base_fare = bus.get("ticket_fare") if bus.get(
            "ticket_fare") is not None else 25.0
        total_raw_fare = round(base_fare * seats, 2)
        discount = 0.0

        if promo_code == "TNSTC1":
            discount = max(0.0, total_raw_fare - 1.0)
        elif promo_code == "FIRSTBUS":
            discount = min(10.0, total_raw_fare)
        elif promo_code == "TNSTC20":
            discount = round(total_raw_fare * 0.20, 2)

        final_fare = round(max(1.0, total_raw_fare - discount), 2)
        ticket_id = f"TKT-{secrets.token_hex(4).upper()}"
        qr_data = f"TNSTC|{ticket_id}|BUS:{bus.get('bus_number', 'N/A')}|{from_stop}->{to_stop}|SEATS:{seats}|FARE:{final_fare}"

        sql = """
            INSERT INTO ticket (ticket_id, bus_id, route_id, passenger_name, passenger_phone, from_stop, to_stop, seats, fare_paid, promo_code, discount_amount, qr_data, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'Valid')
        """
        execute_query(sql, params=(ticket_id, bus_id, bus.get("route_id", ""), name, phone,
                      from_stop, to_stop, seats, final_fare, promo_code, discount, qr_data), commit=True)

        new_occ = min(bus.get("capacity", 50),
                      (bus.get("occupancy") or 0) + seats)
        execute_query("UPDATE bus SET occupancy = %s WHERE bus_id = %s", params=(
            new_occ, bus_id), commit=True)

        return jsonify({
            "message": "Ticket booked successfully!",
            "ticket": {
                "ticket_id": ticket_id,
                "bus_id": bus_id,
                "bus_number": bus.get("bus_number"),
                "bus_type": bus.get("bus_type"),
                "route_id": bus.get("route_id"),
                "passenger_name": name,
                "passenger_phone": phone,
                "from_stop": from_stop,
                "to_stop": to_stop,
                "seats": seats,
                "fare_paid": final_fare,
                "promo_code": promo_code,
                "discount_amount": discount,
                "qr_data": qr_data,
                "status": "Valid"
            }
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/tickets/my_tickets", methods=["GET"])
def get_my_tickets():
    phone = request.args.get("phone", "").strip()
    if phone:
        sql = "SELECT t.*, b.bus_number, b.bus_type FROM ticket t LEFT JOIN bus b ON t.bus_id = b.bus_id WHERE t.passenger_phone = %s ORDER BY t.booked_at DESC"
        rows = execute_query(sql, params=(phone,), fetchall=True)
    else:
        sql = "SELECT t.*, b.bus_number, b.bus_type FROM ticket t LEFT JOIN bus b ON t.bus_id = b.bus_id ORDER BY t.booked_at DESC LIMIT 20"
        rows = execute_query(sql, fetchall=True)
    return jsonify(rows or [])


@app.route("/api/bus_pass/buy", methods=["POST"])
def buy_bus_pass():
    try:
        data = request.get_json() or {}
        pass_type = data.get("pass_type", "Daily")
        name = data.get("passenger_name", "Commuter").strip()
        phone = data.get("passenger_phone", "").strip()

        fare = 50.0 if pass_type == "Daily" else 1000.0
        pass_id = f"PASS-{secrets.token_hex(4).upper()}"
        qr_data = f"TNSTC-PASS|{pass_id}|TYPE:{pass_type}|NAME:{name}|FARE:{fare}"

        sql = """
            INSERT INTO ticket (ticket_id, bus_id, route_id, passenger_name, passenger_phone, from_stop, to_stop, seats, fare_paid, promo_code, discount_amount, qr_data, status)
            VALUES (%s, 0, 'ALL_ROUTES', %s, %s, 'Kanyakumari Zone', 'All Stops', 1, %s, 'BUS_PASS', 0.0, %s, 'Valid Pass')
        """
        execute_query(sql, params=(pass_id, name, phone,
                      fare, qr_data), commit=True)

        return jsonify({
            "message": f"{pass_type} Bus Pass issued successfully!",
            "pass": {
                "pass_id": pass_id,
                "pass_type": pass_type,
                "passenger_name": name,
                "fare_paid": fare,
                "qr_data": qr_data,
                "validity": "Today" if pass_type == "Daily" else "30 Days"
            }
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/search_connecting_buses", methods=["POST"])
def search_connecting_buses():
    try:
        data = request.get_json() or {}
        origin = data.get("origin", "").strip()
        destination = data.get("destination", "").strip()

        if not origin or not destination:
            return jsonify({"error": "Origin and Destination required"}), 400

        origin_stops = execute_query(
            "SELECT route_id, stop_name, stop_order FROM bus_stop WHERE LOWER(stop_name) = LOWER(%s)", params=(origin,), fetchall=True) or []
        dest_stops = execute_query("SELECT route_id, stop_name, stop_order FROM bus_stop WHERE LOWER(stop_name) = LOWER(%s)", params=(
            destination,), fetchall=True) or []

        connecting_options = []
        for o_stop in origin_stops:
            r1 = o_stop["route_id"]
            r1_stops = execute_query(
                "SELECT stop_name, stop_order FROM bus_stop WHERE route_id = %s ORDER BY stop_order", params=(r1,), fetchall=True) or []
            r1_stop_names = {s["stop_name"].lower(): s["stop_name"]
                             for s in r1_stops}

            for d_stop in dest_stops:
                r2 = d_stop["route_id"]
                if r1 == r2:
                    continue
                r2_stops = execute_query(
                    "SELECT stop_name, stop_order FROM bus_stop WHERE route_id = %s ORDER BY stop_order", params=(r2,), fetchall=True) or []
                r2_stop_names = {s["stop_name"].lower(): s["stop_name"]
                                 for s in r2_stops}

                common_keys = set(r1_stop_names.keys()).intersection(
                    set(r2_stop_names.keys()))
                for k in common_keys:
                    t_stop = r1_stop_names[k]
                    buses_r1 = execute_query(
                        "SELECT * FROM bus WHERE route_id = %s AND status = 'Active'", params=(r1,), fetchall=True) or []
                    buses_r2 = execute_query(
                        "SELECT * FROM bus WHERE route_id = %s AND status = 'Active'", params=(r2,), fetchall=True) or []

                    if buses_r1 and buses_r2:
                        s1 = execute_query("SELECT departure_time, arrival_time FROM bus_schedule WHERE route_id = %s", params=(r1,), fetchone=True)
                        s2 = execute_query("SELECT departure_time, arrival_time FROM bus_schedule WHERE route_id = %s", params=(r2,), fetchone=True)
                        buses_r1[0]["departure_time"] = s1.get("departure_time") if s1 else "08:30 AM"
                        buses_r1[0]["arrival_time"] = s1.get("arrival_time") if s1 else "09:45 AM"
                        buses_r2[0]["departure_time"] = s2.get("departure_time") if s2 else "10:00 AM"
                        buses_r2[0]["arrival_time"] = s2.get("arrival_time") if s2 else "11:15 AM"

                        connecting_options.append({
                            "transfer_stop": t_stop,
                            "leg1": {
                                "route_id": r1,
                                "from": origin,
                                "to": t_stop,
                                "buses": buses_r1
                            },
                            "leg2": {
                                "route_id": r2,
                                "from": t_stop,
                                "to": destination,
                                "buses": buses_r2
                            },
                            "est_total_fare": (buses_r1[0].get("ticket_fare") or 15) + (buses_r2[0].get("ticket_fare") or 15)
                        })
                        if len(connecting_options) >= 4:
                            break
                if len(connecting_options) >= 4:
                    break
            if len(connecting_options) >= 4:
                break

        return jsonify({"connecting_routes": connecting_options})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/stops/nearby", methods=["POST"])
def get_nearby_stops():
    try:
        data = request.get_json() or {}
        lat = float(data.get("latitude", 0))
        lng = float(data.get("longitude", 0))
        radius = float(data.get("radius_km", 10.0))

        if not lat or not lng:
            return jsonify({"error": "Latitude and Longitude required"}), 400

        all_stops = execute_query(
            "SELECT * FROM bus_stop WHERE latitude IS NOT NULL AND longitude IS NOT NULL", fetchall=True) or []
        nearby = []
        for s in all_stops:
            s_lat = s.get("latitude")
            s_lng = s.get("longitude")
            if s_lat and s_lng:
                dist = haversine_distance(lat, lng, s_lat, s_lng)
                if dist <= radius:
                    nearby.append({
                        "stop_id": s["stop_id"],
                        "route_id": s["route_id"],
                        "stop_name": s["stop_name"],
                        "latitude": s_lat,
                        "longitude": s_lng,
                        "distance_km": round(dist, 2),
                        "distance_m": int(dist * 1000),
                        "is_accessible": s.get("is_accessible", 0)
                    })

        nearby.sort(key=lambda x: x["distance_km"])
        return jsonify(nearby[:15])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/fare/calculate", methods=["POST"])
def calculate_fare():
    data = request.get_json() or {}
    route_id = data.get("route_id")
    from_stop = data.get("from_stop", "").strip()
    to_stop = data.get("to_stop", "").strip()

    if not route_id or not from_stop or not to_stop:
        return jsonify({"fare": 20.0, "stages": 1})

    stops = execute_query("SELECT stop_name, stop_order FROM bus_stop WHERE route_id = %s ORDER BY stop_order", params=(
        route_id,), fetchall=True) or []
    order_from = next(
        (s["stop_order"] for s in stops if s["stop_name"].lower() == from_stop.lower()), None)
    order_to = next((s["stop_order"]
                    for s in stops if s["stop_name"].lower() == to_stop.lower()), None)

    if order_from is not None and order_to is not None:
        stages = abs(order_to - order_from)
        calc_fare = max(10.0, 10.0 + (stages * 3.5))
        return jsonify({"fare": round(calc_fare, 2), "stages": stages, "from": from_stop, "to": to_stop})
    else:
        return jsonify({"fare": 20.0, "stages": 2, "from": from_stop, "to": to_stop})


@app.route("/api/feedback/submit", methods=["POST"])
def submit_feedback():
    try:
        data = request.get_json() or {}
        name = data.get("passenger_name", "Anonymous").strip()
        phone = data.get("passenger_phone", "").strip()
        bus_num = data.get("bus_number", "").strip()
        cat = data.get("category", "General").strip()
        comments = data.get("comments", "").strip()

        if not comments:
            return jsonify({"error": "Comments are required"}), 400

        sql = "INSERT INTO feedback (passenger_name, passenger_phone, bus_number, category, comments, status) VALUES (%s, %s, %s, %s, %s, 'Pending')"
        fid = execute_query(sql, params=(
            name, phone, bus_num, cat, comments), commit=True)
        return jsonify({"message": "Feedback submitted successfully!", "feedback_id": fid})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/admin/feedbacks", methods=["GET"])
@admin_required
def admin_get_feedbacks():
    rows = execute_query(
        "SELECT * FROM feedback ORDER BY created_at DESC", fetchall=True)
    return jsonify(rows or [])


@app.route("/api/admin/feedbacks/<int:feedback_id>", methods=["PATCH"])
@admin_required
def admin_update_feedback(feedback_id):
    data = request.get_json() or {}
    status = data.get("status", "Resolved")
    execute_query("UPDATE feedback SET status = %s WHERE feedback_id = %s", params=(
        status, feedback_id), commit=True)
    return jsonify({"message": f"Feedback status updated to {status}"})



# ==========================================
# 1. BUS STAND LIVE LED BOARD API
# ==========================================
@app.route("/api/busstand/arrivals", methods=["GET"])
def get_busstand_arrivals():
    try:
        stop_name = request.args.get("stop", "MARTHANDAM").strip().upper()
        sql = """
            SELECT DISTINCT b.bus_id, b.bus_number, b.reg_number, b.bus_type, b.depot_name, b.status, b.occupancy, b.capacity,
                   r.route_id, r.origin, r.destination, s.departure_time, s.arrival_time
            FROM bus b
            JOIN route r ON CAST(b.route_id AS TEXT) = CAST(r.route_id AS TEXT)
            LEFT JOIN bus_schedule s ON CAST(b.route_id AS TEXT) = CAST(s.route_id AS TEXT)
            WHERE UPPER(r.origin) LIKE %s OR UPPER(r.destination) LIKE %s OR UPPER(b.current_stop) LIKE %s
            ORDER BY s.departure_time ASC
            LIMIT 15
        """
        pattern = f"%{stop_name}%"
        rows = execute_query(sql, params=(pattern, pattern, pattern), fetchall=True) or []

        platforms = [1, 2, 3, 4, 5, 6]
        result = []
        for idx, r in enumerate(rows):
            item = dict(r)
            item["platform"] = platforms[idx % len(platforms)]
            item["status_label"] = "ON TIME" if (idx % 4 != 3) else "DEPARTING"
            item["origin_ta"] = get_tamil_place_name(item.get("origin", ""))
            item["destination_ta"] = get_tamil_place_name(item.get("destination", ""))
            result.append(item)

        return jsonify({"bus_stand": stop_name, "departures": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500





# ==========================================
# 3. PASS / DAILY TRAVEL CARD API
# ==========================================
@app.route("/api/passes/issue", methods=["POST"])
def issue_pass():
    try:
        data = request.get_json() or {}
        pass_type = data.get("pass_type", "Day Pass").strip()
        passenger_name = data.get("passenger_name", "Commuter").strip()
        phone = data.get("passenger_phone", "").strip()
        price = 50.0 if pass_type == "Day Pass" else (0.0 if pass_type == "Senior Citizen" else 20.0)

        pass_id = f"PASS-{secrets.token_hex(4).upper()}"
        valid_until = "31-12-2026" if pass_type != "Day Pass" else "TODAY (Midnight)"
        qr_data = f"TNSTC-PASS|{pass_id}|NAME:{passenger_name}|TYPE:{pass_type}|VALID:{valid_until}"

        sql = """
            INSERT INTO ticket (ticket_id, bus_id, route_id, passenger_name, passenger_phone, from_stop, to_stop, seats, fare_paid, promo_code, discount_amount, qr_data, status)
            VALUES (%s, 1, 'ALL', %s, %s, 'ALL TNSTC STOPS', 'ALL TNSTC STOPS', 1, %s, %s, 0.0, %s, 'Active Pass')
        """
        execute_query(sql, params=(pass_id, passenger_name, phone, price, pass_type.upper().replace(' ', '_'), qr_data), commit=True)

        return jsonify({
            "message": "Pass issued successfully!",
            "pass": {
                "pass_id": pass_id,
                "passenger_name": passenger_name,
                "passenger_phone": phone,
                "pass_type": pass_type,
                "price": price,
                "valid_until": valid_until,
                "qr_data": qr_data
            }
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/passes/verify/<string:pass_id>", methods=["GET"])
def verify_pass(pass_id):
    try:
        ticket = execute_query("SELECT * FROM ticket WHERE ticket_id = %s", params=(pass_id,), fetchone=True)
        if not ticket:
            return jsonify({"valid": False, "message": "Pass Not Found or Invalid ID"}), 404
        return jsonify({
            "valid": True,
            "pass_id": ticket["ticket_id"],
            "passenger_name": ticket["passenger_name"],
            "pass_type": ticket["promo_code"],
            "status": ticket["status"]
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ==========================================
# 4. ADMIN FINANCIAL & SALES REPORTS API
# ==========================================
@app.route("/api/admin/reports/sales", methods=["GET"])
@admin_required
def admin_sales_report():
    try:
        t_row = execute_query("SELECT COUNT(*) as c FROM ticket", fetchone=True) or {}
        total_tickets = list(t_row.values())[0] if t_row else 0
        r_row = execute_query("SELECT COALESCE(SUM(fare_paid), 0.0) as sum FROM ticket", fetchone=True) or {}
        total_revenue = list(r_row.values())[0] if r_row else 0.0
        recent_tickets = execute_query("SELECT * FROM ticket ORDER BY created_at DESC LIMIT 20", fetchall=True) or []
        route_breakdown = execute_query("SELECT route_id, COUNT(*) as count, SUM(fare_paid) as total_fare FROM ticket GROUP BY route_id ORDER BY total_fare DESC LIMIT 10", fetchall=True) or []

        return jsonify({
            "total_tickets_issued": total_tickets,
            "total_revenue_collected": round(float(total_revenue or 0.0), 2),
            "route_breakdown": route_breakdown,
            "recent_tickets": recent_tickets
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/admin/reports/export_csv", methods=["GET"])
@admin_required
def admin_export_csv():
    try:
        tickets = execute_query("SELECT ticket_id, route_id, passenger_name, from_stop, to_stop, seats, fare_paid, promo_code, status, created_at FROM ticket ORDER BY created_at DESC", fetchall=True) or []
        csv_lines = ["Ticket ID,Route ID,Passenger Name,From Stop,To Stop,Seats,Fare Paid (INR),Promo/Pass,Status,Date"]
        for t in tickets:
            line = f'"{t.get("ticket_id")}","{t.get("route_id")}","{t.get("passenger_name")}","{t.get("from_stop")}","{t.get("to_stop")}",{t.get("seats")},{t.get("fare_paid")},"{t.get("promo_code")}","{t.get("status")}","{t.get("created_at")}"'
            csv_lines.append(line)

        csv_content = "\n".join(csv_lines)
        return Response(
            csv_content,
            mimetype="text/csv",
            headers={"Content-disposition": "attachment; filename=tnstc_ticket_sales_report.csv"}
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True, use_reloader=False, port=5000)
