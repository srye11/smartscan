import os
import requests
from dotenv import load_dotenv

load_dotenv()
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_ANON_KEY")

email = input("Email: ")
password = input("Password: ")

r = requests.post(
    f"{url}/auth/v1/token?grant_type=password",
    headers={"apikey": key, "Content-Type": "application/json"},
    json={"email": email, "password": password},
)
print(r.json().get("access_token") or r.text)