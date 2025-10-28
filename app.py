import os
from flask import Flask, render_template, request, redirect, url_for, flash
import csv
from datetime import datetime
import bcrypt
from twilio.rest import Client

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "dev-secret")  # Change in production

DATA_CSV = "submissions.csv"

def save_submission(row: dict):
    fieldnames = ["timestamp", "name", "email", "password_hash", "gender", "interests", "bio"]
    exists = os.path.exists(DATA_CSV)
    with open(DATA_CSV, "a", newline='', encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not exists:
            writer.writeheader()
        writer.writerow(row)

def hash_password(pw: str) -> str:
    if not pw:
        return ""
    pw_bytes = pw.encode("utf-8")
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(pw_bytes, salt)
    return hashed.decode("utf-8")

def send_whatsapp_message(body_text: str) -> bool:
    sid = os.environ.get("TWILIO_ACCOUNT_SID")
    token = os.environ.get("TWILIO_AUTH_TOKEN")
    from_whatsapp = os.environ.get("TWILIO_WHATSAPP_FROM")
    to_whatsapp = os.environ.get("OWNER_WHATSAPP_TO")
    if not (sid and token and from_whatsapp and to_whatsapp):
        app.logger.info("Twilio details not configured; skipping WhatsApp send.")
        return False
    client = Client(sid, token)
    try:
        message = client.messages.create(body=body_text, from_=from_whatsapp, to=to_whatsapp)
        app.logger.info("Sent message SID: %s", message.sid)
        return True
    except Exception as e:
        app.logger.error("Failed to send WhatsApp message: %s", e)
        return False

@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")

@app.route("/submit", methods=["POST"])
def submit():
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    password = request.form.get("password", "")
    gender = request.form.get("gender", "")
    interests = request.form.getlist("interests")
    bio = request.form.get("bio", "").strip()

    if not name or not email:
        flash("Name and email are required.")
        return redirect(url_for("index"))

    pw_hash = hash_password(password)

    row = {
        "timestamp": datetime.utcnow().isoformat(),
        "name": name,
        "email": email,
        "password_hash": pw_hash,
        "gender": gender,
        "interests": ";".join(interests),
        "bio": bio
    }
    save_submission(row)

    message = (
        f"New form submission:\n"
        f"Name: {name}\n"
        f"Email: {email}\n"
        f"Gender: {gender}\n"
        f"Interests: {', '.join(interests) if interests else 'None'}\n"
        f"Bio: {bio[:200]}\n"
        f"Time(UTC): {row['timestamp']}"
    )

    sent = send_whatsapp_message(message)
    if sent:
        flash("Submission received. WhatsApp notification sent.")
    else:
        flash("Submission received. Saved locally (WhatsApp not configured).")
    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(debug=True)
