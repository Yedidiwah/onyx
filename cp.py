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
    if not AIRTABLE_API_KEY or not AIRTABLE_BASE_ID:
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
    requests.post(url, json=payload, headers=headers)

def generate_video_with_remotion(deal_data):
    print("🎬 Starting Remotion video rendering via npm script...")
    output_path = "output_deal.mp4"

    part1_idx = random.randint(1, 6)
    part2_idx = random.randint(1, 6)
    part3_idx = random.randint(1, 7) 

    props = {
        "titleToReplace": f"{deal_data.get('origin_iata')} ➡️ {deal_data.get('destination_iata')}",
        "subTitleToReplace": f"Price: {deal_data.get('price_raw')} | Seats: {deal_data.get('seats_available')}",
        "video1": f"part1_{part1_idx}.mp4",
        "video2": f"part2_{part2_idx}.mp4",
        "video3": f"part3_{part3_idx}.mp4"
    }

    try:
        cmd = f"npm run render-deal -- --props='{json.dumps(props)}' --frames=0-539"
        subprocess.run(cmd, shell=True, check=True, cwd="./video-generator")
        return output_path
    except Exception as e:
        print(f"❌ Video generation failed: {e}")
        return None

def send_to_telegram(video_path, caption):
    if not TELEGRAM_CREAT_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return

    print("📤 Sending video and text to Telegram...")
    url = f"https://api.telegram.org/bot{TELEGRAM_CREAT_BOT_TOKEN}/sendVideo"

    try:
        with open(video_path, 'rb') as video_file:
            files = {'video': video_file}
            data = {'chat_id': TELEGRAM_CHAT_ID, 'caption': caption}
            requests.post(url, data=data, files=files)
            print("✅ Successfully sent video to Telegram!")
    except Exception as e:
        print(f"❌ Error sending to Telegram: {e}")

def process_empty_leg():
    flights, status = get_all_flights()

    if not flights:
        print(status)
        return

    print("\n" + "="*85)
    print("🔍 הטיסות הזמינות (3 בשורה - בחר מספר מהסוגריים המרובעים):")
    print("="*85)
    
    for i in range(0, len(flights), 3):
        line_str = ""
        for j in range(3):
            if i + j < len(flights):
                f = flights[i+j]
                idx = i + j + 1
                origin = f.get('origin_iata', '???').upper()
                dest = f.get('destination_iata', '???').upper()
                date_full = str(f.get('departure_date_raw', 'TBD'))
                date_short = date_full[:6].replace(' ', '') if len(date_full) >= 6 else date_full
                price = str(f.get('price_raw', '???')).replace(' ', '')
                seats = f.get('seats_available', '?')
                
                flight_str = f"[{idx:02d}] {origin}-{dest} {date_short} {price} ({seats}s)"
                line_str += f"{flight_str:<28}"
        print(line_str)
        
    print("="*85)

    try:
        choice = int(input("\nהכנס את מספר הטיסה שתרצה להפוך לריל (למשל 1, 12, וכו'): "))
    except ValueError:
        print("❌ נא להזין מספר תקין בלבד.")
        sys.exit()

    if choice < 1 or choice > len(flights):
        print("❌ בחירה שגויה, המספר חורג מהרשימה.")
        sys.exit()
        
    selected_deal = flights[choice - 1]

    print(f"\n🚀 מעבד את הטיסה מ-{selected_deal.get('origin_iata')} ל-{selected_deal.get('destination_iata')}...")

    origin_city = selected_deal.get("origin_city", selected_deal.get("origin_airport_name", "Unknown"))
    origin_code = selected_deal.get("origin_iata", "").upper()
    dest_city = selected_deal.get("destination_city", selected_deal.get("destination_airport_name", "Unknown"))
    dest_code = selected_deal.get("destination_iata", "").upper()

    date = selected_deal.get("departure_date_raw", selected_deal.get("departure_date_iso", "TBD"))
    time = selected_deal.get("departure_time", "TBD")
    seats = selected_deal.get("seats_available", "N/A")
    aircraft = selected_deal.get("aircraft_type", "Private Jet")
    price_raw = selected_deal.get("price_raw", "Request Price")
    booking_link = selected_deal.get("booking_link") or selected_deal.get("tracking_link") or selected_deal.get("rss_link") or "https://flywithonyx.com/"

    tweet_text = f"""🚨 EMPTY LEG DEAL 🚨
🛫 {origin_city} ({origin_code}) ➡️ 🛬 {dest_city} ({dest_code})
🗓️ {date}, {time}
🛩️ {aircraft} | 💺 {seats} Seats
💰 {price_raw} (Total Aircraft!)

🔗 Book this flight: {booking_link}
🌐 Browse all live deals: https://flywithonyx.com/

#PrivateJet #EmptyLegs #Affiliate"""

    save_to_airtable(selected_deal, tweet_text)
    video_path = generate_video_with_remotion(selected_deal)
    
    if video_path and os.path.exists(video_path):
        send_to_telegram(video_path, tweet_text)

if __name__ == "__main__":
    process_empty_leg()
