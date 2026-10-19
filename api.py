import io
import json
import logging
import os
import tempfile
import uuid

import requests
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from PIL import Image, ImageOps
from pydantic import BaseModel
from supabase import create_client

# client and SYSTEM_PROMPT are reused for the typed-ingredients mode,
# so photo scans and text scans follow exactly the same rules.
from detector import detect_allergens, client, SYSTEM_PROMPT, clean_result

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
BUCKET = "scan-images"
BIG9 = ["Milk", "Egg", "Peanut", "Tree Nut", "Soy", "Wheat", "Fish", "Shellfish", "Sesame"]
REPORT_KINDS = ["false_alarm", "missed", "wrong_severity", "other"]
MAX_TEXT = 4000

supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)

app = FastAPI(title="SmartScan API")

# Open for now. We restrict this to your real website later.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

bearer = HTTPBearer()


def get_user(creds: HTTPAuthorizationCredentials = Depends(bearer)):
    """Check the login token with Supabase and return the user."""
    r = requests.get(
        f"{SUPABASE_URL}/auth/v1/user",
        headers={"Authorization": f"Bearer {creds.credentials}", "apikey": SUPABASE_ANON_KEY},
        timeout=10,
    )
    if r.status_code != 200:
        raise HTTPException(status_code=401, detail="Invalid or expired login")
    return r.json()


def get_profile(user):
    res = supabase.table("profiles").select("*").eq("id", user["id"]).execute()
    if res.data:
        return res.data[0]
    new = {
        "id": user["id"],
        "full_name": (user.get("user_metadata") or {}).get("full_name"),
        "allergies": [],
    }
    supabase.table("profiles").insert(new).execute()
    return new


def prepare_image(raw: bytes) -> bytes:
    """Fix iPhone rotation, shrink big photos, convert to JPEG."""
    img = Image.open(io.BytesIO(raw))
    img = ImageOps.exif_transpose(img)
    img = img.convert("RGB")
    img.thumbnail((1600, 1600))
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=85)
    return out.getvalue()


def detect_allergens_text(text, allergies):
    """Same rules and model as detect_allergens(), but the ingredients come as typed text."""
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0,
        max_tokens=600,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Declared allergies: {', '.join(allergies)}\n\n"
                    "The ingredient list was typed in as text instead of a photo. "
                    "Check only the text between the markers.\n"
                    f"<<<INGREDIENTS\n{text}\nINGREDIENTS>>>"
                ),
            },
        ],
    )
    raw = (response.choices[0].message.content or "").strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.lower().startswith("json"):
            raw = raw[4:]
    try:
        return clean_result(json.loads(raw), allergies)
    except json.JSONDecodeError:
        logging.warning("Model did not return clean JSON for text scan: %s", raw[:200])
        return None


class ProfileIn(BaseModel):
    full_name: str | None = None
    allergies: list[str] = []


class TextIn(BaseModel):
    text: str


class ReportIn(BaseModel):
    scan_id: int
    kind: str
    allergen: str | None = None
    note: str | None = None


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/profile")
def read_profile(user=Depends(get_user)):
    return get_profile(user)


@app.put("/profile")
def update_profile(body: ProfileIn, user=Depends(get_user)):
    bad = [a for a in body.allergies if a not in BIG9]
    if bad:
        raise HTTPException(status_code=400, detail=f"Unknown allergens: {bad}")
    get_profile(user)  # makes sure the row exists
    data = {"allergies": body.allergies}
    if body.full_name:
        data["full_name"] = body.full_name
    supabase.table("profiles").update(data).eq("id", user["id"]).execute()
    return get_profile(user)


@app.post("/scan")
def scan(file: UploadFile = File(...), user=Depends(get_user)):
    raw = file.file.read()
    if len(raw) > 15 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Image too large (max 15MB)")
    try:
        jpeg = prepare_image(raw)
    except Exception:
        raise HTTPException(status_code=400, detail="Could not read this image file")

    allergies = get_profile(user)["allergies"]
    if not allergies:
        raise HTTPException(status_code=400, detail="Set at least one allergy in your profile first")

    tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
    try:
        tmp.write(jpeg)
        tmp.close()
        allergen_result = detect_allergens(tmp.name, allergies)
    except Exception:
        logging.exception("AI call failed")
        raise HTTPException(status_code=502, detail="The AI service had a problem. Please try again.")
    finally:
        os.unlink(tmp.name)

    if allergen_result is None:
        raise HTTPException(status_code=502, detail="Could not read the label clearly. Please retake the photo.")

    # The AI says it cannot read the ingredient text. Never show that as a normal result.
    if allergen_result.get("unreadable"):
        raise HTTPException(
            status_code=422,
            detail="Could not read the ingredient text clearly. Please retake the photo closer and flatter, or use Type ingredients.",
        )

    path = f"{user['id']}/{uuid.uuid4().hex}.jpg"
    supabase.storage.from_(BUCKET).upload(path, jpeg, {"content-type": "image/jpeg"})
    row = {
        "user_id": user["id"],
        "image_path": path,
        "allergen_result": allergen_result,
    }
    saved = supabase.table("scans").insert(row).execute().data[0]
    return {"id": saved["id"], "allergen_result": allergen_result}


@app.post("/scan-text")
def scan_text(body: TextIn, user=Depends(get_user)):
    text = body.text.strip()
    if len(text) < 3:
        raise HTTPException(status_code=400, detail="Type or paste the ingredient list first")
    if len(text) > MAX_TEXT:
        raise HTTPException(status_code=400, detail=f"Text is too long (max {MAX_TEXT} characters)")

    allergies = get_profile(user)["allergies"]
    if not allergies:
        raise HTTPException(status_code=400, detail="Set at least one allergy in your profile first")

    try:
        allergen_result = detect_allergens_text(text, allergies)
    except Exception:
        logging.exception("AI call failed (text)")
        raise HTTPException(status_code=502, detail="The AI service had a problem. Please try again.")

    if allergen_result is None:
        raise HTTPException(status_code=502, detail="Could not read the result. Please try again.")

    row = {
        "user_id": user["id"],
        "image_path": None,
        "input_text": text,
        "allergen_result": allergen_result,
    }
    saved = supabase.table("scans").insert(row).execute().data[0]
    return {"id": saved["id"], "allergen_result": allergen_result}


@app.post("/report")
def report(body: ReportIn, user=Depends(get_user)):
    if body.kind not in REPORT_KINDS:
        raise HTTPException(status_code=400, detail="Unknown report type")
    if body.allergen and body.allergen not in BIG9:
        raise HTTPException(status_code=400, detail="Unknown allergen")
    note = (body.note or "").strip()[:500] or None

    res = (
        supabase.table("scans")
        .select("id, allergen_result, input_text")
        .eq("id", body.scan_id)
        .eq("user_id", user["id"])
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=404, detail="Scan not found")
    scan_row = res.data[0]

    supabase.table("reports").insert(
        {
            "user_id": user["id"],
            "scan_id": scan_row["id"],
            "kind": body.kind,
            "allergen": body.allergen,
            "note": note,
            "result_snapshot": scan_row["allergen_result"],
            "input_text": scan_row.get("input_text"),
        }
    ).execute()
    return {"ok": True}


@app.get("/scans")
def list_scans(user=Depends(get_user)):
    rows = (
        supabase.table("scans").select("*").eq("user_id", user["id"]).order("id", desc=True).execute().data
    )
    for r in rows:
        r["image_url"] = None
        if r.get("image_path"):
            try:
                signed = supabase.storage.from_(BUCKET).create_signed_url(r["image_path"], 3600)
                r["image_url"] = signed.get("signedURL") or signed.get("signedUrl")
            except Exception:
                pass
    return rows


@app.delete("/scans/{scan_id}")
def delete_scan(scan_id: int, user=Depends(get_user)):
    res = (
        supabase.table("scans").select("image_path").eq("id", scan_id).eq("user_id", user["id"]).execute()
    )
    if not res.data:
        raise HTTPException(status_code=404, detail="Scan not found")
    if res.data[0].get("image_path"):
        supabase.storage.from_(BUCKET).remove([res.data[0]["image_path"]])
    supabase.table("scans").delete().eq("id", scan_id).eq("user_id", user["id"]).execute()
    return {"deleted": scan_id}