from flask import Flask, render_template, jsonify, request
import imaplib, smtplib, email
from email.mime.text import MIMEText
import threading, time, random
from datetime import datetime, timedelta

# ---------- CONFIG ----------
EMAIL_ACCOUNT = "susan.m.mills1954@gmail.com"
EMAIL_PASSWORD = "xssj tnpe jusl allo"
IMAP_SERVER = "imap.gmail.com"
IMAP_PORT = 993
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587  # starttls
CHECK_INTERVAL = 15  # seconds

reply_delay_enabled = True
next_reply_time = datetime.now()

inbound_emails = []
outbound_emails = []

lock = threading.Lock()
LOG_FILE = "susan_log.txt"

app = Flask(__name__)

# ---------- LOGGING ----------
def log_event(message: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {message}"
    print(line)
    with lock:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")

# ---------- EMAIL FUNCTIONS ----------
def check_inbox():
    while True:
        try:
            log_event("Connecting to IMAP server...")
            mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
            mail.login(EMAIL_ACCOUNT, EMAIL_PASSWORD)
            mail.select("inbox")
            status, response = mail.search(None, "UNSEEN")
            unseen_ids = response[0].split()
            if unseen_ids:
                for e_id in unseen_ids:
                    status, msg_data = mail.fetch(e_id, "(RFC822)")
                    msg = email.message_from_bytes(msg_data[0][1])
                    from_addr = email.utils.parseaddr(msg["From"])[1]
                    subject = msg["Subject"]
                    body = ""
                    if msg.is_multipart():
                        for part in msg.walk():
                            if part.get_content_type() == "text/plain":
                                body += part.get_payload(decode=True).decode()
                    else:
                        body = msg.get_payload(decode=True).decode()
                    with lock:
                        inbound_emails.append({
                            "from": from_addr,
                            "subject": subject,
                            "body": body,
                            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        })
                        log_event(f"New email from {from_addr} | {subject}")
            mail.logout()
        except Exception as e:
            log_event(f"Error checking inbox: {e}")
        time.sleep(CHECK_INTERVAL)

def send_email(to_addr, subject, body):
    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_ACCOUNT, EMAIL_PASSWORD)
        message = f"From: {EMAIL_ACCOUNT}\nTo: {to_addr}\nSubject: {subject}\n\n{body}"
        server.sendmail(EMAIL_ACCOUNT, to_addr, message)
        server.quit()
        with lock:
            outbound_emails.append({
                "to": to_addr,
                "subject": subject,
                "body": body,
                "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })
        log_event(f"Email sent to {to_addr} | {subject}")
        return True
    except Exception as e:
        log_event(f"Failed to send email: {e}")
        return False

# ---------- FLASK ROUTES ----------
@app.route("/")
def dashboard():
    with lock:
        next_reply_iso = next_reply_time.isoformat() if next_reply_time else datetime.now().isoformat()
        try:
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                logs = f.read()
        except FileNotFoundError:
            logs = ""
        return render_template(
            "dashboard.html",
            inbound=inbound_emails,
            outbound=outbound_emails,
            reply_delay=reply_delay_enabled,
            next_reply_time=next_reply_iso,
            logs=logs
        )

@app.route("/inbound")
def get_inbound():
    with lock:
        return jsonify(inbound_emails)

@app.route("/outbound")
def get_outbound():
    with lock:
        return jsonify(outbound_emails)

@app.route("/toggle_delay", methods=["POST"])
def toggle_delay():
    global reply_delay_enabled
    reply_delay_enabled = not reply_delay_enabled
    log_event(f"Reply delay toggled: {reply_delay_enabled}")
    return jsonify({"reply_delay": reply_delay_enabled})

# ---------- EMAIL CHECK THREAD ----------
threading.Thread(target=check_inbox, daemon=True).start()

if __name__ == "__main__":
    log_event("Server started")
    app.run(debug=True, use_reloader=False)
