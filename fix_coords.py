import mysql.connector

try:
    con = mysql.connector.connect(
        host="localhost",
        user="root",
        password="Saikalyan1@",
        database="smart_bus"
    )
    cur = con.cursor()
    
    coords = {
        "MARTHANDAM": (8.3184, 77.2185),
        "KARUNGAL": (8.2434, 77.2407),
        "ENAYAM": (8.2197, 77.1895),
        "ENAYAM PUTHENTHURAI": (8.2167, 77.1870),
        "COLACHEL": (8.1812, 77.2514),
        "NAGERCOIL": (8.1833, 77.4119),
        "KANYAKUMARI": (8.0883, 77.5385),
        "THIRUVANANATHAPURAM": (8.5241, 76.9366),
        "ERAIYUMANTHURAI": (8.2405, 77.1592),
        "NEEERODY": (8.2711, 77.1044),
        "VALLAVILAI": (8.2612, 77.1242),
        "THENGAPATTINAM": (8.2383, 77.1729),
        "MELMIDALAM": (8.2255, 77.2104),
        "CHOOZHAL": (8.2932, 77.1738),
        "KURUMBANAI": (8.2045, 77.2193),
        "CHINNATHURAI": (8.2758, 77.1147),
        "KOLLEMCODE": (8.2831, 77.1354),
        "KIRATHOOR": (8.2917, 77.1549),
        "THOOTHUR": (8.2678, 77.1121),
        "THADEYUPURAM": (8.3283, 77.1994),
        "KAKAVILAI": (8.3094, 77.2047),
        "KALINGARAJAPURAM": (8.2872, 77.1432),
        "KALIYAL": (8.3842, 77.2346),
        "HELAN NAGAR": (8.2250, 77.1900),
        "PUTHUKADAI": (8.2941, 77.1756),
        "AROCKIYA NAGAR": (8.1633, 77.4219),
        "KALIYAKAVILAI": (8.3421, 77.1624),
        "MUNCHIRAI": (8.3125, 77.1789),
        "MONDAY MARKET": (8.2014, 77.2911)
    }
    
    for place, (lat, lng) in coords.items():
        cur.execute("UPDATE bus_stop SET latitude = %s, longitude = %s WHERE stop_name = %s", (lat, lng, place))
        
    con.commit()
    print("Updated coordinates for real road mapping successfully!")
    
except Exception as e:
    print(f"Error: {e}")
finally:
    if 'con' in locals() and con.is_connected():
        cur.close()
        con.close()
