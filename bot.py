import json
import os
import subprocess
import requests
import random
import telebot
from dotenv import load_dotenv

# ==========================================
# 1. CONFIGURATION
# ==========================================
load_dotenv()
TELEGRAM_CREAT_BOT_TOKEN = os.getenv("TELEGRAM_CREAT_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
MAKE_WEBHOOK_URL = "https://hook.eu1.make.com/mvudpjo9r7pdbfaqkydj66wwuc2939jq"
HISTORY_FILE = "history.json"
OUTPUT_VIDEO_PATH = "/mnt/volume_fra1_1786451349368/output_deal.mp4"

bot = telebot.TeleBot(TELEGRAM_CREAT_BOT_TOKEN)
GLOBAL_FLIGHTS = []

# ==========================================
# 2. HELPER FUNCTIONS
# ==========================================
def is_authorized(message):
    return str(message.chat.id) == TELEGRAM_CHAT_ID

def get_all_flights(json_path="data/flights.json"):
    if not os.path.exists(json_path):
        return []
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data if isinstance(data, list) else data.get("flights", [])

def get_smart_random_combo():
    music_options = ["m1.mp3", "m2.mp3", "m4.mp3", "m5.mp3"]
    history = []
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r') as f: history = json.load(f)
        except: pass
            
    while True:
        p1, p2, p3, music = random.randint(1, 6), random.randint(1, 6), random.randint(1, 7), random.choice(music_options)
        combo_str = f"{p1}-{p2}-{p3}-{music}"
        if combo_str not in history[-50:]:
            history.append(combo_str)
            with open(HISTORY_FILE, 'w') as f: json.dump(history[-50:], f)
            return p1, p2, p3, music

def upload_to_telegram_and_get_url(video_path, caption):
    url = f"https://api.telegram.org/bot{TELEGRAM_CREAT_BOT_TOKEN}/sendVideo"
    try:
        with open(video_path, 'rb') as f:
            res = requests.post(url, data={'chat_id': TELEGRAM_CHAT_ID, 'caption': caption}, files={'video': f}).json()
        
        if res.get("ok"):
            file_id = res['result']['video']['file_id']
            file_res = requests.get(f"https://api.telegram.org/bot{TELEGRAM_CREAT_BOT_TOKEN}/getFile?file_id={file_id}").json()
            if file_res.get("ok"):
                return f"https://api.telegram.org/file/bot{TELEGRAM_CREAT_BOT_TOKEN}/{file_res['result']['file_path']}"
    except Exception as e:
        print(e)
    return None

def clean_server(video_path):
    if video_path and os.path.exists(video_path): os.remove(video_path)
    os.system("rm -rf /mnt/volume_fra1_1786451349368/tmp/*")

# ==========================================
# 3. TELEGRAM BOT HANDLERS
# ==========================================
@bot.message_handler(commands=['start', 'flights'])
def send_flights_list(message):
    if not is_authorized(message): return
    
    global GLOBAL_FLIGHTS
    GLOBAL_FLIGHTS = get_all_flights()
    
    if not GLOBAL_FLIGHTS:
        bot.send_message(message.chat.id, "❌ לא מצאתי טיסות בקובץ הנתונים.")
        return

    text_msg = "🛫 *טיסות זמינות ליצירת וידאו:*\n\n"
    for i, f in enumerate(GLOBAL_FLIGHTS):
        origin = f.get('origin_iata', '???').upper()
        dest = f.get('destination_iata', '???').upper()
        date = str(f.get('departure_date_raw', 'TBD'))[:6].strip()
        price = str(f.get('price_raw', '???')).replace(' ', '')
        text_msg += f"[{i+1}] {origin} ➡️ {dest} | {date} | {price}\n"
    
    text_msg += "\n*השב לי עם מספר הטיסה שתרצה ליצור לה וידאו (לדוגמה: 19):*"
    msg = bot.send_message(message.chat.id, text_msg, parse_mode='Markdown')
    bot.register_next_step_handler(msg, process_flight_selection)

def process_flight_selection(message):
    if not is_authorized(message): return
    
    try:
        choice = int(message.text.strip())
        if choice < 1 or choice > len(GLOBAL_FLIGHTS): raise ValueError
    except ValueError:
        bot.send_message(message.chat.id, "❌ קלט לא תקין. שלח /flights כדי לנסות שוב.")
        return

    selected_deal = GLOBAL_FLIGHTS[choice - 1]
    bot.send_message(message.chat.id, f"🎬 מתחיל לרנדר וידאו לטיסה מ-{selected_deal.get('origin_iata')} ל-{selected_deal.get('destination_iata')}...\nזה ייקח כ-7-10 דקות ⏳")

    # הכנת הנתונים
    origin_city = selected_deal.get("origin_city", "Unknown")
    origin_code = selected_deal.get("origin_iata", "").upper()
    dest_city = selected_deal.get("destination_city", "Unknown")
    dest_code = selected_deal.get("destination_iata", "").upper()
    date = selected_deal.get("departure_date_raw", "TBD")
    aircraft = selected_deal.get("aircraft_type", "Private Jet")
    seats = selected_deal.get("seats_available", "N/A")
    price = selected_deal.get("price_raw", "Request Price")
    deal_link = selected_deal.get("source_id", "https://flywithonyx.com")

tweet_text = f"""🚨 VIP EMPTY LEG DEAL 🚨
🛫 {origin_city} ({origin_code}) ➡️ 🛬 {dest_city} ({dest_code})
🗓️ {date}
🛩️ {aircraft} | 💺 {seats} Seats
💰 {price} (Total Aircraft)

🔗 Book this flight: {deal_link}

🤖 Need a custom route? Chat with our 24/7 AI Concierge: https://t.me/OnyxAirRadar_bot

#PrivateJet #EmptyLegs #LuxuryTravel"""


       # רינדור
    p1, p2, p3, music = get_smart_random_combo()
    props = {
        "titleToReplace": f"{origin_code} ➡️ {dest_code}",
        "subTitleToReplace": f"Price: {price} | Seats: {seats}",
        "video1": f"part1_{p1}.mp4", "video2": f"part2_{p2}.mp4", "video3": f"part3_{p3}.mp4", "music": music
    }
    
    try:
        cmd = f"TMPDIR=/mnt/volume_fra1_1786451349368/tmp npx remotion render HelloWorld {OUTPUT_VIDEO_PATH} --props='{json.dumps(props)}' --frames=0-539 --image-format=jpeg --concurrency=1"
        subprocess.run(cmd, shell=True, check=True, cwd="/mnt/volume_fra1_1786451349368/video-generator")
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ שגיאה ברינדור הוידאו: {e}")
        return

    # העלאה
    bot.send_message(message.chat.id, "✅ הרינדור הסתיים! שולח את הקובץ ומרים אוטומציה ב-Make...")
    video_url = upload_to_telegram_and_get_url(OUTPUT_VIDEO_PATH, tweet_text)
    
    if video_url:
        data = {
            'caption': tweet_text,
            'origin': origin_code, 'destination': dest_code,
            'price': price, 'date': date, 'video_url': video_url
        }
        res = requests.post(MAKE_WEBHOOK_URL, json=data)
        if res.status_code == 200:
            bot.send_message(message.chat.id, "🚀 שוגר בהצלחה ל-Make.com (הפוסט יעלה בתוך רגע לאינסטגרם ו-X)!")
        else:
            bot.send_message(message.chat.id, f"⚠️ נשלח, אבל Make החזיר שגיאה: {res.status_code}")
    
    clean_server(OUTPUT_VIDEO_PATH)

# ==========================================
# RUN BOT
# ==========================================
if __name__ == "__main__":
    print("[*] Bot is running and listening for commands...")
    bot.infinity_polling()
