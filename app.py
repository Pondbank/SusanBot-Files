import os
import time
import json
import random
import threading
from datetime import datetime
from flask import Flask, render_template, request, jsonify

# --- CONFIG ---
EMAIL_ADDRESS = "susan.m.mills1954@gmail.com"
EMAIL_PASSWORD = "xssj tnpe jusl allo"
OPENAI_API_KEY = "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"
OPENAI_MODEL = "gpt-4o-mini"

CHECK_INTERVAL_SECONDS = 15
MIN_REPLY_DELAY_MIN = 2
MAX_REPLY_DELAY_MIN = 5

# --- STATE ---
app = Flask(__name__)
inbound_emails = []
outbound_emails = []
scheduled_queue = []
state_lock = threading.Lock()
log_lock = threading.Lock()
auto_sending_enabled = True

# --- LOGGING ---
LOG_FILE = "susan_log.txt"
def log_event(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    with log_lock:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    print(line, flush=True)

# --- OPENAI CLIENT ---
import openai
openai.api_key = OPENAI_API_KEY

def get_susan_reply(item):
    prompt = SUSAN_PROMPT + f"\nCompose a short email about a {item['item']} ({item['brand']}, {item['color']}) priced at {item['price']}."
    response = openai.ChatCompletion.create(
        model=OPENAI_MODEL,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=150
    )
    return response.choices[0].message.content.strip()

# --- SUSAN PROMPT (16 paragraphs) ---
SUSAN_PROMPT = """
You are “Susan M. Mills,” a 78-year-old retiree who replies to scam-like emails to waste their time.
Keep replies polite, human, and brief (max 6 sentences). You never give personal data.
You live alone in a modest terrace. You have an old Windows XP PC and a tablet. You don’t use a smartphone.
You enjoy crocheting, swapping books, gardening, and baking rock cakes. You have two children, John and Mary.
Your health is mostly fine but sometimes forgetful. You drink lots of tea and occasionally mention neighbors.
Never share real bank info, one-time codes, photos, or attachments.
Keep responses friendly, simple, slightly confused. 60% of replies end with a warm question.
Stall when asked for tech support, crypto, or gift cards. Ask simple clarifying questions.
If accused of being a bot, say you prefer email because phones confuse you.
If a scam is suspected, be firm but polite. Suggest you might stop replying.
Vary replies to feel natural, occasionally mention tea, glasses, or slow PC.
Bulk emails can start with a short note about a second-hand item.
Keep replies under 6 sentences. Always safe, no links, no codes.
Time responses realistically; if pressed, mention bus or going to shop.
End conversations politely if person loses interest or becomes hostile.
"""

# --- ITEM LIST (50 realistic items) ---
ITEMS = [
{"item":"lawn mower","brand":"Stiga Combi","color":"red","price":"£120"},
{"item":"vacuum cleaner","brand":"Dyson","color":"black","price":"£180"},
{"item":"bicycle","brand":"Giant","color":"blue","price":"£250"},
{"item":"coffee maker","brand":"Nespresso","color":"white","price":"£90"},
{"item":"drill","brand":"Bosch","color":"green","price":"£45"},
{"item":"toaster","brand":"Breville","color":"silver","price":"£35"},
{"item":"kettle","brand":"Russell Hobbs","color":"white","price":"£25"},
{"item":"blender","brand":"Philips","color":"black","price":"£40"},
{"item":"microwave","brand":"Samsung","color":"grey","price":"£110"},
{"item":"fan","brand":"Dyson","color":"white","price":"£130"},
{"item":"table lamp","brand":"Ikea","color":"yellow","price":"£15"},
{"item":"chair","brand":"Ikea","color":"black","price":"£45"},
{"item":"desk","brand":"Ikea","color":"brown","price":"£80"},
{"item":"bookshelf","brand":"Argos","color":"white","price":"£60"},
{"item":"sofa","brand":"DFS","color":"grey","price":"£400"},
{"item":"armchair","brand":"DFS","color":"blue","price":"£220"},
{"item":"rug","brand":"Wayfair","color":"red","price":"£70"},
{"item":"curtains","brand":"John Lewis","color":"green","price":"£50"},
{"item":"wall clock","brand":"Next","color":"black","price":"£25"},
{"item":"alarm clock","brand":"Sony","color":"white","price":"£35"},
{"item":"headphones","brand":"Sony","color":"black","price":"£60"},
{"item":"earbuds","brand":"Apple","color":"white","price":"£120"},
{"item":"tablet","brand":"Samsung","color":"silver","price":"£220"},
{"item":"smartphone","brand":"Samsung","color":"black","price":"£400"},
{"item":"camera","brand":"Canon","color":"black","price":"£320"},
{"item":"tripod","brand":"Manfrotto","color":"black","price":"£60"},
{"item":"watch","brand":"Casio","color":"black","price":"£50"},
{"item":"sunglasses","brand":"Ray-Ban","color":"black","price":"£80"},
{"item":"backpack","brand":"Nike","color":"blue","price":"£45"},
{"item":"handbag","brand":"Michael Kors","color":"brown","price":"£150"},
{"item":"wallet","brand":"Fossil","color":"black","price":"£60"},
{"item":"jacket","brand":"North Face","color":"green","price":"£120"},
{"item":"coat","brand":"Columbia","color":"grey","price":"£140"},
{"item":"boots","brand":"Dr. Martens","color":"black","price":"£130"},
{"item":"sneakers","brand":"Adidas","color":"white","price":"£80"},
{"item":"hat","brand":"New Era","color":"blue","price":"£25"},
{"item":"gloves","brand":"North Face","color":"black","price":"£30"},
{"item":"scarf","brand":"Burberry","color":"beige","price":"£180"},
{"item":"umbrella","brand":"Fulton","color":"black","price":"£20"},
{"item":"bike helmet","brand":"Giro","color":"red","price":"£50"},
{"item":"bike lock","brand":"Kryptonite","color":"black","price":"£40"},
{"item":"tent","brand":"Vango","color":"green","price":"£120"},
{"item":"sleeping bag","brand":"Coleman","color":"blue","price":"£70"},
{"item":"camping stove","brand":"Primus","color":"silver","price":"£60"},
{"item":"lantern","brand":"Coleman","color":"black","price":"£25"},
{"item":"garden hose","brand":"Hozelock","color":"green","price":"£30"},
{"item":"spade","brand":"Fiskars","color":"orange","price":"£20"},
{"item":"rake","brand":"Fiskars","color":"black","price":"£18"},
{"item":"wheelbarrow","brand":"Jackson","color":"red","price":"£90"},
{"item":"pruning shears","brand":"Bahco","color":"red","price":"£25"},
]

# --- ROUTES ---
@app.route("/")
def index():
    with state_lock:
        return render_template("dashboard.html",
            inbound=inbound_emails,
            outbound=outbound_emails,
            logs="\n".join(open(LOG_FILE).readlines()[-50:])
        )

@app.route("/set_auto", methods=["POST"])
def set_auto():
    global auto_sending_enabled
    data = request.get_json()
    auto_sending_enabled = data.get("enabled", True)
    return jsonify(status="ok")

@app.route("/send_bulk", methods=["POST"])
def send_bulk():
    emails_text = request.get_json().get("emails","")
    emails = re.split(r"[\s,]+", emails_text.strip())
    for addr in emails:
        choice = random.choice(ITEMS)
        body = f"Hello,\n\nI just received an email from you about my {choice['item']}. It's a {choice['color']} one by {choice['brand']}, thinking about {choice['price']}.\n\nSusan M"
        subject = f"My {choice['item']}"
        with state_lock:
            outbound_emails.append({"to": addr,"subject":subject,"body":body,"scheduled_for":datetime.now().strftime("%H:%M:%S"),"status":"scheduled"})
    return jsonify(status="ok")

@app.route("/manual_send", methods=["POST"])
def manual_send():
    data = request.get_json()
    to = data.get("to","")
    subject = data.get("subject","")
    body = data.get("body","")
    with state_lock:
        outbound_emails.append({"to": to,"subject":subject,"body":body,"scheduled_for":datetime.now().strftime("%H:%M:%S"),"status":"scheduled"})
    return jsonify(status="ok")

if __name__ == "__main__":
    log_event("SusanBot starting...")
    app.run(debug=True)
