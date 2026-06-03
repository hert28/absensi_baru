import mysql.connector
import os
from config import DB_CONFIG

def check():
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM admin")
        admins = cursor.fetchall()
        print("Admin di database:")
        for a in admins:
            print(a)
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == '__main__':
    check()
