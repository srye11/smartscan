import sqlite3
import json
import hashlib
import os
from datetime import datetime

DB_PATH = "smartscan.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            email TEXT PRIMARY KEY,
            full_name TEXT,
            salt TEXT,
            password_hash TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS profile (
            email TEXT PRIMARY KEY,
            allergies TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS scans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT,
            timestamp TEXT,
            image BLOB,
            result TEXT
        )
    """)

    conn.commit()
    conn.close()

def hash_password(password, salt=None):
    if salt is None:
        salt = os.urandom(16).hex()
    pw_hash = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 100_000).hex()
    return salt, pw_hash

def create_user(email, full_name, password):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT email FROM users WHERE email = ?", (email,))
    if cursor.fetchone():
        conn.close()
        return False

    salt, pw_hash = hash_password(password)
    cursor.execute(
        "INSERT INTO users (email, full_name, salt, password_hash) VALUES (?, ?, ?, ?)",
        (email, full_name, salt, pw_hash)
    )
    conn.commit()
    conn.close()
    return True

def verify_login(email, password):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT full_name, salt, password_hash FROM users WHERE email = ?", (email,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    full_name, salt, stored_hash = row
    _, check_hash = hash_password(password, salt)
    if check_hash == stored_hash:
        return full_name
    return None

def save_profile(email, allergies):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM profile WHERE email = ?", (email,))
    cursor.execute(
        "INSERT INTO profile (email, allergies) VALUES (?, ?)",
        (email, json.dumps(allergies))
    )
    conn.commit()
    conn.close()

def load_profile(email):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT allergies FROM profile WHERE email = ?", (email,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return json.loads(row[0])
    return []

def save_scan(email, image_bytes, result_dict):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO scans (email, timestamp, image, result) VALUES (?, ?, ?, ?)",
        (email, datetime.now().isoformat(), image_bytes, json.dumps(result_dict))
    )
    conn.commit()
    conn.close()

def load_scans(email):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, timestamp, image, result FROM scans WHERE email = ? ORDER BY id DESC",
        (email,)
    )
    rows = cursor.fetchall()
    conn.close()

    scans = []
    for db_id, timestamp, image, result_json in rows:
        scans.append({"db_id": db_id, "timestamp": timestamp, "image": image, "result": json.loads(result_json)})
    return scans

def delete_scan(email, scan_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM scans WHERE id = ? AND email = ?", (scan_id, email))
    conn.commit()
    conn.close()

def get_user_count():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    count = cursor.fetchone()[0]
    conn.close()
    return count

def get_all_users():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT email, full_name FROM users")
    rows = cursor.fetchall()
    conn.close()
    return rows