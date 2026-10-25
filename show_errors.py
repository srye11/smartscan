"""
Show WHY each mistake happened.

It reads evaluation_results.csv, finds every image with a false alarm or a miss, runs the
detector on that image again (all 9 allergies declared), and prints:
  - for each FALSE ALARM: the exact quoted_text the AI used as "proof"
  - for each MISS: what the AI did flag instead
Everything is also saved to errors_report.txt so you can send it.

Run from the SmartScan folder:   python show_errors.py
Note: this makes one AI call per image with a mistake (about 16 calls).
"""
import csv
import json
import os
import sys

from detector import detect_allergens

RESULTS = "evaluation_results.csv"
IMAGE_FOLDER = "test_images"
ALL9 = ["egg", "fish", "milk", "peanut", "sesame", "shellfish", "soy", "tree nut", "wheat"]
OUT = "errors_report.txt"


def split(s):
    return [x.strip() for x in (s or "").split(",") if x.strip()]


def find_image(name):
    for root, _d, files in os.walk(IMAGE_FOLDER):
        if name in files:
            return os.path.join(root, name)
    return None


def main():
    if not os.path.exists(RESULTS):
        print(f"Cannot find {RESULTS} in this folder.")
        sys.exit(1)
    with open(RESULTS, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    lines = []

    def out(s=""):
        print(s)
        lines.append(s)

    bad = [r for r in rows if split(r["false_positives"]) or split(r["false_negatives"])]
    out(f"{len(bad)} images have at least one mistake.\n")

    for r in bad:
        name = r["image"]
        fps = split(r["false_positives"])
        fns = split(r["false_negatives"])
        path = find_image(name)
        out("=" * 64)
        out(name)
        out(f"  Really on label (your answer key): {r['actual'] or 'none'}")
        if not path:
            out("  (image file not found, skipped)")
            continue
        try:
            res = detect_allergens(path, ALL9)
        except Exception as e:
            out(f"  (AI call failed: {e})")
            continue
        if not res:
            out("  (AI did not return a readable answer)")
            continue
        if res.get("unreadable"):
            out("  AI says: UNREADABLE")
        flagged = {f.get("allergen", "").lower(): f for f in res.get("flagged_allergens", [])}
        for a in fps:
            f = flagged.get(a)
            if f:
                out(f"  FALSE ALARM  {a} ({f.get('severity')})")
                out(f"      quote: \"{f.get('quoted_text')}\"")
                out(f"      why:   {f.get('explanation')}")
            else:
                out(f"  FALSE ALARM  {a}  (not flagged this time, the AI is not fully consistent)")
        for a in fns:
            if a in flagged:
                out(f"  MISS         {a}  (flagged this time, the AI is not fully consistent)")
            else:
                out(f"  MISS         {a}  (still not flagged)")
        out(f"  AI flagged this time: {', '.join(flagged) or 'nothing'}")
        for d in res.get("dropped_by_guard", []) or []:
            real = d.get("allergen") in split(r["actual"])
            tag = "!! REAL ALLERGEN REMOVED BY THE CHECK" if real else "removed (correctly, not on label)"
            out(f"  GUARD DROPPED {d.get('allergen')}: \"{d.get('quoted_text')}\"  -> {tag}")
        for d in res.get("added_by_guard", []) or []:
            real = d.get("allergen") in split(r["actual"])
            tag = "correct, it is on the label" if real else "!! FALSE ADD, not on the label"
            out(f"  GUARD ADDED   {d.get('allergen')}: \"{d.get('quoted_text')}\"  -> {tag}")
    out("=" * 64)

    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"\nSaved to {OUT}")


if __name__ == "__main__":
    main()
