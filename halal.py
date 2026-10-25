"""
SmartScan halal check.

How it works (two separate jobs):
  1. The AI only READS the label (photo -> plain text). It is not asked to judge halal or haram.
  2. Plain Python word lists (below) decide what is Haram, Syubhah (doubtful) or a meat Warning.

Why: the rules are fixed and can be checked, explained and changed by you or your supervisor in one
place, and the answer does not change from one scan to the next (a typed list uses no AI at all).

THIS IS NOT A HALAL CERTIFICATE. It only points out ingredient words that need attention. The
only real proof is a valid JAKIM / recognised halal logo on the pack.

Tiers:
  Haram    pork / pig products, alcoholic drinks, blood
  Syubhah  doubtful: source not stated or not clear (gelatin, carmine, E471, glycerine, ...)
  Warning  chicken / beef / any meat: the way the animal was slaughtered is not stated on the label

!! The lists below are a starting point. Check them against JAKIM / fatwa sources and have your
   supervisor approve them before you write them in the report.
"""
import json
import re

TIER_ORDER = {"Haram": 0, "Syubhah": 1, "Warning": 2}
STATUS_TEXT = {
    "Haram": "Contains an ingredient that is haram",
    "Syubhah": "Contains a doubtful (syubhah) ingredient",
    "Warning": "Meat ingredient: slaughter method not stated",
    "Clear": "No haram, doubtful or meat ingredient words found",
}


def _num(n):
    """E-number written as E471, E 471 or (471)."""
    return rf"re:(?<![a-z0-9])(?:e\s?|\(\s?){n}(?![0-9a-z])"


# key, tier, label, terms (plain words, or "re:" raw regex), neutral phrases, explanation
GROUPS = [
    # ------------------------------------------------------------------ HARAM
    {
        "key": "pork", "tier": "Haram", "label": "Pork / pig",
        "terms": ["pork", "babi", "pig", "swine", "bacon", "ham", "gammon", "pancetta", "prosciutto",
                  "lard", "lemak babi", "minyak babi", "daging babi"],
        "neutral": ["pork free", "pork-free", "no pork", "contains no pork", "bebas babi", "tanpa babi",
                    "tiada babi", "guinea pig"],
        "why": "Pork and pig products are haram.",
    },
    {
        "key": "alcohol_drink", "tier": "Haram", "label": "Alcoholic drink",
        "terms": ["wine", "wain", "beer", "bir", "rum", "whisky", "whiskey", "brandy", "vodka", "liquor",
                  "liqueur", "sake", "arak", "tuak", "cider", "sherry", "champagne", "gin", "mirin"],
        "neutral": ["root beer", "ginger beer", "wine vinegar", "cuka wain", "cider vinegar", "apple cider",
                    "non alcoholic", "non-alcoholic", "alcohol free", "alcohol-free"],
        "why": "An alcoholic drink is named. If it is only a flavour name (for example 'rum flavour'), "
               "check for the JAKIM halal logo.",
    },
    {
        "key": "blood", "tier": "Haram", "label": "Blood",
        "terms": ["blood", "darah"],
        "neutral": ["blood orange"],
        "why": "Blood is haram.",
    },
    # ---------------------------------------------------------------- SYUBHAH
    {
        "key": "gelatin", "tier": "Syubhah", "label": "Gelatin / collagen",
        "terms": ["gelatin", "gelatine", "gelatina", "collagen", "kolagen", _num(441)],
        "neutral": ["fish gelatin", "fish gelatine", "gelatin ikan", "gelatine ikan", "fish collagen",
                    "marine collagen", "kolagen ikan"],
        "why": "Gelatin often comes from pork or from cattle that were not slaughtered the halal way. "
               "The source is not stated.",
    },
    {
        "key": "carmine", "tier": "Syubhah", "label": "Carmine / cochineal",
        "terms": ["carmine", "cochineal", "carminic", "karmin", _num(120)],
        "neutral": [],
        "why": "A red colour made from insects. Scholars differ on whether it is halal.",
    },
    {
        "key": "cysteine", "tier": "Syubhah", "label": "L-cysteine",
        "terms": ["l-cysteine", "l cysteine", "cysteine", "sistein", _num(920)],
        "neutral": [],
        "why": "Can be made from animal hair or feathers, sometimes from non-halal sources.",
    },
    {
        "key": "emulsifier", "tier": "Syubhah", "label": "Emulsifier of unstated source",
        "terms": ["mono and diglycerides", "mono- and diglycerides", "mono-diglycerides", "monoglycerides",
                  "diglycerides", "monogliserida", "digliserida", "pengemulsi lemak",
                  _num(471), _num(470), _num(472)],
        "neutral": [],
        "why": "Fatty-acid emulsifiers can come from plants or from animal fat. The label does not say which.",
    },
    {
        "key": "glycerine", "tier": "Syubhah", "label": "Glycerine / glycerol of unstated source",
        "terms": ["glycerine", "glycerin", "glycerol", "gliserin", "gliserol", _num(422)],
        "neutral": ["vegetable glycerine", "vegetable glycerin", "vegetable glycerol", "plant glycerin",
                    "gliserin sayuran", "gliserol sayuran"],
        "why": "Glycerine can come from plants or from animal fat. The label does not say which.",
    },
    {
        "key": "rennet", "tier": "Syubhah", "label": "Rennet / pepsin",
        "terms": ["rennet", "rennin", "pepsin", "renet"],
        "neutral": ["microbial rennet", "vegetable rennet", "vegetarian rennet", "fungal rennet",
                    "non-animal rennet"],
        "why": "Cheese enzymes can come from calves that were not slaughtered the halal way.",
    },
    {
        "key": "animal_fat", "tier": "Syubhah", "label": "Animal fat",
        "terms": ["animal fat", "animal oil", "tallow", "suet", "dripping", "lemak haiwan", "minyak haiwan"],
        "neutral": [],
        "why": "The animal and the way it was slaughtered are not stated.",
    },
    {
        "key": "alcohol_ingredient", "tier": "Syubhah", "label": "Alcohol / ethanol",
        "terms": ["alcohol", "ethanol", "ethyl alcohol", "alkohol", "etanol"],
        "neutral": ["alcohol free", "alcohol-free", "non alcoholic", "non-alcoholic", "fatty alcohol",
                    "sugar alcohol", "benzyl alcohol", "cetyl alcohol", "cetearyl alcohol",
                    "stearyl alcohol", "polyvinyl alcohol", "bebas alkohol", "tanpa alkohol"],
        "why": "Alcohol is named as an ingredient (often a flavour carrier). Check the JAKIM halal logo.",
    },
    {
        "key": "bone", "tier": "Syubhah", "label": "Bone-derived ingredient",
        "terms": ["bone phosphate", "bone char", "bone meal", "tulang", _num(542)],
        "neutral": [],
        "why": "Made from animal bones. The animal and slaughter method are not stated.",
    },
    # ------------------------------------------------- WARNING (meat, slaughter unknown)
    {
        "key": "meat", "tier": "Warning", "label": "Meat",
        "terms": ["chicken", "ayam", "beef", "lembu", "daging", "mutton", "kambing", "lamb", "goat", "duck",
                  "itik", "turkey", "meat", "poultry", "unggas", "veal", "venison", "rusa", "buffalo",
                  "kerbau", "sausage", "sosej", "bone broth"],
        "neutral": ["meat free", "meat-free", "meatless", "goat milk", "goat's milk", "goat cheese",
                    "goat's cheese", "susu kambing", "vegan chicken", "vegetarian chicken",
                    "plant-based chicken", "plant based chicken", "vegan beef", "vegetarian beef",
                    "meat alternative", "meat substitute", "meat analogue", "meat analog",
                    "lamb's lettuce"],
        "why": "The label does not say how the animal was slaughtered. Look for a valid halal logo.",
    },
]

_FLAVOUR = re.compile(r"flavou?r|perisa|essence|seasoning|perasa", re.I)


def _compile_term(t):
    if t.startswith("re:"):
        return t[3:]
    p = re.escape(t.lower()).replace(r"\ ", r"[\s\-]+")
    return rf"(?<![a-z0-9]){p}(?:s|es)?(?![a-z])"


for _g in GROUPS:
    _g["rx"] = re.compile("|".join(f"(?:{_compile_term(t)})" for t in _g["terms"]))
    _g["neutral_rx"] = (
        re.compile("|".join(re.escape(n).replace(r"\ ", r"[\s\-]+") for n in _g["neutral"]))
        if _g["neutral"] else None
    )


def _segments(text):
    """Split into (start, end) pieces at commas / semicolons / full stops / new lines, but not
    inside brackets, so 'Gelatin (Beef, Halal)' stays together."""
    spans, depth, start = [], 0, 0
    for i, ch in enumerate(text):
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth = max(0, depth - 1)
        elif depth == 0 and (ch in ",;\n•" or (ch == "." and text[i + 1:i + 2] in (" ", "\n", ""))):
            spans.append((start, i))
            start = i + 1
    spans.append((start, len(text)))
    return spans


def _quote_for(text, pos, spans):
    for s, e in spans:
        if s <= pos <= e:
            seg = text[s:e].strip(" \t\r\n.,;:•-")
            if len(seg) > 140:  # one huge sentence with no commas: cut around the word
                a = max(0, pos - s - 60)
                seg = text[s:e][a:a + 120].strip()
                seg = ("…" if a > 0 else "") + seg + "…"
            return seg
    return text[max(0, pos - 40):pos + 40].strip()


def scan_text(text):
    """Rule-based check of an ingredient text. Returns the halal result dict."""
    text = (text or "").replace("\r", "\n")
    low = text.lower()
    spans = _segments(text)
    items, seen = [], set()
    for g in GROUPS:
        masked = low
        if g["neutral_rx"]:
            # blank the harmless phrase out but keep every position the same
            masked = g["neutral_rx"].sub(lambda m: " " * len(m.group(0)), masked)
        for m in g["rx"].finditer(masked):
            word = re.sub(r"\s+", " ", m.group(0)).strip(" ()").lower()
            key = (g["key"], word if g["key"] == "meat" else "")
            if key in seen:
                continue
            seen.add(key)
            quote = _quote_for(text, m.start(), spans)
            why = g["why"]
            if g["key"] == "meat" and _FLAVOUR.search(quote):
                why += " It is written as a flavour, which may be artificial, but the label does not say so."
            items.append({
                "ingredient": word if g["key"] == "meat" else g["label"],
                "group": g["key"],
                "tier": g["tier"],
                "quoted_text": quote,
                "explanation": why,
            })
    # "daging ayam" gives two meat words in the same piece of text: show them as one warning
    merged = []
    for it in items:
        same = next((m for m in merged if m["group"] == "meat" and it["group"] == "meat"
                     and m["quoted_text"] == it["quoted_text"]), None)
        if same:
            same["ingredient"] += ", " + it["ingredient"]
        else:
            merged.append(it)
    items = merged
    items.sort(key=lambda i: TIER_ORDER[i["tier"]])
    status = items[0]["tier"] if items else "Clear"
    return {
        "scan_type": "halal",
        "status": status,
        "summary": STATUS_TEXT[status],
        "flagged_items": items,
        "safe": not items,
    }


# --------------------------------------------------------------------------- AI reads the photo
READ_PROMPT = """You are a label reader. You will be shown a photo of a food product label. Labels may be
in English, Bahasa Malaysia, or both.

Your ONLY job is to copy the text. Do not judge, summarise, translate or explain.

Copy exactly, in the original spelling and language:
- the full ingredients list (Ramuan / Ingredients), including anything in brackets and E-numbers
- any sentence that starts with Contains / Mengandungi / May contain / Mungkin mengandungi /
  Processed in a facility / Diproses di kilang / Allergy advice

Rules:
- Copy only what you can actually read in THIS image. Never fill a gap from memory or guess.
- Do not copy nutrition tables, addresses, barcodes or storage advice.
- If the ingredient text is too small, blurry, curved, glared or cut off to read, set "unreadable" to true.

Respond ONLY in this JSON format, nothing else:
{"ingredients_text": "the copied text on one line", "unreadable": false}
"""


def read_label(image_path, client, encode_image):
    """Ask the AI to copy the label text. Returns the text, or None when it could not be read."""
    b64 = encode_image(image_path)
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0,
        max_tokens=900,
        messages=[
            {"role": "system", "content": READ_PROMPT},
            {"role": "user", "content": [
                {"type": "text", "text": "Copy the ingredient text from this label."},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
            ]},
        ],
    )
    raw = (response.choices[0].message.content or "").strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.lower().startswith("json"):
            raw = raw[4:]
    data = json.loads(raw)  # JSONDecodeError is handled by the caller
    if data.get("unreadable"):
        return None
    text = str(data.get("ingredients_text") or "").strip()
    return text if len(text) >= 3 else None


def detect_halal(image_path):
    """Photo -> halal result. {'unreadable': True} when the AI could not read the label."""
    from detector import client, encode_image  # imported here so tests can run without an API key

    text = read_label(image_path, client, encode_image)
    if not text:
        return {"scan_type": "halal", "unreadable": True}
    result = scan_text(text)
    result["ingredients_read"] = text[:1500]
    return result