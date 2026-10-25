"""
Helper to add new label images to the ground truth CSV without typing rows by hand.

It finds images that are not in the CSV yet, opens each one, and asks you:
  1. which allergies to pretend the user declared (type numbers)
  2. which of those are really on the label (type numbers)
  3. severity for each one that is present
Then it writes the row for you. Progress is saved after every image.
Type q at any question to stop. Run it again later to continue.
"""
import csv
import os
import re
import sys

BIG9 = ["milk", "egg", "peanut", "tree nut", "soy", "wheat", "fish", "shellfish", "sesame"]
IMG_EXT = (".jpg", ".jpeg", ".png")
SKIP_DIRS = {"venv", ".venv", ".git", "__pycache__", "node_modules", "web"}


def find_ground_truth():
    for name in os.listdir("."):
        if name.lower().endswith(".csv"):
            try:
                with open(name, encoding="utf-8") as f:
                    if f.readline().strip().lower().startswith("image,declared_allergies"):
                        return name
            except Exception:
                pass
    return None


def natural_key(s):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]


IMAGE_FOLDER = "test_images"   # only this folder is scanned
NAME_PREFIX = "label"          # only files starting with this are used


def find_images():
    if not os.path.isdir(IMAGE_FOLDER):
        print(f"Could not find a folder called '{IMAGE_FOLDER}' here. Check IMAGE_FOLDER at the top of this script.")
        sys.exit(1)
    found = {}
    for root, dirs, files in os.walk(IMAGE_FOLDER):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
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


def pick_numbers(prompt, allowed):
    """allowed = list of allergen names the numbers refer to (numbered from the BIG9 list)."""
    while True:
        ans = ask(prompt)
        if ans in ("", "none", "0"):
            return []
        try:
            nums = sorted({int(x) for x in re.split(r"[,\s]+", ans) if x})
        except ValueError:
            print("  Type numbers like 1,3,5")
            continue
        if all(1 <= n <= 9 for n in nums):
            chosen = [BIG9[n - 1] for n in nums]
            if all(c in allowed for c in chosen):
                return chosen
            print("  That allergen is not in the declared list. Try again.")
        else:
            print("  Numbers must be between 1 and 9.")


def main():
    gt = find_ground_truth()
    if not gt:
        print("Could not find the ground truth CSV in this folder. Run this from the SmartScan folder.")
        sys.exit(1)

    with open(gt, newline="", encoding="utf-8") as f:
        done = {row["image"] for row in csv.DictReader(f)}

    images = find_images()
    todo = sorted([n for n in images if n not in done], key=natural_key)
    print(f"Ground truth file: {gt}")
    print(f"{len(done)} images already labelled. {len(todo)} new images to label.\n")
    if not todo:
        print("Nothing to do.")
        return

    # make sure the file ends with a newline before appending
    with open(gt, "rb") as f:
        data = f.read()
    if data and not data.endswith(b"\n"):
        with open(gt, "ab") as f:
            f.write(b"\n")

    menu = "   ".join(f"{i + 1}={a}" for i, a in enumerate(BIG9))
    for idx, name in enumerate(todo, 1):
        print("=" * 60)
        print(f"Image {idx} of {len(todo)}: {name}")
        try:
            os.startfile(images[name])  # opens the picture on Windows
        except Exception:
            print(f"  (Open this picture yourself: {images[name]})")
        print(menu)
        declared = pick_numbers("Declared allergies to test (numbers, e.g. 1,3,5): ", BIG9)
        if not declared:
            print("  You need at least one declared allergy. Skipping this image.")
            continue
        print("  Declared:", ", ".join(declared))
        numbers_for_declared = " ".join(f"{BIG9.index(a) + 1}={a}" for a in declared)
        print("  ", numbers_for_declared)
        present = pick_numbers(
            "Which of these are REALLY on the label? (numbers, or press Enter for none): ", declared
        )

        sev_parts = []
        for a in sorted(present):
            s = ask(f"  Severity for {a}? Enter = Severe (in ingredients), m = Moderate (may contain/factory): ")
            sev_parts.append(f"{a}:{'Moderate' if s.startswith('m') else 'Severe'}")

        row = [
            name,
            ",".join(sorted(declared)),
            ",".join(sorted(present)) if present else "none",
            ";".join(sev_parts),
        ]
        with open(gt, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow(row)
        print("  Saved:", row)

    print("\nAll done. Now rename evaluation_results.csv and run evaluate.py.")


if __name__ == "__main__":
    main()