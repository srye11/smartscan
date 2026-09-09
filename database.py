import sqlite3
import json
from datetime import datetime

DB_PATH = "smartscan.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS profile (
            id INTEGER PRIMARY KEY,
            allergies TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS scans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            image BLOB,
            result TEXT
        )
    """)

    conn.commit()
    conn.close()

def save_profile(allergies):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM profile")
    cursor.execute(
        "INSERT INTO profile (id, allergies) VALUES (1, ?)",
        (json.dumps(allergies),)
    )
    conn.commit()
    conn.close()

def load_profile():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT allergies FROM profile WHERE id = 1")
    row = cursor.fetchone()
    conn.close()
    if row:
        return json.loads(row[0])
    return []

def save_scan(image_bytes, result_dict):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO scans (timestamp, image, result) VALUES (?, ?, ?)",
        (datetime.now().isoformat(), image_bytes, json.dumps(result_dict))
    )
    conn.commit()
    conn.close()

def load_scans():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT timestamp, image, result FROM scans ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()

    scans = []
    for timestamp, image, result_json in rows:
        scans.append({
            "timestamp": timestamp,
            "image": image,
            "result": json.loads(result_json)
        })
    return scans