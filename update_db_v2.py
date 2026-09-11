import mysql.connector

try:
    con = mysql.connector.connect(
        host="localhost",
        user="root",
        password="Saikalyan1@",
        database="smart_bus"
    )
    cur = con.cursor()
    
    print("Dropping foreign keys...")
    cur.execute("ALTER TABLE bus DROP FOREIGN KEY bus_ibfk_1;")
    cur.execute("ALTER TABLE bus_stop DROP FOREIGN KEY bus_stop_ibfk_1;")
    
    print("Altering types...")
    # First remove auto_increment
    cur.execute("ALTER TABLE route MODIFY route_id INT NOT NULL;")
    # Then change to VARCHAR
    cur.execute("ALTER TABLE route MODIFY route_id VARCHAR(20) NOT NULL;")
    
    cur.execute("ALTER TABLE bus MODIFY route_id VARCHAR(20);")
    cur.execute("ALTER TABLE bus_stop MODIFY route_id VARCHAR(20);")
    
    print("Restoring foreign keys...")
    cur.execute("ALTER TABLE bus ADD CONSTRAINT bus_ibfk_1 FOREIGN KEY (route_id) REFERENCES route(route_id);")
    cur.execute("ALTER TABLE bus_stop ADD CONSTRAINT bus_stop_ibfk_1 FOREIGN KEY (route_id) REFERENCES route(route_id);")
    
    # Needs to add missing total_distance column in the route table since the query has it
    try:
        cur.execute("ALTER TABLE route ADD COLUMN total_distance FLOAT DEFAULT NULL;")
    except Exception as e:
        print("Column total_distance might already exist.")
        
    queries = [
        "INSERT IGNORE INTO route (route_id, origin, destination, total_distance) VALUES ('81A','MARTHANDAM','ERAIYUMANTHURAI',NULL)",
        "INSERT IGNORE INTO route (route_id, origin, destination, total_distance) VALUES ('81B','MARTHANDAM','CHOOZHAL',NULL)",
        "INSERT IGNORE INTO route (route_id, origin, destination, total_distance) VALUES ('81C','KURUMBANAI','NEEERODY',NULL)",
        "INSERT IGNORE INTO route (route_id, origin, destination, total_distance) VALUES ('81V','MARTHANDAM','CHINNATHURAI',NULL)",
        "INSERT IGNORE INTO route (route_id, origin, destination, total_distance) VALUES ('82','MARTHANDAM','KOLLEMCODE',NULL)",
        "INSERT IGNORE INTO route (route_id, origin, destination, total_distance) VALUES ('82A','MARTHANDAM','KOLLEMCODE',NULL)",
        "INSERT IGNORE INTO route (route_id, origin, destination, total_distance) VALUES ('82B','MARTHANDAM','KOLLEMCODE',NULL)",
        "INSERT IGNORE INTO route (route_id, origin, destination, total_distance) VALUES ('82D','MARTHANDAM','KIRATHOOR',NULL)",
        "INSERT IGNORE INTO route (route_id, origin, destination, total_distance) VALUES ('82J','MARTHANDAM','THOOTHUR',NULL)",
        "INSERT IGNORE INTO route (route_id, origin, destination, total_distance) VALUES ('82K','MARTHANDAM','THADEYUPURAM',NULL)",
        "INSERT IGNORE INTO route (route_id, origin, destination, total_distance) VALUES ('82M','MARTHANDAM','KOLLEMCODE',NULL)",
        "INSERT IGNORE INTO route (route_id, origin, destination, total_distance) VALUES ('83','MARTHANDAM','ERAIYUMANTHURAI',NULL)",
        "INSERT IGNORE INTO route (route_id, origin, destination, total_distance) VALUES ('83A','MARTHANDAM','ERAIYUMANTHURAI',NULL)",
        "INSERT IGNORE INTO route (route_id, origin, destination, total_distance) VALUES ('83B','MARTHANDAM','VALLAVILAI',NULL)",
        "INSERT IGNORE INTO route (route_id, origin, destination, total_distance) VALUES ('83C','MARTHANDAM','NEEERODY',NULL)",
        "INSERT IGNORE INTO route (route_id, origin, destination, total_distance) VALUES ('83D','MARTHANDAM','KAKAVILAI',NULL)",
        "INSERT IGNORE INTO route (route_id, origin, destination, total_distance) VALUES ('83L','MARTHANDAM','KALINGARAJAPURAM',NULL)",
        "INSERT IGNORE INTO route (route_id, origin, destination, total_distance) VALUES ('84A','MARTHANDAM','KALIYAL',NULL)",
        "INSERT IGNORE INTO route (route_id, origin, destination, total_distance) VALUES ('PCG II','MARTHANDAM','VALLAVILAI',NULL)",
        "INSERT IGNORE INTO route (route_id, origin, destination, total_distance) VALUES ('87','MARTHANDAM','THENGAPATTINAM',NULL)",
        "INSERT IGNORE INTO route (route_id, origin, destination, total_distance) VALUES ('87A','MARTHANDAM','ENAYAM',NULL)",
        "INSERT IGNORE INTO route (route_id, origin, destination, total_distance) VALUES ('87B','MARTHANDAM','MELMIDALAM',NULL)",
        "INSERT IGNORE INTO route (route_id, origin, destination, total_distance) VALUES ('87C','MARTHANDAM','ENAYAM',NULL)",
        "INSERT IGNORE INTO route (route_id, origin, destination, total_distance) VALUES ('87G','MARTHANDAM','KARUNGAL',NULL)",
        "INSERT IGNORE INTO route (route_id, origin, destination, total_distance) VALUES ('87H','MARTHANDAM','KARUNGAL',NULL)",
        "INSERT IGNORE INTO route (route_id, origin, destination, total_distance) VALUES ('87 TSS','MARTHANDAM','HELAN NAGAR',NULL)",
        "INSERT IGNORE INTO route (route_id, origin, destination, total_distance) VALUES ('9H','COLACHEL','THOOTHUR',NULL)",
        "INSERT IGNORE INTO route (route_id, origin, destination, total_distance) VALUES ('9J','COLACHEL','ERAIYUMANTHURAI',NULL)",
        "INSERT IGNORE INTO route (route_id, origin, destination, total_distance) VALUES ('10C','KARUNGAL','PUTHUKADAI',NULL)",
        "INSERT IGNORE INTO route (route_id, origin, destination, total_distance) VALUES ('90','NAGERCOIL','MARTHANDAM',NULL)",
        "INSERT IGNORE INTO route (route_id, origin, destination, total_distance) VALUES ('302','NAGERCOIL','AROCKIYA NAGAR',NULL)",
        "INSERT IGNORE INTO route (route_id, origin, destination, total_distance) VALUES ('303','KANYAKUMARI','KALIYAKAVILAI',NULL)",
        "INSERT IGNORE INTO route (route_id, origin, destination, total_distance) VALUES ('309','NAGERCOIL','THENGAPATTINAM',NULL)",
        "INSERT IGNORE INTO route (route_id, origin, destination, total_distance) VALUES ('310','NAGERCOIL','VALLAVILAI',NULL)",
        "INSERT IGNORE INTO route (route_id, origin, destination, total_distance) VALUES ('310A','NAGERCOIL','PUTHUKADAI',NULL)",
        "INSERT IGNORE INTO route (route_id, origin, destination, total_distance) VALUES ('310B','NAGERCOIL','MUNCHIRAI',NULL)",
        "INSERT IGNORE INTO route (route_id, origin, destination, total_distance) VALUES ('382','NAGERCOIL','KOLLEMCODE',NULL)",
        "INSERT IGNORE INTO route (route_id, origin, destination, total_distance) VALUES ('383','NAGERCOIL','NEERODY',NULL)",
        "INSERT IGNORE INTO route (route_id, origin, destination, total_distance) VALUES ('451','NAGERCOIL','THIRUVANANATHAPURAM',NULL)",
        "INSERT IGNORE INTO route (route_id, origin, destination, total_distance) VALUES ('455','THIRUVANANATHAPURAM','THENGAPATTINAM',NULL)",
        "INSERT IGNORE INTO route (route_id, origin, destination, total_distance) VALUES ('456','THIRUVANANATHAPURAM','MONDAY MARKET',NULL)",
        "INSERT IGNORE INTO route (route_id, origin, destination, total_distance) VALUES ('475','THIRUVANANATHAPURAM','KANYAKUMARI',NULL)"
    ]
    
    for q in queries:
        cur.execute(q)
        
    con.commit()
    print("Successfully migrated db and inserted new route values.")
    
except Exception as e:
    print(f"Error: {e}")
finally:
    if 'con' in locals() and con.is_connected():
        cur.close()
        con.close()
