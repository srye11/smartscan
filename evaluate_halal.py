import csv
import os
import time
from halal import detect_halal
from openai import RateLimitError

GT_FILE = "halal_ground_truth.csv"
OUT_FILE = "halal_eval_results.csv"
FIELDS = ["image", "expected_status", "predicted_status", "status_correct", "predicted_flags"]
ORDER = ["haram_found", "doubtful", "none_found"]

ground_truth = {}
with open(GT_FILE, newline="", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        exp = row["expected_status"].strip().lower()
        if exp not in ORDER:
            print(f"Skipping {row['image']}: expected_status must be one of {ORDER} (got '{exp}')")
            continue
        ground_truth[row["image"].strip()] = exp

done = set()
if os.path.exists(OUT_FILE):
    with open(OUT_FILE, newline="", encoding="utf-8") as f:
        done = {r["image"] for r in csv.DictReader(f)}
    print(f"Resuming, {len(done)} already done")
else:
    with open(OUT_FILE, "w", newline="", encoding="utf-8") as f:
        csv.DictWriter(f, fieldnames=FIELDS).writeheader()

for image, expected in ground_truth.items():
    if image in done:
        continue

    result = None
    for attempt in range(5):
        try:
            result = detect_halal(f"test_images/{image}")
            break
        except RateLimitError:
            wait = 20 * (attempt + 1)
            print(f"  Rate limit, waiting {wait}s ({attempt + 1}/5)...")
            time.sleep(wait)
        except FileNotFoundError:
            print(f"  FILE NOT FOUND: {image}")
            break

    if result is None:
        print(f"{image}: FAILED")
        continue

    predicted = result["status"]
    flags = "; ".join(f"{x['ingredient']} ({x['category']})" for x in result["flags"]) or "none"
    correct = predicted == expected
    print(f"{image}: expected={expected} | predicted={predicted} | {'OK' if correct else 'WRONG'}")

    with open(OUT_FILE, "a", newline="", encoding="utf-8") as f:
        csv.DictWriter(f, fieldnames=FIELDS).writerow({
            "image": image,
            "expected_status": expected,
            "predicted_status": predicted,
            "status_correct": correct,
            "predicted_flags": flags,
        })
    time.sleep(5)

# ---- Summary ----
confusion = {e: {p: 0 for p in ORDER} for e in ORDER}
tp = fp = fn = tn = exact = n = 0

with open(OUT_FILE, newline="", encoding="utf-8") as f:
    for r in csv.DictReader(f):
        e, p = r["expected_status"], r["predicted_status"]
        if e not in ORDER or p not in ORDER:
            continue
        n += 1
        confusion[e][p] += 1
        exact += e == p
        exp_flag, pred_flag = e != "none_found", p != "none_found"
        tp += exp_flag and pred_flag
        fp += (not exp_flag) and pred_flag
        fn += exp_flag and (not pred_flag)
        tn += (not exp_flag) and (not pred_flag)

precision = tp / (tp + fp) if (tp + fp) else 0
recall = tp / (tp + fn) if (tp + fn) else 0
f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0
haram_total = sum(confusion["haram_found"].values())
haram_hit = confusion["haram_found"]["haram_found"]

print("\n" + "=" * 50)
print(f"Labels evaluated: {n}")
print(f"Exact status accuracy: {exact}/{n} = {exact / n:.2f}" if n else "No results")
print(f"Flagged vs not flagged -> TP {tp} | FP {fp} | FN {fn} | TN {tn}")
print(f"Precision: {precision:.2f} | Recall: {recall:.2f} | F1: {f1:.2f}")
print(f"Haram labels caught as haram: {haram_hit}/{haram_total}")
print("\nConfusion matrix (rows = expected, columns = predicted)")
print(f"{'':16}" + "".join(f"{p:>14}" for p in ORDER))
for e in ORDER:
    print(f"{e:16}" + "".join(f"{confusion[e][p]:>14}" for p in ORDER))
print("=" * 50)