import json
import os
import subprocess
import requests
import random
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

# ==========================================
# 2. HELPER FUNCTIONS
# ==========================================
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
    # העלאה לטלגרם כדי לקבל את הלינק הנדרש למערכת Make
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
        print(f"[!] Error uploading to Telegram: {e}")
    return None

def clean_server(video_path):
    if video_path and os.path.exists(video_path): os.remove(video_path)
    os.system("rm -rf /mnt/volume_fra1_1786451349368/tmp/*")

def send_telegram_notification(text):
    # פונקציה חדשה לשליחת הודעת סיכום חזרה אליך
    url = f"https://api.telegram.org/bot{TELEGRAM_CREAT_BOT_TOKEN}/sendMessage"
    payload = {'chat_id': TELEGRAM_CHAT_ID, 'text': text, 'parse_mode': 'Markdown'}
    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"[!] Notification failed: {e}")

# ==========================================
# 3. MAIN AUTOMATION LOGIC
# ==========================================
def main():
    print("[*] Starting automated flight deal processing...")
    
    flights = get_all_flights()
    if not flights:
        print("❌ No flights found in data file.")
        return
    
    # בחירה רנדומלית
    selected_deal = random.choice(flights)
    
    origin_city = selected_deal.get("origin_city", "Unknown")
    origin_code = selected_deal.get("origin_iata", "").upper()
    dest_city = selected_deal.get("destination_city", "Unknown")
    dest_code = selected_deal.get("destination_iata", "").upper()
    date = selected_deal.get("departure_date_raw", "TBD")
    aircraft = selected_deal.get("aircraft_type", "Private Jet")
    seats = selected_deal.get("seats_available", "N/A")
    price = selected_deal.get("price_raw", "Request Price")
    deal_link = selected_deal.get("source_id", "https://flywithonyx.com")

    print(f"[*] Selected Flight: {origin_code} ➡️ {dest_code} | {date}")

    tweet_text = f"🚨 VIP EMPTY LEG DEAL 🚨\n🛫 {origin_city} ({origin_code}) ➡️ 🛬 {dest_city} ({dest_code})\n🗓️ {date}\n🛩️ {aircraft} | 💺 {seats} Seats\n💰 {price} (Total Aircraft)\n\n🔗 Book this flight: {deal_link}\n\n#PrivateJet #EmptyLegs"

    # רינדור הווידאו
    p1, p2, p3, music = get_smart_random_combo()
    props = {
        "titleToReplace": f"{origin_code} ➡️ {dest_code}",
        "subTitleToReplace": f"Price: {price} | Seats: {seats}",
        "video1": f"part1_{p1}.mp4", "video2": f"part2_{p2}.mp4", "video3": f"part3_{p3}.mp4", "music": music
    }
    
    print("[*] Rendering video (this takes about 7-10 minutes)...")
    try:
        # פקודת הרינדור עם הפתרון של ה-Volume לקבצים הזמניים
        cmd = f"TMPDIR=/mnt/volume_fra1_1786451349368/tmp npx remotion render HelloWorld {OUTPUT_VIDEO_PATH} --props='{json.dumps(props)}' --frames=0-539 --image-format=jpeg --concurrency=1"
        subprocess.run(cmd, shell=True, check=True, cwd="/mnt/volume_fra1_1786451349368/video-generator")
    except Exception as e:
        print(f"❌ Video rendering failed: {e}")
        return

    # העלאה ושיגור למייק
    print("[*] Render complete. Uploading to Telegram to get CDN URL...")
    video_url = upload_to_telegram_and_get_url(OUTPUT_VIDEO_PATH, tweet_text)
    
    if video_url:
        print(f"[*] Video uploaded. Triggering Make.com Webhook...")
        data = {
            'caption': tweet_text,
            'origin': origin_code, 'destination': dest_code,
            'price': price, 'date': date, 'video_url': video_url
        }
        res = requests.post(MAKE_WEBHOOK_URL, json=data)
        if res.status_code == 200:
            print("✅ Successfully sent to Make.com!")
            
            # שליחת הודעת סיכום לטלגרם שלך
            success_msg = f"🤖 *אוטומציה סיימה בהצלחה!*\n\n🛫 טיסה נבחרה: {origin_code} ➡️ {dest_code}\n🗓️ תאריך: {date}\n💰 מחיר: {price}\n\n✅ הווידאו נוצר ושוגר ל-Make (בדרך לאינסטגרם ו-X)."
            send_telegram_notification(success_msg)
        else:
            print(f"⚠️ Sent to Make.com, but received error status: {res.status_code}")
    else:
        print("❌ Failed to upload video to Telegram.")
    
    print("[*] Cleaning up temporary files...")
    clean_server(OUTPUT_VIDEO_PATH)
    print("[*] Automation run finished successfully!")

if __name__ == "__main__":
    main()
