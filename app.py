import os
import io
import json
import re
import sqlite3
from datetime import datetime, timezone

from flask import Flask, request, jsonify, render_template, g
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-key")

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
MODEL_NAME = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash").strip()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "rakshacircle.db")
LOCAL_USER_ID = 1
LOCAL_USER_NAME = "RakshaCircle User"

gemini_client = genai.Client(api_key=GEMINI_API_KEY) if GEMINI_API_KEY else None

SYSTEM_PROMPT = """You are RakshaCircle, a defensive scam-detection assistant for Indian users.

Analyze the supplied message, URL, PDF text and/or screenshot for:
- phishing and credential theft
- UPI/bank/KYC scams
- OTP/password/PIN requests
- impersonation
- fake jobs and courier scams
- investment/crypto scams
- malicious or suspicious links
- urgency, threats and social engineering

Do not claim something is definitely a scam unless the supplied evidence supports it.
If an image is supplied, inspect visible text, logos, UI and suspicious instructions.
If a PDF is supplied, analyze its extracted text.

Return ONLY valid JSON matching this structure:
{
  "risk_score": 0-100,
  "risk_label": "Safe|Low Risk|Suspicious|High Risk|Confirmed Scam Pattern",
  "language_detected": "language/script",
  "red_flags": [
    {"phrase": "short exact phrase or URL from supplied content", "reason": "why it is suspicious"}
  ],
  "explanation": "2-4 simple sentences in the user's language where possible",
  "suggested_action": "one concrete safe next step"
}

Maximum 5 red_flags. Never invent phrases or URLs that were not supplied.
"""

def now():
    return datetime.now(timezone.utc).isoformat()

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db:
        db.close()

def init_db():
    db = sqlite3.connect(DB_PATH)
    db.execute("""
        CREATE TABLE IF NOT EXISTS family_members(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            relation TEXT,
            phone TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS scan_history(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            message_snippet TEXT,
            attachment_names TEXT,
            link TEXT,
            risk_score INTEGER,
            risk_label TEXT,
            language_detected TEXT,
            alerted_family INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        )
    """)
    db.commit()
    db.close()

@app.context_processor
def inject_user():
    return {"current_user_name": LOCAL_USER_NAME}

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/logout")
def logout():
    # Login is intentionally removed; keep this route harmless for old links.
    return jsonify({"message": "Login is not required in this local prototype."})

def extract_pdf_text(data):
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data))
        parts = [(page.extract_text() or "") for page in reader.pages[:10]]
        return "\n".join(parts)[:12000]
    except Exception as exc:
        return f"[PDF text extraction failed: {exc}]"

def find_urls(text):
    return re.findall(r'https?://[^\s<>"\']+', text or "", flags=re.I)

def analyze_with_gemini(message_text, link, attachment_text, image_parts):
    if gemini_client is None:
        raise RuntimeError("GEMINI_API_KEY is missing. Add your key to .env.")

    all_urls = find_urls(message_text) + find_urls(link) + find_urls(attachment_text)

    prompt = f"""USER MESSAGE:
{message_text[:8000] or "None"}

EXPLICIT LINK FIELD:
{link[:2000] or "None"}

EXTRACTED PDF/ATTACHMENT TEXT:
{attachment_text[:12000] or "None"}

LINKS FOUND:
{", ".join(all_urls) or "None"}

Analyze all supplied evidence. Images/screenshots are supplied as image parts.
Return JSON only."""

    contents = [prompt]
    contents.extend(image_parts[:4])

    response = gemini_client.models.generate_content(
        model=MODEL_NAME,
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=0.1,
            response_mime_type="application/json",
            response_schema={
                "type": "OBJECT",
                "properties": {
                    "risk_score": {"type": "INTEGER"},
                    "risk_label": {"type": "STRING"},
                    "language_detected": {"type": "STRING"},
                    "red_flags": {
                        "type": "ARRAY",
                        "items": {
                            "type": "OBJECT",
                            "properties": {
                                "phrase": {"type": "STRING"},
                                "reason": {"type": "STRING"}
                            },
                            "required": ["phrase", "reason"]
                        }
                    },
                    "explanation": {"type": "STRING"},
                    "suggested_action": {"type": "STRING"}
                },
                "required": [
                    "risk_score",
                    "risk_label",
                    "language_detected",
                    "red_flags",
                    "explanation",
                    "suggested_action"
                ]
            }
        )
    )

    raw = (response.text or "").strip()
    if not raw:
        raise RuntimeError("Gemini returned an empty response.")

    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        raise RuntimeError("Gemini returned invalid JSON.")

    result.setdefault("risk_score", 50)
    result.setdefault("risk_label", "Suspicious")
    result.setdefault("language_detected", "Unknown")
    result.setdefault("red_flags", [])
    result.setdefault("explanation", "")
    result.setdefault("suggested_action", "")
    return result

def send_sms_alert(phone, score):
    """Optional Twilio SMS. Without Twilio credentials, alert is logged locally."""
    sid = os.environ.get("TWILIO_ACCOUNT_SID")
    token = os.environ.get("TWILIO_AUTH_TOKEN")
    from_number = os.environ.get("TWILIO_FROM_NUMBER")

    if not (sid and token and from_number):
        print(f"[SIMULATED FAMILY ALERT] To {phone}: high-risk scan, score {score}.")
        return False

    try:
        from twilio.rest import Client
        Client(sid, token).messages.create(
            body=f"RakshaCircle alert: a high-risk message was detected (score {score}). Verify before any payment or OTP sharing.",
            from_=from_number,
            to=phone
        )
        return True
    except Exception as exc:
        print(f"[SMS FAILED] {phone}: {exc}")
        return False

def alert_family(score):
    members = get_db().execute(
        "SELECT * FROM family_members WHERE user_id=?",
        (LOCAL_USER_ID,)
    ).fetchall()

    if not members:
        return False, 0

    sent = 0
    for member in members:
        if send_sms_alert(member["phone"], score):
            sent += 1

    # The app still reports that the family alert was triggered even when
    # Twilio is not configured; the local console is the prototype fallback.
    return True, sent

@app.route("/api/analyze", methods=["POST"])
def api_analyze():
    message = request.form.get("message", "").strip()
    link = request.form.get("link", "").strip()
    files = request.files.getlist("attachments")

    if not message and not link and not files:
        return jsonify({"error": "Message, link, image, screenshot, or PDF is required."}), 400

    if len(message) > 8000 or len(link) > 2000:
        return jsonify({"error": "Input is too large."}), 400

    attachment_text = []
    image_parts = []
    names = []

    for f in files[:5]:
        if not f or not f.filename:
            continue

        name = os.path.basename(f.filename)
        names.append(name)
        data = f.read()

        if len(data) > 10 * 1024 * 1024:
            return jsonify({"error": f"{name} is larger than 10 MB."}), 400

        ext = os.path.splitext(name)[1].lower()
        mime = f.mimetype or ""

        if ext == ".pdf" or mime == "application/pdf":
            attachment_text.append(f"[PDF: {name}]\n{extract_pdf_text(data)}")
        elif ext in {".png", ".jpg", ".jpeg", ".webp"} or mime.startswith("image/"):
            image_parts.append(types.Part.from_bytes(
                data=data,
                mime_type=mime or "image/jpeg"
            ))
        else:
            attachment_text.append(
                f"[Attachment: {name}] Unsupported file type; filename was supplied."
            )

    try:
        result = analyze_with_gemini(
            message,
            link,
            "\n".join(attachment_text),
            image_parts
        )
    except Exception as exc:
        return jsonify({"error": f"Gemini analysis failed: {exc}"}), 502

    try:
        score = max(0, min(100, int(result.get("risk_score", 0) or 0)))
    except (TypeError, ValueError):
        score = 50

    alerted = False
    sms_sent = 0

    if score >= 70:
        alerted, sms_sent = alert_family(score)

    db = get_db()
    db.execute("""
        INSERT INTO scan_history
        (user_id, message_snippet, attachment_names, link, risk_score,
         risk_label, language_detected, alerted_family, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        LOCAL_USER_ID,
        message[:200],
        json.dumps(names),
        link,
        score,
        result.get("risk_label", "Suspicious"),
        result.get("language_detected", "Unknown"),
        1 if alerted else 0,
        now()
    ))
    db.commit()

    result["risk_score"] = score
    result["family_alerted"] = alerted
    result["sms_sent"] = sms_sent
    result["family_notified"] = alerted
    result["attachments"] = names
    result["links_found"] = find_urls(message + " " + link + " " + "\n".join(attachment_text))
    return jsonify(result)

@app.route("/api/family", methods=["GET"])
def get_family():
    rows = get_db().execute(
        "SELECT * FROM family_members WHERE user_id=? ORDER BY created_at DESC",
        (LOCAL_USER_ID,)
    ).fetchall()
    return jsonify([dict(row) for row in rows])

@app.route("/api/family", methods=["POST"])
def add_family():
    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()
    phone = str(data.get("phone", "")).strip()
    relation = str(data.get("relation", "")).strip()

    if not name or not phone:
        return jsonify({"error": "Name and phone number are required."}), 400

    db = get_db()
    cur = db.execute(
        "INSERT INTO family_members(user_id,name,relation,phone,created_at) VALUES(?,?,?,?,?)",
        (LOCAL_USER_ID, name, relation, phone, now())
    )
    db.commit()

    row = db.execute(
        "SELECT * FROM family_members WHERE id=?",
        (cur.lastrowid,)
    ).fetchone()

    return jsonify(dict(row)), 201

@app.route("/api/family/<int:member_id>", methods=["DELETE"])
def delete_family(member_id):
    db = get_db()
    db.execute(
        "DELETE FROM family_members WHERE id=? AND user_id=?",
        (member_id, LOCAL_USER_ID)
    )
    db.commit()
    return jsonify({"deleted": member_id})

@app.route("/api/history")
def history():
    rows = get_db().execute("""
        SELECT id, message_snippet, attachment_names, link, risk_score,
               risk_label, language_detected, alerted_family, created_at
        FROM scan_history
        WHERE user_id=?
        ORDER BY created_at DESC
        LIMIT 30
    """, (LOCAL_USER_ID,)).fetchall()

    return jsonify([dict(row) for row in rows])

@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "ai_configured": bool(GEMINI_API_KEY),
        "model": MODEL_NAME,
        "login_required": False
    })

init_db()

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=True
    )
