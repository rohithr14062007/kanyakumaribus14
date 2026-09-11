import mysql.connector

try:
    con = mysql.connector.connect(
        host="localhost",
        user="root",
        password="Saikalyan1@",
        database="smart_bus"
    )
    cur = con.cursor(dictionary=True)
    
    # Get all routes
    cur.execute("SELECT route_id FROM route")
    routes = cur.fetchall()
    
    buses_added = 0
    for r in routes:
        rid = r['route_id']
        cur.execute("SELECT COUNT(*) as count FROM bus WHERE route_id = %s", (rid,))
        count = cur.fetchone()['count']
        
        if count == 0:
            # Add a Standard and an AC bus for the route
            cur.execute("INSERT INTO bus (bus_type, route_id) VALUES (%s, %s)", ("Standard", rid))
            cur.execute("INSERT INTO bus (bus_type, route_id) VALUES (%s, %s)", ("AC", rid))
            buses_added += 2
            
    con.commit()
    print(f"Added {buses_added} new buses to the database.")
    
except Exception as e:
    print(f"Error: {e}")
finally:
    if 'con' in locals() and con.is_connected():
        cur.close()
        con.close()
