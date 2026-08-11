import json
import os
import subprocess
import requests
import sys
import random
from dotenv import load_dotenv

# ==========================================
# 1. LOAD ENVIRONMENT VARIABLES
# ==========================================
load_dotenv()

AIRTABLE_API_KEY = os.getenv("AIRTABLE_API_KEY")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID")
AIRTABLE_TABLE_NAME = "Empty_Legs" 
TELEGRAM_CREAT_BOT_TOKEN = os.getenv("TELEGRAM_CREAT_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
HISTORY_FILE = "history.json"

def get_all_flights(json_path="data/flights.json"):
    if not os.path.exists(json_path):
        return None, f"❌ Error: Data file not found at {json_path}"
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    flights = data if isinstance(data, list) else data.get("flights", [])
    if not flights:
        return None, "❌ No active flights found in the data."
    return flights, "Success"

def save_to_airtable(deal_data, tweet_text):
    if not AIRTABLE_API_KEY or not AIRTABLE_BASE_ID: return
    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_NAME}"
    headers = {"Authorization": f"Bearer {AIRTABLE_API_KEY}", "Content-Type": "application/json"}
    payload = {"fields": {"Route": f"{deal_data.get('origin_iata')} -> {deal_data.get('destination_iata')}", "Price": deal_data.get("price_raw"), "Date": deal_data.get("departure_date_raw"), "CaptionText": tweet_text, "Status": "Generated via Script"}}
    requests.post(url, json=payload, headers=headers)

# מנגנון בחירה חכמה עם זיכרון
def get_smart_random_combo():
    music_options = ["m1.mp3", "m2.mp3", "m4.mp3", "m5.mp3"]
    history = []
    
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r') as f:
                history = json.load(f)
        except:
            history = []
            
    while True:
        p1 = random.randint(1, 6)
        p2 = random.randint(1, 6)
        p3 = random.randint(1, 7)
        music = random.choice(music_options)
        combo_str = f"{p1}-{p2}-{p3}-{music}"
        
        # מוודא שהקומבינציה לא נמצאת ב-50 האחרונות שיוצרו
        if combo_str not in history[-50:]:
            history.append(combo_str)
            with open(HISTORY_FILE, 'w') as f:
                json.dump(history[-50:], f)
            print(f"🧠 Smart Randomizer selected: Part1={p1}, Part2={p2}, Part3={p3}, Music={music}")
            return p1, p2, p3, music

def generate_video_with_remotion(deal_data):
    print("🎬 Starting Remotion video rendering via npm script...")
    output_path = "output_deal.mp4"

    p1, p2, p3, music = get_smart_random_combo()

    props = {
        "titleToReplace": f"{deal_data.get('origin_iata')} ➡️ {deal_data.get('destination_iata')}",
        "subTitleToReplace": f"Price: {deal_data.get('price_raw')} | Seats: {deal_data.get('seats_available')}",
        "video1": f"part1_{p1}.mp4",
        "video2": f"part2_{p2}.mp4",
        "video3": f"part3_{p3}.mp4",
        "music": music
    }

    try:
        cmd = f"npm run render-deal -- --props='{json.dumps(props)}' --frames=0-539"
        subprocess.run(cmd, shell=True, check=True, cwd="./video-generator")
        return output_path
    except Exception as e:
        print(f"❌ Video generation failed: {e}")
        return None

def send_to_telegram(video_path, caption):
    if not TELEGRAM_CREAT_BOT_TOKEN or not TELEGRAM_CHAT_ID: return
    print("📤 Sending video and text to Telegram...")
    url = f"https://api.telegram.org/bot{TELEGRAM_CREAT_BOT_TOKEN}/sendVideo"
    try:
        with open(video_path, 'rb') as video_file:
            requests.post(url, data={'chat_id': TELEGRAM_CHAT_ID, 'caption': caption}, files={'video': video_file})
            print("✅ Successfully sent video to Telegram!")
    except Exception as e:
        print(f"❌ Error sending to Telegram: {e}")

# פונקציית ניקיון אוטומטית שומרת על השרת שלך מבריק
def clean_server(video_path):
    print("🧹 Cleaning up temporary files to save server space...")
    if video_path and os.path.exists(video_path):
        os.remove(video_path)
    os.system("rm -rf /tmp/remotion*")
    print("✨ Server is clean and ready for the next video!")

def process_empty_leg():
    flights, status = get_all_flights()
    if not flights: return

    for i in range(0, len(flights), 3):
        line_str = ""
        for j in range(3):
            if i + j < len(flights):
                f = flights[i+j]
                idx = i + j + 1
                flight_str = f"[{idx:02d}] {f.get('origin_iata', '???').upper()}-{f.get('destination_iata', '???').upper()} {str(f.get('price_raw', '???')).replace(' ', '')}"
                line_str += f"{flight_str:<28}"
        print(line_str)
        
    choice = int(input("\nהכנס את מספר הטיסה: "))
    selected_deal = flights[choice - 1]

    tweet_text = f"""🚨 VIP EMPTY LEG DEAL 🚨
🛫 {selected_deal.get("origin_city", selected_deal.get("origin_airport_name", "Unknown"))} ({selected_deal.get("origin_iata", "").upper()}) ➡️ 🛬 {selected_deal.get("destination_city", selected_deal.get("destination_airport_name", "Unknown"))} ({selected_deal.get("destination_iata", "").upper()})
🗓️ {selected_deal.get("departure_date_raw", "TBD")}
🛩️ {selected_deal.get("aircraft_type", "Private Jet")} | 💺 {selected_deal.get("seats_available", "N/A")} Seats
💰 {selected_deal.get("price_raw", "Request Price")} (Total Aircraft)

🔗 Link in bio to book!
#PrivateJet #EmptyLegs #LuxuryTravel"""

    save_to_airtable(selected_deal, tweet_text)
    video_path = generate_video_with_remotion(selected_deal)
    
    if video_path:
        send_to_telegram(video_path, tweet_text)
        clean_server(video_path) # קריאה למנקה

if __name__ == "__main__":
    process_empty_leg()
