import json
import os
import subprocess
import requests
import sys
from dotenv import load_dotenv

# ==========================================
# 1. LOAD ENVIRONMENT VARIABLES
# ==========================================
load_dotenv()

# הגדרות שנוספו עבור Airtable ו-Telegram
AIRTABLE_API_KEY = os.getenv("AIRTABLE_API_KEY")
AIRTABLE_BASE_ID = os.getenv("AIRTABLE_BASE_ID")
AIRTABLE_TABLE_NAME = "Empty_Legs" # ודא שזה שם הטבלה שלך
TELEGRAM_CREAT_BOT_TOKEN = os.getenv("TELEGRAM_CREAT_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def get_all_flights(json_path="data/flights.json"):
    """שולף את כל הטיסות הקיימות בקובץ ללא סינון אוטומטי"""
    if not os.path.exists(json_path):
        return None, f"❌ Error: Data file not found at {json_path}"

    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    flights = data if isinstance(data, list) else data.get("flights", [])
    if not flights:
        return None, "❌ No active flights found in the data."

    return flights, "Success"

def save_to_airtable(deal_data, tweet_text):
    if not AIRTABLE_API_KEY or not AIRTABLE_BASE_ID:
        print("⚠️ Skipping Airtable: Missing credentials.")
        return

    url = f"https://api.airtable.com/v0/{AIRTABLE_BASE_ID}/{AIRTABLE_TABLE_NAME}"
    headers = {
        "Authorization": f"Bearer {AIRTABLE_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "fields": {
            "Route": f"{deal_data.get('origin_iata')} -> {deal_data.get('destination_iata')}",
            "Price": deal_data.get("price_raw"),
            "Date": deal_data.get("departure_date_raw"),
            "CaptionText": tweet_text,
            "Status": "Generated via Script"
        }
    }

    response = requests.post(url, json=payload, headers=headers)
    if response.status_code in [200, 201]:
        print("✅ Deal successfully saved to Airtable!")
    else:
        print(f"❌ Failed to save to Airtable: {response.text}")

def generate_video_with_remotion(deal_data):
    print("🎬 Starting Remotion video rendering via npm script...")
    output_path = "output_deal.mp4"

    props = {
        "titleToReplace": f"{deal_data.get('origin_iata')} ➡️ {deal_data.get('destination_iata')}",
        "subTitleToReplace": f"Price: {deal_data.get('price_raw')} | Seats: {deal_data.get('seats_available')}"
    }

    try:
        # שימוש ב-npm run מריץ את הבינארי המקומי בלי שגיאות נתיבים
        cmd = f"npm run render-deal -- --props='{json.dumps(props)}'"
        subprocess.run(cmd, shell=True, check=True, cwd="./video-generator")

        print(f"✅ Video successfully generated at {output_path}")
        return output_path
    except Exception as e:
        print(f"❌ Video generation failed: {e}")
        return None

def send_to_telegram(video_path, caption):
    if not TELEGRAM_CREAT_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ Skipping Telegram: Missing credentials.")
        return

    print("📤 Sending video and text to Telegram...")
    url = f"https://api.telegram.org/bot{TELEGRAM_CREAT_BOT_TOKEN}/sendVideo"

    try:
        with open(video_path, 'rb') as video_file:
            files = {'video': video_file}
            data = {'chat_id': TELEGRAM_CHAT_ID, 'caption': caption}
            response = requests.post(url, data=data, files=files)

            if response.status_code == 200:
                print("✅ Successfully sent video to Telegram!")
            else:
                print(f"❌ Failed to send to Telegram: {response.text}")
    except Exception as e:
        print(f"❌ Error sending to Telegram: {e}")

def process_empty_leg():
    # 1. שליפת כל הטיסות
    flights, status = get_all_flights()

    if not flights:
        print(status)
        return

    # 2. הצגת תפריט בחירה למשתמש
    print("\n" + "="*80)
    print("🔍 הטיסות הזמינות לפירסום:")
    print("="*80)
    for i, f in enumerate(flights, 1):
        origin = f.get('origin_iata', 'N/A').upper()
        dest = f.get('destination_iata', 'N/A').upper()
        date = f.get('departure_date_raw', f.get('departure_date_iso', 'TBD'))
        price = f.get('price_raw', 'N/A')
        seats = f.get('seats_available', 'N/A')
        
        print(f"[{i}] from: {origin} | to: {dest} | date: {date} | cost: {price} | seats: {seats}")
    print("="*80)

    try:
        choice = int(input("\nchoose flight: "))
        if choice < 1 or choice > len(flights):
            print("X err, no such number.")
            sys.exit()
        selected_deal = flights[choice - 1]
    except ValueError:
        print("number only.")
        sys.exit()

    print(f"\n🚀 מעבד את הטיסה מ-{selected_deal.get('origin_iata')} ל-{selected_deal.get('destination_iata')}...")

    # 3. חילוץ נתוני הטיסה הנבחרת
    origin_city = selected_deal.get("origin_city", selected_deal.get("origin_airport_name", "Unknown"))
    origin_code = selected_deal.get("origin_iata", "").upper()
    dest_city = selected_deal.get("destination_city", selected_deal.get("destination_airport_name", "Unknown"))
    dest_code = selected_deal.get("destination_iata", "").upper()

    date = selected_deal.get("departure_date_raw", selected_deal.get("departure_date_iso", "TBD"))
    time = selected_deal.get("departure_time", "TBD")
    seats = selected_deal.get("seats_available", "N/A")
    aircraft = selected_deal.get("aircraft_type", "Private Jet")
    price_raw = selected_deal.get("price_raw", "Request Price")

    # שליפת קישור ההזמנה
    booking_link = selected_deal.get("booking_link") or selected_deal.get("tracking_link") or selected_deal.get("rss_link") or "https://flywithonyx.com/"

    # 4. הרכבת הציוץ
    tweet_text = f"""🚨 EMPTY LEG DEAL 🚨
🛫 {origin_city} ({origin_code}) ➡️ 🛬 {dest_city} ({dest_code})
🗓️ {date}, {time}
🛩️ {aircraft} | 💺 {seats} Seats
💰 {price_raw} (Total Aircraft!)

🔗 Book this flight: {booking_link}
🌐 Browse all live deals: https://flywithonyx.com/

#PrivateJet #EmptyLegs #Affiliate"""

    print("\nDrafting Text:\n" + "-"*30)
    print(tweet_text)
    print("-"*30 + "\n")

    # 5. ביצוע הפעולות מול השירותים החיצוניים
    save_to_airtable(selected_deal, tweet_text)
    
    video_path = generate_video_with_remotion(selected_deal)
    
    if video_path and os.path.exists(video_path):
        send_to_telegram(video_path, tweet_text)

if __name__ == "__main__":
    process_empty_leg()
