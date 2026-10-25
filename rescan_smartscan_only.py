"""
Redo ONLY the "what SmartScan showed" answers. Your answers for what is really on the label
are kept as they are.

For every label image the script opens the picture and asks:
  - What did SmartScan flag when you scan it again (all 9 ticked), and at what severity?
Then it compares with the real label answers you already saved and tells you:
match / false alarm / missed / wrong severity.

At ANY question you can type:
  r  = redo this image
  b  = go back to the previous image
  q  = stop (run the script again later to continue)

If an image is new (not in your ground truth yet), it also asks what is really on the label
and adds it to the ground truth file.

Files:
  - reads  scan_check_log.csv  (your real-label answers are taken from here and the ground truth)
  - writes scan_check_log.csv  (new SmartScan answers); the old one is saved first as
    scan_check_log_before_rescan.csv
  - ground truth CSV is NOT changed (except to add a brand-new image).
Progress is saved after every image in rescan_progress.csv.
"""
import csv
import os
import re
import shutil
import sys

BIG9 = ["milk", "egg", "peanut", "tree nut", "soy", "wheat", "fish", "shellfish", "sesame"]
IMG_EXT = (".jpg", ".jpeg", ".png")
IMAGE_FOLDER = "test_images"
NAME_PREFIX = "label"
LOG_FILE = "scan_check_log.csv"
LOG_BACKUP = "scan_check_log_before_rescan.csv"
PROGRESS = "rescan_progress.csv"
LOG_HEADER = ["image", "smartscan_flagged", "really_on_label", "verdict"]
ALL_DECLARED = ",".join(sorted(BIG9))
GT_HEADER = ["image", "declared_allergies", "actual_allergens_present", "expected_severity"]


class Redo(Exception):
    pass


class Back(Exception):
    pass


def natural_key(s):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]


def read_rows(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.reader(f))


def write_rows(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows(rows)


def find_ground_truth():
    for name in os.listdir("."):
        low = name.lower()
        if low.endswith(".csv") and "backup" not in low and "all9" not in low and "log" not in low \
                and "before" not in low and "progress" not in low:
            try:
                with open(name, encoding="utf-8") as f:
                    if f.readline().strip().lower().startswith("image,declared_allergies"):
                        return name
            except Exception:
                pass
    return None


def find_images():
    if not os.path.isdir(IMAGE_FOLDER):
        print(f"Could not find a folder called '{IMAGE_FOLDER}' here.")
        sys.exit(1)
    found = {}
    for root, _dirs, files in os.walk(IMAGE_FOLDER):
        for fn in files:
            if fn.lower().endswith(IMG_EXT) and fn.lower().startswith(NAME_PREFIX):
                found[fn] = os.path.join(root, fn)
    return found


def parse_sev(text):
    """'milk:Severe; soy:Moderate' or 'milk:Severe;soy:Moderate' -> dict"""
    out = {}
    text = (text or "").strip()
    if not text or text.lower() == "none":
        return out
    for part in text.split(";"):
        part = part.strip()
        if ":" in part:
            a, s = part.split(":", 1)
            out[a.strip().lower()] = s.strip().capitalize()
    return out


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


def ask(prompt):
    ans = input(prompt).strip().lower()
    if ans == "q":
        print("Stopped. Run the script again to continue.")
        sys.exit(0)
    if ans in ("r", "redo"):
        raise Redo()
    if ans in ("b", "back"):
        raise Back()
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
            print("  Type numbers like 1,5,6   (r = redo, b = previous image, q = quit)")
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


def load_real_answers(gt_path):
    """Real answers per image: from the ground truth CSV (the one evaluate.py uses)."""
    real = {}
    if gt_path:
        for r in read_rows(gt_path)[1:]:
            if len(r) >= 4:
                actual = [x.strip().lower() for x in r[2].split(",") if x.strip() and x.strip().lower() != "none"]
                sev = parse_sev(r[3])
                real[r[0]] = {a: sev.get(a, "Severe") for a in actual}
    return real


def main():
    gt = find_ground_truth()
    if not gt:
        print("Could not find the ground truth CSV. Run this from the SmartScan folder.")
        sys.exit(1)
    real_answers = load_real_answers(gt)

    images = find_images()
    names = sorted(images, key=natural_key)

    if os.path.exists(LOG_FILE) and not os.path.exists(LOG_BACKUP):
        shutil.copyfile(LOG_FILE, LOG_BACKUP)
    if not os.path.exists(PROGRESS):
        write_rows(PROGRESS, [LOG_HEADER])

    def done_names():
        return {r[0] for r in read_rows(PROGRESS)[1:]}

    print(f"Ground truth file (not changed): {gt}")
    print(f"{len(names)} label images found. {len(done_names())} done.")
    print("Tip: type r to redo the current image, b to go back to the previous one, q to quit.\n")
    menu = "   ".join(f"{i + 1}={a}" for i, a in enumerate(BIG9))

    while True:
        done = done_names()
        todo = [n for n in names if n not in done]
        if not todo:
            break
        name = todo[0]
        print("=" * 60)
        print(f"Image {len(done) + 1} of {len(names)}: {name}")
        try:
            os.startfile(images[name])
        except Exception:
            print(f"  (Open this picture yourself: {images[name]})")
        print(menu)

        new_gt_row = None
        try:
            print("\nScan this image in SmartScan again (all 9 ticked). What did it show?")
            scan_list = ask_allergens("   Flagged allergens (numbers, or 0 if it said safe): ")
            scan = ask_severities(scan_list)
            if name in real_answers:
                real = real_answers[name]
            else:
                print("\n  This image is NOT in your ground truth yet. Read the label yourself.")
                real_list = ask_allergens("   Allergens really on the label (numbers, or 0 for none): ")
                real = ask_severities(real_list)
                new_gt_row = [
                    name, ALL_DECLARED,
                    ",".join(sorted(real)) if real else "none",
                    ";".join(f"{a}:{s}" for a, s in sorted(real.items())),
                ]
        except Redo:
            print("\n  OK, starting this image again.\n")
            continue
        except Back:
            rows = read_rows(PROGRESS)
            if len(rows) > 1:
                prev = rows.pop()
                write_rows(PROGRESS, rows)
                print(f"\n  Going back to {prev[0]}. Its new answer was deleted.\n")
            else:
                print("\n  Nothing to go back to. Starting this image again.\n")
            continue

        notes = compare(scan, real)
        verdict = "MATCH" if not notes else " | ".join(notes)
        print("\n   Result:", verdict)

        if new_gt_row:
            with open(gt, "a", newline="", encoding="utf-8") as f:
                csv.writer(f).writerow(new_gt_row)
            real_answers[name] = real
            print(f"   (Added {name} to {gt})")
        with open(PROGRESS, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow([name, fmt(scan), fmt(real), verdict])

    shutil.copyfile(PROGRESS, LOG_FILE)
    print("\nAll images done.")
    print(f"New scan-vs-real notes are in {LOG_FILE}. The old one is saved as {LOG_BACKUP}.")
    print("Your ground truth file was not changed (except for any new image).")
    print("Next: rename evaluation_results.csv and run the evaluation again.")


if __name__ == "__main__":
    main()