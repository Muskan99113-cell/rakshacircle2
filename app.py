import os
import io
import json
import re
import sqlite3
import base64
from datetime import datetime, timezone

import requests
from flask import Flask, request, jsonify, render_template, g
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get(
    "SECRET_KEY",
    "change-this-secret-key"
)

# ============================================================
# OPENROUTER CONFIG
# ============================================================

OPENROUTER_API_KEY = os.environ.get(
    "OPENROUTER_API_KEY",
    ""
).strip()

MODEL_NAME = os.environ.get(
    "OPENROUTER_MODEL",
    "openrouter/free"
).strip()

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


# ============================================================
# APP / DATABASE CONFIG
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DB_PATH = os.path.join(
    BASE_DIR,
    "rakshacircle.db"
)

LOCAL_USER_ID = 1
LOCAL_USER_NAME = "RakshaCircle User"


# ============================================================
# AI SYSTEM PROMPT
# ============================================================

SYSTEM_PROMPT = """
You are RakshaCircle, a defensive scam-detection assistant
for Indian users.

Analyze the supplied message, URL, PDF text and/or screenshot for:

- phishing and credential theft
- UPI/bank/KYC scams
- OTP/password/PIN requests
- impersonation
- fake jobs and courier scams
- investment/crypto scams
- malicious or suspicious links
- urgency, threats and social engineering

Do not claim something is definitely a scam unless the
supplied evidence supports it.

If an image is supplied, inspect visible text, logos, UI,
and suspicious instructions.

If a PDF is supplied, analyze its extracted text.

Return ONLY valid JSON matching this structure:

{
  "risk_score": 0-100,
  "risk_label": "Safe|Low Risk|Suspicious|High Risk|Confirmed Scam Pattern",
  "language_detected": "language/script",
  "red_flags": [
    {
      "phrase": "short exact phrase or URL from supplied content",
      "reason": "why it is suspicious"
    }
  ],
  "explanation": "2-4 simple sentences in the user's language where possible",
  "suggested_action": "one concrete safe next step"
}

Maximum 5 red_flags.

Never invent phrases or URLs that were not supplied.
"""


# ============================================================
# DATABASE
# ============================================================

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

    # Family members
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

    # Scan history
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


# ============================================================
# TEMPLATE CONTEXT
# ============================================================

@app.context_processor
def inject_user():
    return {
        "current_user_name": LOCAL_USER_NAME
    }


# ============================================================
# MAIN PAGE
# ============================================================

@app.route("/")
def index():
    return render_template("index.html")


# ============================================================
# OLD LOGOUT ROUTE
# ============================================================

@app.route("/logout")
def logout():

    return jsonify({
        "message": "Login is not required in this local prototype."
    })


# ============================================================
# PDF TEXT EXTRACTION
# ============================================================

def extract_pdf_text(data):

    try:

        from pypdf import PdfReader

        reader = PdfReader(
            io.BytesIO(data)
        )

        parts = []

        for page in reader.pages[:10]:

            text = page.extract_text() or ""

            parts.append(text)

        return "\n".join(parts)[:12000]

    except Exception as exc:

        return (
            f"[PDF text extraction failed: {exc}]"
        )


# ============================================================
# URL DETECTION
# ============================================================

def find_urls(text):

    return re.findall(
        r'https?://[^\s<>"\']+',
        text or "",
        flags=re.I
    )


# ============================================================
# OPENROUTER AI ANALYSIS
# ============================================================

def analyze_with_openrouter(
    message_text,
    link,
    attachment_text,
    image_parts
):

    if not OPENROUTER_API_KEY:

        raise RuntimeError(
            "OPENROUTER_API_KEY is missing. "
            "Add your OpenRouter key to .env."
        )

    all_urls = (
        find_urls(message_text)
        + find_urls(link)
        + find_urls(attachment_text)
    )

    prompt = f"""
USER MESSAGE:
{message_text[:8000] or "None"}

EXPLICIT LINK FIELD:
{link[:2000] or "None"}

EXTRACTED PDF/ATTACHMENT TEXT:
{attachment_text[:12000] or "None"}

LINKS FOUND:
{", ".join(all_urls) or "None"}

Analyze all supplied evidence.

Images/screenshots are supplied as image parts.

Return ONLY a single valid JSON object.
Do not use markdown fences.
Do not add commentary.
"""

    # First text message
    user_content = [
        {
            "type": "text",
            "text": prompt
        }
    ]

    # Add images
    for image in image_parts[:4]:

        user_content.append({
            "type": "image_url",
            "image_url": {
                "url": (
                    f"data:{image['mime_type']};"
                    f"base64,{image['data']}"
                )
            }
        })

    payload = {

        "model": MODEL_NAME,

        "messages": [

            {
                "role": "system",
                "content": SYSTEM_PROMPT
            },

            {
                "role": "user",
                "content": user_content
            }

        ],

        "temperature": 0.1,

        "max_tokens": 1200
    }

    headers = {

        "Authorization":
            f"Bearer {OPENROUTER_API_KEY}",

        "Content-Type":
            "application/json",

        "HTTP-Referer":
            "http://localhost:5000",

        "X-Title":
            "RakshaCircle"
    }

    # --------------------------------------------------------
    # API REQUEST
    # --------------------------------------------------------

    try:

        response = requests.post(

            OPENROUTER_URL,

            headers=headers,

            json=payload,

            timeout=90
        )

    except requests.RequestException as exc:

        raise RuntimeError(
            f"OpenRouter connection failed: {exc}"
        ) from exc


    # --------------------------------------------------------
    # API ERROR
    # --------------------------------------------------------

    if response.status_code >= 400:

        try:

            detail = (
                response.json()
                .get("error", {})
                .get("message", response.text)
            )

        except ValueError:

            detail = response.text

        raise RuntimeError(
            f"OpenRouter API "
            f"{response.status_code}: "
            f"{detail}"
        )


    # --------------------------------------------------------
    # RESPONSE PARSING
    # --------------------------------------------------------

    try:

        data = response.json()

        raw = (
            data["choices"][0]["message"]
            .get("content")
            or ""
        ).strip()

    except (
        ValueError,
        KeyError,
        IndexError,
        TypeError
    ) as exc:

        raise RuntimeError(
            "OpenRouter returned an unexpected response."
        ) from exc


    if not raw:

        raise RuntimeError(
            "OpenRouter returned an empty response."
        )


    # --------------------------------------------------------
    # REMOVE MARKDOWN JSON FENCES
    # --------------------------------------------------------

    raw = re.sub(
        r"^```(?:json)?\s*",
        "",
        raw,
        flags=re.I
    )

    raw = re.sub(
        r"\s*```$",
        "",
        raw
    ).strip()


    # --------------------------------------------------------
    # JSON PARSING
    # --------------------------------------------------------

    try:

        result = json.loads(raw)

    except json.JSONDecodeError:

        # Try finding JSON object inside response
        match = re.search(
            r"\{.*\}",
            raw,
            flags=re.S
        )

        if not match:

            raise RuntimeError(
                "OpenRouter returned invalid JSON."
            )

        try:

            result = json.loads(
                match.group(0)
            )

        except json.JSONDecodeError as exc:

            raise RuntimeError(
                "OpenRouter returned invalid JSON."
            ) from exc


    # --------------------------------------------------------
    # DEFAULT VALUES
    # --------------------------------------------------------

    result.setdefault(
        "risk_score",
        50
    )

    result.setdefault(
        "risk_label",
        "Suspicious"
    )

    result.setdefault(
        "language_detected",
        "Unknown"
    )

    result.setdefault(
        "red_flags",
        []
    )

    result.setdefault(
        "explanation",
        ""
    )

    result.setdefault(
        "suggested_action",
        ""
    )

    return result


# ============================================================
# TWILIO SMS
# ============================================================

def send_sms_alert(phone, score):

    """
    Optional Twilio SMS.

    If Twilio credentials are not configured,
    the alert is simulated in the terminal.
    """

    sid = os.environ.get(
        "TWILIO_ACCOUNT_SID"
    )

    token = os.environ.get(
        "TWILIO_AUTH_TOKEN"
    )

    from_number = os.environ.get(
        "TWILIO_FROM_NUMBER"
    )


    # No Twilio = local simulation
    if not (
        sid
        and token
        and from_number
    ):

        print(
            f"[SIMULATED FAMILY ALERT] "
            f"To {phone}: "
            f"high-risk scan, "
            f"score {score}."
        )

        return False


    try:

        from twilio.rest import Client

        Client(sid, token).messages.create(

            body=(
                "RakshaCircle alert: "
                f"a high-risk message was detected "
                f"(score {score}). "
                "Verify before any payment "
                "or OTP sharing."
            ),

            from_=from_number,

            to=phone
        )

        return True


    except Exception as exc:

        print(
            f"[SMS FAILED] "
            f"{phone}: {exc}"
        )

        return False


# ============================================================
# FAMILY ALERT
# ============================================================

def alert_family(score):

    members = get_db().execute(

        """
        SELECT *
        FROM family_members
        WHERE user_id=?
        """,

        (LOCAL_USER_ID,)

    ).fetchall()


    if not members:

        return False, 0


    sent = 0


    for member in members:

        if send_sms_alert(
            member["phone"],
            score
        ):

            sent += 1


    # Family alert was triggered even if
    # Twilio is not configured.
    return True, sent


# ============================================================
# ANALYZE API
# ============================================================

@app.route(
    "/api/analyze",
    methods=["POST"]
)
def api_analyze():

    message = request.form.get(
        "message",
        ""
    ).strip()

    link = request.form.get(
        "link",
        ""
    ).strip()

    files = request.files.getlist(
        "attachments"
    )


    # --------------------------------------------------------
    # EMPTY INPUT
    # --------------------------------------------------------

    if (
        not message
        and not link
        and not files
    ):

        return jsonify({

            "error":
                "Message, link, image, "
                "screenshot, or PDF is required."

        }), 400


    # --------------------------------------------------------
    # INPUT LIMITS
    # --------------------------------------------------------

    if (
        len(message) > 8000
        or len(link) > 2000
    ):

        return jsonify({

            "error":
                "Input is too large."

        }), 400


    attachment_text = []

    image_parts = []

    names = []


    # --------------------------------------------------------
    # FILE PROCESSING
    # --------------------------------------------------------

    for f in files[:5]:

        if not f or not f.filename:

            continue


        name = os.path.basename(
            f.filename
        )

        names.append(name)


        data = f.read()


        # 10 MB max
        if len(data) > (
            10 * 1024 * 1024
        ):

            return jsonify({

                "error":
                    f"{name} is larger than 10 MB."

            }), 400


        ext = os.path.splitext(
            name
        )[1].lower()

        mime = (
            f.mimetype
            or ""
        )


        # ----------------------------------------------------
        # PDF
        # ----------------------------------------------------

        if (
            ext == ".pdf"
            or mime == "application/pdf"
        ):

            attachment_text.append(

                f"[PDF: {name}]\n"
                f"{extract_pdf_text(data)}"

            )


        # ----------------------------------------------------
        # IMAGE
        # ----------------------------------------------------

        elif (
            ext in {
                ".png",
                ".jpg",
                ".jpeg",
                ".webp"
            }
            or mime.startswith("image/")
        ):

            image_parts.append({

                "data":
                    base64.b64encode(
                        data
                    ).decode("ascii"),

                "mime_type":
                    mime or "image/jpeg"

            })


        # ----------------------------------------------------
        # OTHER FILE
        # ----------------------------------------------------

        else:

            attachment_text.append(

                f"[Attachment: {name}] "
                "Unsupported file type; "
                "filename was supplied."

            )


    # --------------------------------------------------------
    # AI ANALYSIS
    # --------------------------------------------------------

    try:

        result = analyze_with_openrouter(

            message,
            link,
            "\n".join(
                attachment_text
            ),
            image_parts

        )

    except Exception as exc:

        return jsonify({

            "error":
                f"AI analysis failed: {exc}"

        }), 502


    # --------------------------------------------------------
    # NORMALIZE SCORE
    # --------------------------------------------------------

    try:

        score = max(
            0,
            min(
                100,
                int(
                    result.get(
                        "risk_score",
                        0
                    )
                    or 0
                )
            )
        )

    except (
        TypeError,
        ValueError
    ):

        score = 50


    # --------------------------------------------------------
    # FAMILY ALERT
    # --------------------------------------------------------

    alerted = False

    sms_sent = 0


    if score >= 70:

        alerted, sms_sent = alert_family(
            score
        )


    # --------------------------------------------------------
    # SAVE HISTORY
    # --------------------------------------------------------

    db = get_db()


    db.execute(

        """
        INSERT INTO scan_history
        (
            user_id,
            message_snippet,
            attachment_names,
            link,
            risk_score,
            risk_label,
            language_detected,
            alerted_family,
            created_at
        )

        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,

        (
            LOCAL_USER_ID,

            message[:200],

            json.dumps(names),

            link,

            score,

            result.get(
                "risk_label",
                "Suspicious"
            ),

            result.get(
                "language_detected",
                "Unknown"
            ),

            1 if alerted else 0,

            now()
        )

    )


    db.commit()


    # --------------------------------------------------------
    # FINAL RESPONSE
    # --------------------------------------------------------

    result["risk_score"] = score

    result["family_alerted"] = alerted

    result["sms_sent"] = sms_sent

    result["family_notified"] = alerted

    result["attachments"] = names

    result["links_found"] = find_urls(

        message
        + " "
        + link
        + " "
        + "\n".join(
            attachment_text
        )

    )


    return jsonify(result)


# ============================================================
# FAMILY MEMBERS - GET
# ============================================================

@app.route(
    "/api/family",
    methods=["GET"]
)
def get_family():

    rows = get_db().execute(

        """
        SELECT *
        FROM family_members
        WHERE user_id=?
        ORDER BY created_at DESC
        """,

        (LOCAL_USER_ID,)

    ).fetchall()


    return jsonify([
        dict(row)
        for row in rows
    ])


# ============================================================
# FAMILY MEMBERS - ADD
# ============================================================

@app.route(
    "/api/family",
    methods=["POST"]
)
def add_family():

    data = request.get_json(
        silent=True
    ) or {}


    name = str(
        data.get(
            "name",
            ""
        )
    ).strip()


    phone = str(
        data.get(
            "phone",
            ""
        )
    ).strip()


    relation = str(
        data.get(
            "relation",
            ""
        )
    ).strip()


    if not name or not phone:

        return jsonify({

            "error":
                "Name and phone number "
                "are required."

        }), 400


    db = get_db()


    cur = db.execute(

        """
        INSERT INTO family_members
        (
            user_id,
            name,
            relation,
            phone,
            created_at
        )

        VALUES (?, ?, ?, ?, ?)
        """,

        (
            LOCAL_USER_ID,
            name,
            relation,
            phone,
            now()
        )

    )


    db.commit()


    row = db.execute(

        """
        SELECT *
        FROM family_members
        WHERE id=?
        """,

        (cur.lastrowid,)

    ).fetchone()


    return jsonify(
        dict(row)
    ), 201


# ============================================================
# FAMILY MEMBER - DELETE
# ============================================================

@app.route(
    "/api/family/<int:member_id>",
    methods=["DELETE"]
)
def delete_family(member_id):

    db = get_db()


    db.execute(

        """
        DELETE FROM family_members
        WHERE id=?
        AND user_id=?
        """,

        (
            member_id,
            LOCAL_USER_ID
        )

    )


    db.commit()


    return jsonify({

        "deleted":
            member_id

    })


# ============================================================
# HISTORY
# ============================================================

@app.route(
    "/api/history"
)
def history():

    rows = get_db().execute(

        """
        SELECT
            id,
            message_snippet,
            attachment_names,
            link,
            risk_score,
            risk_label,
            language_detected,
            alerted_family,
            created_at

        FROM scan_history

        WHERE user_id=?

        ORDER BY created_at DESC

        LIMIT 30
        """,

        (LOCAL_USER_ID,)

    ).fetchall()


    return jsonify([
        dict(row)
        for row in rows
    ])


# ============================================================
# HEALTH CHECK
# ============================================================

@app.route("/health")
def health():

    return jsonify({

        "status":
            "ok",

        "ai_configured":
            bool(
                OPENROUTER_API_KEY
            ),

        "model":
            MODEL_NAME,

        "login_required":
            False

    })


# ============================================================
# INITIALIZE DATABASE
# ============================================================

init_db()


# ============================================================
# RUN APP
# ============================================================

if __name__ == "__main__":

    app.run(

        host="0.0.0.0",

        port=int(
            os.environ.get(
                "PORT",
                5000
            )
        ),

        debug=True
    )