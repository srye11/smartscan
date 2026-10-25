"""
Re-label the ground truth for ALL label images, with all 9 allergies declared.

For every image the script opens the picture and asks 3 things:
  1. What did SmartScan flag when you scanned it (and at what severity)?
  2. What is REALLY on the label?
  3. What severity is each real allergen?
Then it tells you straight away: match / false alarm / missed / wrong severity.

It writes two files:
  - the ground truth CSV (used by evaluate.py), with all 9 allergies declared
  - scan_check_log.csv: your notes on what SmartScan showed vs what was really there

Progress is saved after every image. Type q at any question to stop and run it again later.
When every image is done, your old ground truth file is backed up and replaced.
"""
import csv
import os
import re
import shutil
import sys

BIG9 = ["milk", "egg", "peanut", "tree nut", "soy", "wheat", "fish", "shellfish", "sesame"]
IMG_EXT = (".jpg", ".jpeg", ".png")
IMAGE_FOLDER = "test_images"   # only this folder is scanned
NAME_PREFIX = "label"          # only files starting with this are used
HEADER = ["image", "declared_allergies", "actual_allergens_present", "expected_severity"]
LOG_FILE = "scan_check_log.csv"
LOG_HEADER = ["image", "smartscan_flagged", "really_on_label", "verdict"]
ALL_DECLARED = ",".join(sorted(BIG9))


def natural_key(s):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]


def find_ground_truth():
    for name in os.listdir("."):
        low = name.lower()
        if low.endswith(".csv") and "backup" not in low and "all9" not in low and "log" not in low:
            try:
                with open(name, encoding="utf-8") as f:
                    if f.readline().strip().lower().startswith("image,declared_allergies"):
                        return name
            except Exception:
                pass
    return None


def find_images():
    if not os.path.isdir(IMAGE_FOLDER):
        print(f"Could not find a folder called '{IMAGE_FOLDER}' here. Check IMAGE_FOLDER at the top of this script.")
        sys.exit(1)
    found = {}
    for root, _dirs, files in os.walk(IMAGE_FOLDER):
        for fn in files:
            if fn.lower().endswith(IMG_EXT) and fn.lower().startswith(NAME_PREFIX):
                found[fn] = os.path.join(root, fn)
    return found


def ask(prompt):
    ans = input(prompt).strip().lower()
    if ans == "q":
        print("Stopped. Run the script again to continue.")
        sys.exit(0)
    return ans


def ask_allergens(prompt):
    while True:
        ans = ask(prompt)
        if ans in ("0", "none"):
            return []
        if not ans:
            print("  Type 0 if there are none.")
            continue
        try:
            nums = sorted({int(x) for x in re.split(r"[,\s]+", ans) if x})
        except ValueError:
            print("  Type numbers like 1,5,6")
            continue
        if nums and all(1 <= n <= 9 for n in nums):
            return [BIG9[n - 1] for n in nums]
        print("  Numbers must be between 1 and 9.")


def ask_severities(allergens):
    sev = {}
    for a in allergens:
        s = ask(f"    Severity of {a}? Enter = Severe, m = Moderate: ")
        sev[a] = "Moderate" if s.startswith("m") else "Severe"
    return sev


def fmt(sev):
    return "; ".join(f"{a}:{s}" for a, s in sorted(sev.items())) or "none"


def compare(scan, real):
    notes = []
    for a in sorted(set(scan) - set(real)):
        notes.append(f"FALSE ALARM: {a}")
    for a in sorted(set(real) - set(scan)):
        notes.append(f"MISSED: {a}")
    for a in sorted(set(scan) & set(real)):
        if scan[a] != real[a]:
            notes.append(f"WRONG SEVERITY: {a} (scan {scan[a]}, real {real[a]})")
    return notes


def main():
    gt = find_ground_truth()
    if not gt:
        print("Could not find the ground truth CSV in this folder. Run this from the SmartScan folder.")
        sys.exit(1)
    partial = gt[:-4] + "_all9_partial.csv"

    images = find_images()
    names = sorted(images, key=natural_key)

    done = set()
    if os.path.exists(partial):
        with open(partial, newline="", encoding="utf-8") as f:
            done = {row["image"] for row in csv.DictReader(f)}
    else:
        with open(partial, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(HEADER)
    if not os.path.exists(LOG_FILE):
        with open(LOG_FILE, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(LOG_HEADER)

    todo = [n for n in names if n not in done]
    print(f"Ground truth file: {gt}")
    print(f"{len(names)} label images found. {len(done)} done, {len(todo)} to go.\n")

    menu = "   ".join(f"{i + 1}={a}" for i, a in enumerate(BIG9))
    for idx, name in enumerate(todo, 1):
        print("=" * 60)
        print(f"Image {idx} of {len(todo)}: {name}")
        try:
            os.startfile(images[name])  # opens the picture on Windows
        except Exception:
            print(f"  (Open this picture yourself: {images[name]})")
        print(menu)

        print("\n1) What did SmartScan show when you scanned this image (all 9 ticked)?")
        scan_list = ask_allergens("   Flagged allergens (numbers, or 0 if it said safe): ")
        scan = ask_severities(scan_list)

        print("\n2) Now read the label yourself. What is REALLY on it?")
        real_list = ask_allergens("   Allergens really on the label (numbers, or 0 for none): ")

        print("\n3) How severe is each one?")
        real = ask_severities(real_list)

        notes = compare(scan, real)
        verdict = "MATCH" if not notes else " | ".join(notes)
        print("\n   Result:", verdict)

        with open(partial, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow([
                name,
                ALL_DECLARED,
                ",".join(sorted(real)) if real else "none",
                ";".join(f"{a}:{s}" for a, s in sorted(real.items())),
            ])
        with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow([name, fmt(scan), fmt(real), verdict])

    # everything labelled: back up the old file and replace it
    backup = gt[:-4] + "_backup_few_allergies.csv"
    if not os.path.exists(backup):
        shutil.copyfile(gt, backup)
    shutil.copyfile(partial, gt)
    print("\nAll images labelled.")
    print(f"Old file saved as {backup}")
    print(f"{gt} now has all 9 allergies declared for every image.")
    print(f"Your scan-vs-real notes are in {LOG_FILE}.")
    print("Next: rename evaluation_results.csv and run the three evaluation runs again.")


if __name__ == "__main__":
    main()