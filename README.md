# RakshaCircle

Local Flask + Gemini scam detection prototype.

## Run

1. Create `.env` in this same folder as `app.py`.
2. Add your Gemini API key:
   `GEMINI_API_KEY=YOUR_NEW_KEY`
3. Install dependencies:
   `pip install -r requirements.txt`
4. Start:
   `python app.py`
5. Open `http://127.0.0.1:5000`

Login/signup are intentionally removed. The local prototype uses one local profile and keeps family contacts and scan history in SQLite.

For real SMS alerts, add Twilio credentials to `.env`. Without them, high-risk family alerts are simulated in the terminal.
