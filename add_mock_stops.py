import mysql.connector
import random

try:
    con = mysql.connector.connect(
        host="localhost",
        user="root",
        password="Saikalyan1@",
        database="smart_bus"
    )
    cur = con.cursor(dictionary=True)
    
    cur.execute("SELECT * FROM route")
    routes = cur.fetchall()
    
    # Specific coordinates mapped
    coords = {
        "MARTHANDAM": (8.3184, 77.2185),
        "KARUNGAL": (8.2434, 77.2407),
        "CHENNAI": (13.0827, 80.2707),
        "GUINDY": (13.0067, 80.2206)
    }
    
    # Check if empty, or just add missing
    stops_added = 0
    for r in routes:
        rid = r['route_id']
        cur.execute("SELECT COUNT(*) as c FROM bus_stop WHERE route_id = %s", (rid,))
        if cur.fetchone()['c'] == 0:
            origin_name = r['origin'].upper()
            dest_name = r['destination'].upper()
            
            # Origin coords
            o_coord = coords.get(origin_name)
            if not o_coord:
                o_coord = (8.3184 + random.uniform(-0.05, 0.05), 77.2185 + random.uniform(-0.05, 0.05))
                
            # Dest coords
            d_coord = coords.get(dest_name)
            if not d_coord:
                d_coord = (8.3184 + random.uniform(-0.05, 0.05), 77.2185 + random.uniform(-0.05, 0.05))
            
            # Insert Origin
            cur.execute("""
                INSERT INTO bus_stop (route_id, stop_name, latitude, longitude, stop_order)
                VALUES (%s, %s, %s, %s, %s)
            """, (rid, origin_name, o_coord[0], o_coord[1], 1))
            
            # Insert some intermediate stops maybe? Just origin and dest for simplicity right now.
            # Insert Destination
            cur.execute("""
                INSERT INTO bus_stop (route_id, stop_name, latitude, longitude, stop_order)
                VALUES (%s, %s, %s, %s, %s)
            """, (rid, dest_name, d_coord[0], d_coord[1], 2))
            
            stops_added += 2
            
    con.commit()
    print(f"Added {stops_added} stops.")
    
except Exception as e:
    print(f"Error: {e}")
finally:
    if 'con' in locals() and con.is_connected():
        cur.close()
        con.close()
