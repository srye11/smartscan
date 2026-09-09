import csv
from detector import detect_allergens

# Edit this list to match YOUR actual test_images files and realistic allergies to test against.
# Doesn't have to be exactly 9 - add/remove rows to cover your Big 9 allergens across your labels.
test_cases = [
    {"image": "test_images/label1.jpg", "allergies": ["milk", "peanut", "wheat"]},
    {"image": "test_images/label2.jpg", "allergies": ["peanut", "soy"]},
    {"image": "test_images/label3.jpg", "allergies": ["milk", "peanut", "wheat"]},
    {"image": "test_images/label4.jpg", "allergies": ["egg", "soy"]},
    {"image": "test_images/label5.jpg", "allergies": ["soy"]},
    {"image": "test_images/label6.jpg", "allergies": ["fish"]},
    {"image": "test_images/label7.jpg", "allergies": ["shellfish"]},
    {"image": "test_images/label8.jpg", "allergies": ["tree nut", "soy"]},
    {"image": "test_images/label9.jpg", "allergies": ["sesame"]},
]

results_log = []

for i, case in enumerate(test_cases, start=1):
    print(f"\n{'='*50}")
    print(f"TEST {i}: {case['image']}")
    print(f"Declared allergies: {', '.join(case['allergies'])}")
    print(f"{'='*50}")

    try:
        result = detect_allergens(case["image"], case["allergies"])

        if result is None:
            print("FAILED - model did not return valid JSON")
            results_log.append({
                "test_num": i,
                "image": case["image"],
                "declared_allergies": ", ".join(case["allergies"]),
                "safe": "ERROR",
                "flagged_allergens": "ERROR - invalid JSON returned",
                "correct_yn": ""
            })
            continue

        print(f"Safe: {result.get('safe')}")
        flagged = result.get("flagged_allergens", [])

        if not flagged:
            print("No allergens flagged.")
        else:
            for a in flagged:
                print(f"  - {a['allergen']} | {a['severity']} | {a['explanation']}")

        results_log.append({
            "test_num": i,
            "image": case["image"],
            "declared_allergies": ", ".join(case["allergies"]),
            "safe": result.get("safe"),
            "flagged_allergens": "; ".join(
                [f"{a['allergen']} ({a['severity']})" for a in flagged]
            ) if flagged else "none",
            "correct_yn": ""
        })

    except FileNotFoundError:
        print(f"FILE NOT FOUND: {case['image']} - check the filename/path")
        results_log.append({
            "test_num": i,
            "image": case["image"],
            "declared_allergies": ", ".join(case["allergies"]),
            "safe": "ERROR",
            "flagged_allergens": "ERROR - file not found",
            "correct_yn": ""
        })

# Save everything to a CSV for your records
with open("test_results.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(
        f,
        fieldnames=["test_num", "image", "declared_allergies", "safe", "flagged_allergens", "correct_yn"]
    )
    writer.writeheader()
    writer.writerows(results_log)

print(f"\n{'='*50}")
print("Done. Results saved to test_results.csv")
print("Open the CSV and fill in the 'correct_yn' column (Y/N) after checking each label.")
print(f"{'='*50}")