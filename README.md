# RakshaCircle

Local Flask + OpenRouter scam detection prototype, with multi-language UI
(English, Hindi, Marathi, Tamil, Telugu, Bengali, Gujarati, Kannada) and
real family alerts by email and/or SMS.

## Run

1. Create `.env` in this same folder as `app.py` (copy `.env.example`).
2. Add your OpenRouter API key:
   `OPENROUTER_API_KEY=YOUR_KEY`
3. Install dependencies:
   `pip install -r requirements.txt`
4. Start:
   `python app.py`
5. Open `http://127.0.0.1:5000`

Login/signup are intentionally removed. The local prototype uses one local
profile and keeps family contacts and scan history in SQLite.

## Language switcher

Pick a language from the dropdown in the top-right corner. The whole
interface (labels, buttons, messages) switches instantly, and the choice is
remembered in the browser for next time.

## Family alerts (email / SMS)

Add a family member's phone and/or email under **Family circle**. When a
scan scores 70+ ("high risk"), RakshaCircle will:

- send a real **email** if `SMTP_HOST`, `SMTP_USER`, `SMTP_PASSWORD` and
  `SMTP_FROM_EMAIL` are set in `.env` (a free Gmail account with an
  [App Password](https://myaccount.google.com/apppasswords) works well), and/or
- send a real **SMS** if `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN` and
  `TWILIO_FROM_NUMBER` are set in `.env` (requires a Twilio account).

If neither is configured, the alert is only printed to the terminal
(simulated), and the UI clearly says so instead of pretending it was sent.

## Safety resources referenced in the app

- **1930** — India's official Citizen Financial Cyber Fraud Reporting
  helpline (toll-free).
- **cybercrime.gov.in** — the official National Cyber Crime Reporting
  Portal run by the Government of India.

Both are kept in the app as genuine, working resources for users who have
already been scammed.