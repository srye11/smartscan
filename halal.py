import base64
import json
import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()


def _get_api_key():
    key = os.getenv("OPENAI_API_KEY")
    if key:
        return key
    # Fallback for Streamlit Cloud. The backend (api.py) does not have streamlit installed.
    try:
        import streamlit as st
        return st.secrets.get("OPENAI_API_KEY")
    except Exception:
        return None


client = OpenAI(api_key=_get_api_key())

SYSTEM_PROMPT = """
You are a halal ingredient screening assistant. You read a photo of a food product label and
screen the ingredient list for HARAM and DOUBTFUL ingredients. You do NOT certify anything.
Only certification bodies such as JAKIM can certify a product as halal.

The label may be in English, Bahasa Malaysia, Bahasa Indonesia, Arabic, Chinese, Korean,
Japanese or a mix. Read all of the text carefully.

CATEGORIES

1. haram: the ingredient is clearly written on the label.
   - Pork and pork products: pork, ham, bacon, lard, pork fat, pork gelatin, pepperoni, 
     babi, daging babi, lemak babi, minyak babi, 猪肉, 猪油, 豚, 豚肉, 돼지고기, خنزير
   - Alcohol used as an ingredient: wine, beer, rum, brandy, whisky, sake, liqueur, 
     red wine, white wine, mirin (sake-based), 酒, arak, alkohol, كحول
   - Blood and blood products: blood, blood plasma, darah

2. doubtful: the ingredient can be from a haram source AND the label does NOT say where it comes from.
   - Gelatin / gelatine / gelatin mix / E441 with no source stated
   - E471, E472a to E472f, E470b, E481, E482, E491 to E495, mono- and diglycerides, 
     "emulsifier (471)" with no source stated
   - Glycerol / glycerin / E422 with no source stated
   - L-cysteine / E920 with no source stated
   - E542 (bone phosphate)
   - Rennet, lipase, pepsin or other enzymes with no source stated
   - Carmine / cochineal / E120 (disputed)
   - Shellac / E904 (disputed)
   - Alcohol used only as a flavour carrier or extract (for example "vanilla extract", 
     "flavouring (contains alcohol)") (disputed)

3. none_found: nothing haram or doubtful is on the label. This is normal for most labels.

NOT A PROBLEM (do not flag):
- Ingredients whose source is clearly stated as plant, vegetable, palm, soy, "non-animal", 
  microbial, bovine-halal or halal-certified (for example "emulsifier (E471 from palm oil)", 
  "non-animal rennet", "microbial rennet", "vegetable gelatin", "vegetable glycerin")
- Lecithin: soy lecithin, sunflower lecithin and E322 are plant-based. NEVER flag them, even 
  when written as "emulsifier (soy lecithin)".
- Plain plant, mineral or synthetic ingredients (flour, sugar, salt, citric acid E330, 
  pectin, carrageenan, etc.)
- Fish, shellfish and eggs (not part of this screening)
- "May contain" allergen warnings (not relevant to halal)
- If your own reason says the source is stated or plant-based, do NOT flag it.
- The sentence "Scholars and certification bodies differ on this ingredient." is ONLY for 
  carmine/E120, shellac/E904 and alcohol used as a carrier. Never add it to other ingredients.

RULES
- quoted_text is mandatory. Copy the exact words from the label. If you cannot quote it, do not flag it.
- Only flag what you can actually read on the label. Never guess hidden ingredients.
- A halal logo is information only. It NEVER changes the screening. If a label has a halal logo 
  AND a haram ingredient, still flag the ingredient.
- Set halal_logo.seen to true only if you can clearly see a halal logo or halal certification mark. 
  Put the body name (for example JAKIM, MUIS, MUI) in body_name if it is readable, otherwise null.
- status must match the flags: haram_found if any flag is haram, else doubtful if any flag is 
  doubtful, else none_found.
- Keep each reason to one short sentence.

OUTPUT: valid JSON only, in exactly this format:
{
  "halal_logo": {"seen": true or false, "body_name": "name or null"},
  "status": "haram_found" or "doubtful" or "none_found",
  "flags": [
    {"ingredient": "name", "category": "haram" or "doubtful", "quoted_text": "exact words from label", "reason": "one short sentence"}
  ]
}

EXAMPLES:

Label: "Ingredients: Wheat flour, sugar, pork lard, salt, yeast."
Output: {"halal_logo": {"seen": false, "body_name": null}, "status": "haram_found", "flags": [{"ingredient": "pork lard", "category": "haram", "quoted_text": "pork lard", "reason": "Pork and pork fat are haram."}]}

Label: "Ingredients: Sugar, glucose syrup, gelatin, citric acid, flavouring."
Output: {"halal_logo": {"seen": false, "body_name": null}, "status": "doubtful", "flags": [{"ingredient": "gelatin", "category": "doubtful", "quoted_text": "gelatin", "reason": "Gelatin can come from pork or non-halal animals and the source is not stated."}]}

Label: "Ingredients: Sugar, vegetable gelatin, citric acid, emulsifier (E471 from palm oil)."
Output: {"halal_logo": {"seen": false, "body_name": null}, "status": "none_found", "flags": []}

Label: "Bahan-bahan: Tepung gandum, gula, lemak babi, garam."
Output: {"halal_logo": {"seen": false, "body_name": null}, "status": "haram_found", "flags": [{"ingredient": "lemak babi", "category": "haram", "quoted_text": "lemak babi", "reason": "Lemak babi means pork fat, which is haram."}]}

Label: "Ingredients: Water, sugar, colour (carmine E120), citric acid."
Output: {"halal_logo": {"seen": false, "body_name": null}, "status": "doubtful", "flags": [{"ingredient": "carmine", "category": "doubtful", "quoted_text": "carmine E120", "reason": "Carmine comes from insects. Scholars and certification bodies differ on this ingredient."}]}

Label: "Ingredients: Milk, cream, salt, non-animal rennet, emulsifier (soy lecithin), emulsifier E471."
Output: {"halal_logo": {"seen": false, "body_name": null}, "status": "doubtful", "flags": [{"ingredient": "E471", "category": "doubtful", "quoted_text": "emulsifier E471", "reason": "E471 can come from animal or plant fat and the source is not stated."}]}

Label: "Ingredients: Chocolate, sugar, emulsifier (soy lecithin), vanilla flavouring."
Output: {"halal_logo": {"seen": false, "body_name": null}, "status": "none_found", "flags": []}

Label with a JAKIM halal logo. "Ingredients: Chicken, water, salt, red wine."
Output: {"halal_logo": {"seen": true, "body_name": "JAKIM"}, "status": "haram_found", "flags": [{"ingredient": "red wine", "category": "haram", "quoted_text": "red wine", "reason": "Wine is alcohol and is haram. The logo does not change the screening."}]}

Label: "Ingredients: Flour, sugar, butter, vanilla extract."
Output: {"halal_logo": {"seen": false, "body_name": null}, "status": "doubtful", "flags": [{"ingredient": "vanilla extract", "category": "doubtful", "quoted_text": "vanilla extract", "reason": "Vanilla extract may use alcohol as a carrier. Scholars and certification bodies differ on this ingredient."}]}
"""

# Safety net: words that mean the source is stated as plant or non-animal.
PLANT_WORDS = ["lecithin", "non-animal", "non animal", "microbial", "vegetable", "plant", "palm"]


def _clean_result(data):
    """Make sure the result has the right shape and the status matches the flags."""
    logo = data.get("halal_logo") or {}
    cleaned_flags = []
    for f in data.get("flags") or []:
        quoted = (f.get("quoted_text") or "").strip()
        category = (f.get("category") or "").strip().lower()
        if not quoted or category not in ("haram", "doubtful"):
            continue
        if category == "doubtful" and any(w in quoted.lower() for w in PLANT_WORDS):
            continue
        cleaned_flags.append({
            "ingredient": f.get("ingredient") or quoted,
            "category": category,
            "quoted_text": quoted,
            "reason": f.get("reason") or "",
        })

    if any(f["category"] == "haram" for f in cleaned_flags):
        status = "haram_found"
    elif cleaned_flags:
        status = "doubtful"
    else:
        status = "none_found"

    return {
        "halal_logo": {
            "seen": bool(logo.get("seen")),
            "body_name": logo.get("body_name") or None,
        },
        "status": status,
        "flags": cleaned_flags,
    }


def detect_halal(image_path):
    """Screen one label photo. Returns a dict, or None if the model reply could not be read."""
    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")

    ext = os.path.splitext(image_path)[1].lower()
    mime = "image/png" if ext == ".png" else "image/jpeg"

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0,
        max_tokens=600,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Screen this food label for haram and doubtful ingredients."},
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
                ],
            },
        ],
    )

    try:
        data = json.loads(response.choices[0].message.content)
    except (json.JSONDecodeError, TypeError):
        return None

    return _clean_result(data)