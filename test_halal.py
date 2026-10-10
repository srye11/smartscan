import csv
import time
from halal import detect_halal

# Edit this list. Start with these, then add label31.jpg onwards as you collect more.
images = [
    "label24.jpg",
    "label31.jpg",
    "label32.jpg",
    "label33.jpg",
    "label34.jpg",
    "label35.jpg",
    "label36.jpg",
    "label37.jpg",
    "label38.jpg",
    "label39.jpeg",
    "label40.jpg",
    "label41.jpg",
    "label42.jpg",
    "label43.png",
    "label44.jpg",
]

rows = []

for name in images:
    print(f"\n--- {name} ---")
    try:
        result = detect_halal(f"test_images/{name}")
    except FileNotFoundError:
        print("FILE NOT FOUND, check the name and extension")
        continue

    if result is None:
        print("FAILED")
        continue

    logo = result["halal_logo"]
    print("Status:", result["status"], "| Logo seen:", logo["seen"], "| Body:", logo["body_name"])
    for f in result["flags"]:
        print(f"  [{f['category']}] {f['ingredient']}  ->  \"{f['quoted_text']}\"")
        print(f"      {f['reason']}")

    rows.append({
        "image": name,
        "status": result["status"],
        "logo_seen": logo["seen"],
        "logo_body": logo["body_name"],
        "flags": "; ".join(f"{f['ingredient']} ({f['category']})" for f in result["flags"]) or "none",
        "correct_yn": "",
    })
    time.sleep(5)

with open("halal_results.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=["image", "status", "logo_seen", "logo_body", "flags", "correct_yn"])
    writer.writeheader()
    writer.writerows(rows)

print("\nSaved to halal_results.csv")