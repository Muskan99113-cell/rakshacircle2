import os
import json
import base64
import sqlite3
import smtplib
from email.message import EmailMessage

import requests
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

app.config["SECRET_KEY"] = os.getenv(
    "SECRET_KEY",
    "rakshacircle-hackathon-secret-2026"
)

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_MODEL = os.getenv(
    "OPENROUTER_MODEL",
    "openrouter/free"
)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

DB_FILE = "rakshacircle.db"


# =========================================================
# DATABASE
# =========================================================

def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS family_members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            relation TEXT,
            phone TEXT,
            email TEXT
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS scans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            input_type TEXT,
            content TEXT,
            score INTEGER,
            risk TEXT,
            language TEXT,
            explanation TEXT,
            action TEXT,
            evidence TEXT,
            red_flags TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()


init_db()


# =========================================================
# AI PROMPT
# =========================================================

SYSTEM_PROMPT = """
You are RakshaCircle, an AI-powered scam detection and protection assistant.

Analyze the user's submitted message, link, document, or image.

Your job:
1. Detect scam, fraud, phishing, impersonation, or social-engineering indicators.
2. Give a risk score from 0 to 100.
3. Identify the likely language.
4. Explain the reasoning in simple language.
5. Give practical safety action.
6. Identify evidence and red flags.

Return ONLY valid JSON in this exact format:

{
  "score": 0,
  "risk": "Safe",
  "language": "English",
  "evidence": [
    "example evidence"
  ],
  "red_flags": [
    "example red flag"
  ],
  "explanation": "simple explanation",
  "action": "recommended action"
}

Risk rules:

0-29 = Safe
30-59 = Suspicious
60-79 = High Risk
80-100 = Scam

Be conservative and safety-focused.

Never invent evidence that is not present in the submitted content.
"""


# =========================================================
# OPENROUTER
# =========================================================

def analyze_with_openrouter(user_content, image_data=None):

    if not OPENROUTER_API_KEY:
        raise RuntimeError(
            "OPENROUTER_API_KEY is missing."
        )

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:5000",
        "X-Title": "RakshaCircle"
    }

    if image_data:

        content = [
            {
                "type": "text",
                "text": user_content
            },
            {
                "type": "image_url",
                "image_url": {
                    "url": image_data
                }
            }
        ]

    else:
        content = user_content

    payload = {
        "model": OPENROUTER_MODEL,
        "messages": [
            {
                "role": "system",
                "content": SYSTEM_PROMPT
            },
            {
                "role": "user",
                "content": content
            }
        ],
        "temperature": 0.1
    }

    response = requests.post(
        OPENROUTER_URL,
        headers=headers,
        json=payload,
        timeout=90
    )

    if response.status_code != 200:
        raise RuntimeError(
            f"OpenRouter error {response.status_code}: "
            f"{response.text}"
        )

    data = response.json()

    try:
        answer = data["choices"][0]["message"]["content"]
    except Exception:
        raise RuntimeError(
            "Invalid response received from OpenRouter."
        )

    answer = answer.strip()

    if answer.startswith("```"):
        answer = answer.replace("```json", "")
        answer = answer.replace("```", "")
        answer = answer.strip()

    try:
        result = json.loads(answer)

    except json.JSONDecodeError:

        start = answer.find("{")
        end = answer.rfind("}")

        if start != -1 and end != -1:

            try:
                result = json.loads(
                    answer[start:end + 1]
                )

            except Exception:
                raise RuntimeError(
                    "AI returned invalid JSON."
                )

        else:
            raise RuntimeError(
                "AI returned an invalid response."
            )

    return result


# =========================================================
# PDF EXTRACTION
# =========================================================

def extract_pdf_text(file):

    try:

        from pypdf import PdfReader

        reader = PdfReader(file)

        pages = []

        for page in reader.pages:

            text = page.extract_text()

            if text:
                pages.append(text)

        return "\n".join(pages)

    except Exception as e:

        raise RuntimeError(
            f"Could not read PDF: {e}"
        )


# =========================================================
# EMAIL ALERT
# =========================================================

def send_email_alert(member, result):

    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(
        os.getenv("SMTP_PORT", "587")
    )

    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")

    if not all([
        smtp_host,
        smtp_user,
        smtp_password,
        member["email"]
    ]):
        return False

    msg = EmailMessage()

    msg["Subject"] = "RakshaCircle Safety Alert"
    msg["From"] = smtp_user
    msg["To"] = member["email"]

    msg.set_content(
        f"""
RakshaCircle Safety Alert

A potentially dangerous message/content was detected.

Risk: {result.get("risk", "Unknown")}
Risk Score: {result.get("score", 0)}/100

Explanation:
{result.get("explanation", "")}

Recommended Action:
{result.get("action", "")}

Please verify the sender before taking any action.
"""
    )

    with smtplib.SMTP(
        smtp_host,
        smtp_port
    ) as server:

        server.starttls()

        server.login(
            smtp_user,
            smtp_password
        )

        server.send_message(msg)

    return True


# =========================================================
# WHATSAPP ALERT - META CLOUD API
# =========================================================

def send_whatsapp_alert(member, result):

    access_token = os.getenv(
        "WHATSAPP_ACCESS_TOKEN"
    )

    phone_number_id = os.getenv(
        "WHATSAPP_PHONE_NUMBER_ID"
    )

    if not all([
        access_token,
        phone_number_id,
        member["phone"]
    ]):
        print(
            "WhatsApp configuration missing."
        )
        return False

    to_number = str(
        member["phone"]
    ).strip()

    # Remove spaces, brackets and hyphens
    to_number = (
        to_number
        .replace(" ", "")
        .replace("-", "")
        .replace("(", "")
        .replace(")", "")
    )

    # If Indian number is entered as 10 digits,
    # automatically add +91.
    if len(to_number) == 10:
        to_number = "+91" + to_number

    # Remove + because Meta API expects digits
    to_number = to_number.replace("+", "")

    url = (
        "https://graph.facebook.com/v23.0/"
        f"{phone_number_id}/messages"
    )

    headers = {
        "Authorization": (
            f"Bearer {access_token}"
        ),
        "Content-Type": "application/json"
    }

    # -----------------------------------------------------
    # TEST TEMPLATE
    # -----------------------------------------------------
    #
    # Meta's WhatsApp test environment requires
    # an approved template.
    #
    # hello_world is the standard test template.
    #

    payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "template",
        "template": {
            "name": "hello_world",
            "language": {
                "code": "en_US"
            }
        }
    }

    try:

        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=30
        )

        print(
            "WHATSAPP STATUS:",
            response.status_code
        )

        print(
            "WHATSAPP RESPONSE:",
            response.text
        )

        if response.ok:
            print(
                "WhatsApp message sent successfully."
            )
            return True

        return False

    except Exception as e:

        print(
            "WHATSAPP ERROR:",
            str(e)
        )

        return False


# =========================================================
# FAMILY ALERT
# =========================================================

def send_family_alert(result):

    if result.get("score", 0) < 70:

        return {
            "sent": False,
            "message": "No family alert required."
        }

    conn = get_db()

    members = conn.execute(
        "SELECT * FROM family_members"
    ).fetchall()

    conn.close()

    if not members:

        return {
            "sent": False,
            "message": (
                "High-risk result detected, "
                "but no family member is configured."
            )
        }

    whatsapp_count = 0
    email_count = 0
    errors = []

    for member in members:

        # -------------------------------------------------
        # WHATSAPP ALERT
        # -------------------------------------------------

        if member["phone"]:

            try:

                if send_whatsapp_alert(
                    member,
                    result
                ):
                    whatsapp_count += 1

            except Exception as e:

                print(
                    "WHATSAPP ALERT ERROR:",
                    str(e)
                )

                errors.append(
                    f"{member['name']}: "
                    f"WhatsApp failed - {str(e)}"
                )

        # -------------------------------------------------
        # EMAIL ALERT
        # -------------------------------------------------

        if member["email"]:

            try:

                if send_email_alert(
                    member,
                    result
                ):
                    email_count += 1

            except Exception as e:

                print(
                    "EMAIL ALERT ERROR:",
                    str(e)
                )

                errors.append(
                    f"{member['name']}: "
                    f"Email failed - {str(e)}"
                )

    total_sent = (
        whatsapp_count +
        email_count
    )

    if total_sent == 0:

        return {
            "sent": False,
            "simulated": False,
            "message": (
                "Family alert could not be delivered."
            ),
            "errors": errors
        }

    return {
        "sent": True,
        "simulated": False,
        "message": (
            "Family alert sent successfully. "
            f"WhatsApp: {whatsapp_count}, "
            f"Email: {email_count}."
        ),
        "whatsapp_count": whatsapp_count,
        "email_count": email_count,
        "errors": errors
    }


# =========================================================
# HOME
# =========================================================

@app.route("/")
def home():

    return render_template(
        "index.html"
    )


# =========================================================
# HEALTH
# =========================================================

@app.route("/health")
def health():

    return jsonify({
        "status": "ok",
        "service": "RakshaCircle",
        "ai": "OpenRouter"
    })


# =========================================================
# ANALYZE
# =========================================================

@app.route(
    "/api/analyze",
    methods=["POST"]
)
def analyze():

    try:

        message = request.form.get(
            "message",
            ""
        ).strip()

        link = request.form.get(
            "link",
            ""
        ).strip()

        uploaded_file = request.files.get(
            "file"
        )

        image_data = None

        input_parts = []

        if message:

            input_parts.append(
                f"User message:\n{message}"
            )

        if link:

            input_parts.append(
                f"URL/link:\n{link}"
            )

        if uploaded_file:

            filename = (
                uploaded_file.filename or ""
            )

            extension = os.path.splitext(
                filename
            )[1].lower()

            if extension == ".pdf":

                pdf_text = extract_pdf_text(
                    uploaded_file
                )

                input_parts.append(
                    f"PDF content:\n"
                    f"{pdf_text[:20000]}"
                )

            elif extension in [
                ".png",
                ".jpg",
                ".jpeg",
                ".webp"
            ]:

                raw = uploaded_file.read()

                encoded = base64.b64encode(
                    raw
                ).decode("utf-8")

                mime = (
                    "image/png"
                    if extension == ".png"
                    else "image/webp"
                    if extension == ".webp"
                    else "image/jpeg"
                )

                image_data = (
                    f"data:{mime};base64,{encoded}"
                )

                input_parts.append(
                    "Analyze the attached image "
                    "for scam/phishing indicators."
                )

            else:

                text = uploaded_file.read().decode(
                    "utf-8",
                    errors="ignore"
                )

                input_parts.append(
                    f"Uploaded file content:\n"
                    f"{text[:20000]}"
                )

        if not input_parts:

            return jsonify({
                "error": (
                    "Please enter a message, "
                    "link, or upload a file."
                )
            }), 400

        final_content = "\n\n".join(
            input_parts
        )

        result = analyze_with_openrouter(
            final_content,
            image_data=image_data
        )

        score = int(
            result.get("score", 0)
        )

        score = max(
            0,
            min(100, score)
        )

        result["score"] = score

        if score >= 80:
            result["risk"] = "Scam"

        elif score >= 60:
            result["risk"] = "High Risk"

        elif score >= 30:
            result["risk"] = "Suspicious"

        else:
            result["risk"] = "Safe"

        result.setdefault(
            "language",
            "English"
        )

        result.setdefault(
            "evidence",
            []
        )

        result.setdefault(
            "red_flags",
            []
        )

        result.setdefault(
            "explanation",
            "No detailed explanation was returned."
        )

        result.setdefault(
            "action",
            (
                "Do not share personal "
                "or financial information."
            )
        )

        # -------------------------------------------------
        # SAVE SCAN HISTORY
        # -------------------------------------------------

        conn = get_db()

        conn.execute(
            """
            INSERT INTO scans
            (
                input_type,
                content,
                score,
                risk,
                language,
                explanation,
                action,
                evidence,
                red_flags
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "image" if image_data else "text",
                final_content[:10000],
                result["score"],
                result["risk"],
                result["language"],
                result["explanation"],
                result["action"],
                json.dumps(
                    result["evidence"],
                    ensure_ascii=False
                ),
                json.dumps(
                    result["red_flags"],
                    ensure_ascii=False
                )
            )
        )

        conn.commit()
        conn.close()

        # -------------------------------------------------
        # FAMILY PROTECTION
        # -------------------------------------------------

        alert = send_family_alert(
            result
        )

        result["family_alert"] = alert

        return jsonify(result)

    except Exception as e:

        print(
            "ANALYZE ERROR:",
            str(e)
        )

        return jsonify({
            "error": str(e)
        }), 500


# =========================================================
# FAMILY - GET
# =========================================================

@app.route(
    "/api/family",
    methods=["GET"]
)
def get_family():

    try:

        conn = get_db()

        members = conn.execute(
            """
            SELECT
                id,
                name,
                relation,
                phone,
                email
            FROM family_members
            ORDER BY id DESC
            """
        ).fetchall()

        conn.close()

        return jsonify([
            dict(member)
            for member in members
        ])

    except Exception as e:

        return jsonify({
            "error": str(e)
        }), 500


# =========================================================
# FAMILY - ADD
# =========================================================

@app.route(
    "/api/family",
    methods=["POST"]
)
def add_family():

    try:

        data = request.get_json(
            silent=True
        ) or {}

        name = str(
            data.get("name", "")
        ).strip()

        relation = str(
            data.get("relation", "")
        ).strip()

        phone = str(
            data.get("phone", "")
        ).strip()

        email = str(
            data.get("email", "")
        ).strip()

        if not name:

            return jsonify({
                "error": "Name is required."
            }), 400

        conn = get_db()

        cursor = conn.execute(
            """
            INSERT INTO family_members
            (name, relation, phone, email)
            VALUES (?, ?, ?, ?)
            """,
            (
                name,
                relation,
                phone,
                email
            )
        )

        conn.commit()

        member_id = cursor.lastrowid

        conn.close()

        return jsonify({
            "success": True,
            "id": member_id
        })

    except Exception as e:

        return jsonify({
            "error": str(e)
        }), 500


# =========================================================
# FAMILY - DELETE
# =========================================================

@app.route(
    "/api/family/<int:member_id>",
    methods=["DELETE"]
)
def delete_family(member_id):

    try:

        conn = get_db()

        conn.execute(
            """
            DELETE FROM family_members
            WHERE id = ?
            """,
            (member_id,)
        )

        conn.commit()
        conn.close()

        return jsonify({
            "success": True
        })

    except Exception as e:

        return jsonify({
            "error": str(e)
        }), 500


# =========================================================
# HISTORY
# =========================================================

@app.route(
    "/api/history",
    methods=["GET"]
)
def history():

    try:

        conn = get_db()

        rows = conn.execute(
            """
            SELECT *
            FROM scans
            ORDER BY id DESC
            LIMIT 50
            """
        ).fetchall()

        conn.close()

        output = []

        for row in rows:

            item = dict(row)

            try:

                item["evidence"] = json.loads(
                    item["evidence"] or "[]"
                )

            except Exception:

                item["evidence"] = []

            try:

                item["red_flags"] = json.loads(
                    item["red_flags"] or "[]"
                )

            except Exception:

                item["red_flags"] = []

            output.append(item)

        return jsonify(output)

    except Exception as e:

        return jsonify({
            "error": str(e)
        }), 500


# =========================================================
# RUN
# =========================================================

if __name__ == "__main__":

    port = int(
        os.getenv(
            "PORT",
            "5000"
        )
    )

    app.run(
        host="0.0.0.0",
        port=port,
        debug=True
    )