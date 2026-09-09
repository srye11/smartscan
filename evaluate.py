import csv
import os
import time
from detector import detect_allergens
from openai import RateLimitError

GROUND_TRUTH_FILE = "ground_truth.csv"
RESULTS_FILE = "evaluation_results.csv"
FIELDNAMES = ["image", "declared", "actual", "flagged", "true_positives", "false_positives", "false_negatives"]

# Load ground truth
ground_truth = {}
with open(GROUND_TRUTH_FILE, newline="", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        raw_actual = row["actual_allergens_present"].strip().lower()
        if raw_actual == "none" or raw_actual == "":
            actual = []
        else:
            actual = [a.strip() for a in row["actual_allergens_present"].split(",") if a.strip()]
        declared = [a.strip() for a in row["declared_allergies"].split(",")]
        ground_truth[row["image"]] = {"declared": declared, "actual": actual}

# Load already-completed results (if resuming)
completed_images = set()
if os.path.exists(RESULTS_FILE):
    with open(RESULTS_FILE, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            completed_images.add(row["image"])
    print(f"Found {len(completed_images)} already-completed results. Resuming...")
else:
    # Create the file with headers if it doesn't exist yet
    with open(RESULTS_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()

for image_name, data in ground_truth.items():
    if image_name in completed_images:
        continue  # skip already-done images

    image_path = f"test_images/{image_name}"
    declared = data["declared"]
    actual = set(a.lower() for a in data["actual"])

    result = None
    max_retries = 5
    for attempt in range(max_retries):
        try:
            result = detect_allergens(image_path, declared)
            break
        except RateLimitError:
            wait_time = 20 * (attempt + 1)
            print(f"  Rate limit hit, waiting {wait_time}s before retry ({attempt+1}/{max_retries})...")
            time.sleep(wait_time)
        except FileNotFoundError:
            print(f"  FILE NOT FOUND: {image_path}")
            break

    if result is None:
        print(f"{image_name}: FAILED - could not get a result")
        continue

    flagged = set(a["allergen"].lower() for a in result.get("flagged_allergens", []))

    tp = flagged & actual
    fp = flagged - actual
    fn = actual - flagged

    print(f"\n{image_name}")
    print(f"  Declared: {declared}")
    print(f"  Actual:   {sorted(actual)}")
    print(f"  Flagged:  {sorted(flagged)}")
    print(f"  TP: {sorted(tp)} | FP: {sorted(fp)} | FN: {sorted(fn)}")

    # Append this row to the results file immediately
    with open(RESULTS_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writerow({
            "image": image_name,
            "declared": ", ".join(declared),
            "actual": ", ".join(sorted(actual)),
            "flagged": ", ".join(sorted(flagged)),
            "true_positives": ", ".join(sorted(tp)),
            "false_positives": ", ".join(sorted(fp)),
            "false_negatives": ", ".join(sorted(fn)),
        })

    time.sleep(10)  # pause between calls to avoid rate limits

# ---- Calculate final metrics by reading the full results file back ----
total_tp = 0
total_fp = 0
total_fn = 0

with open(RESULTS_FILE, newline="", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        tp_count = len([a for a in row["true_positives"].split(",") if a.strip()])
        fp_count = len([a for a in row["false_positives"].split(",") if a.strip()])
        fn_count = len([a for a in row["false_negatives"].split(",") if a.strip()])
        total_tp += tp_count
        total_fp += fp_count
        total_fn += fn_count

precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0
recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0
f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0

print(f"\n{'='*50}")
print(f"TOTAL TP: {total_tp} | TOTAL FP: {total_fp} | TOTAL FN: {total_fn}")
print(f"Precision: {precision:.2f}")
print(f"Recall:    {recall:.2f}")
print(f"F1 Score:  {f1:.2f}")
print(f"{'='*50}")
print(f"\nResults saved to {RESULTS_FILE}")