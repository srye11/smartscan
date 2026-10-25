from halal import scan_text

def tiers(t):
    r = scan_text(t)
    return r["status"], [(i["tier"], i["ingredient"]) for i in r["flagged_items"]]

cases = [
 ("Ingredients: Sugar, gelatin (beef), citric acid, colour (E120).", "Syubhah"),
 ("Ramuan: Tepung gandum, lemak babi, garam.", "Haram"),
 ("Ingredients: Rice, salt, chicken flavour, sugar", "Warning"),
 ("Ingredients: Rice, salt, sugar, palm oil", "Clear"),
 ("Ingredients: Fish gelatin, sugar", "Clear"),
 ("Ingredients: chickpeas, hamburger bun, ginger beer, root beer, goat milk powder", "Clear"),
 ("Ingredients: Emulsifier (471), sugar", "Syubhah"),
 ("Pengemulsi (E471), gula", "Syubhah"),
 ("Contains wine vinegar, coconut oil", "Clear"),
 ("Ingredients: pork, ham, bacon", "Haram"),
 ("Ingredients: Vegetable glycerine, water", "Clear"),
 ("Ingredients: glycerine, water", "Syubhah"),
 ("Flavour (contains alcohol), sugar", "Syubhah"),
 ("Sugar-free, fatty alcohol, sugar alcohol", "Clear"),
 ("Daging ayam, kicap, bebas babi", "Warning"),
 ("Ingredients: beef tallow, mono- and diglycerides of fatty acids", "Syubhah"),
 ("Meat-free burger with vegan chicken", "Clear"),
 ("Dark rum, sugar", "Haram"),
 ("Ingredients: Ginger, spices, rennet", "Syubhah"),
]
bad = 0
for t, want in cases:
    st, items = tiers(t)
    ok = st == want
    bad += not ok
    print("OK " if ok else "BAD", want, "<-", st, items, "|", t[:50])
r = scan_text("Ingredients: sugar, gelatin (beef, halal), chicken extract, chicken fat, babi")
for i in r["flagged_items"]: print(i["tier"], i["ingredient"], "|", i["quoted_text"])
print("failures:", bad)