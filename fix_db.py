import mysql.connector

try:
    con = mysql.connector.connect(
        host="localhost",
        user="root",
        password="Saikalyan1@",
        database="smart_bus"
    )
    cur = con.cursor()

    cur.execute("DELETE FROM bus_stop WHERE route_id = 1;")
    
    stops = [
        (1, "Chennai Central", 13.0827, 80.2707, 1),
        (1, "Egmore", 13.0782, 80.2584, 2),
        (1, "Guindy", 13.0067, 80.2206, 3),
        (1, "St. Thomas Mount", 13.0034, 80.1989, 4),
        (1, "Pallavaram", 12.9682, 80.1481, 5),
        (1, "Tambaram", 12.9249, 80.1000, 6)
    ]
    
    sql = "INSERT INTO bus_stop(route_id, stop_name, latitude, longitude, stop_order) VALUES(%s, %s, %s, %s, %s)"
    cur.executemany(sql, stops)
    
    con.commit()
    print("Database bus_stop fixed successfully!")
    con.close()
except Exception as e:
    print("Error:", e)
