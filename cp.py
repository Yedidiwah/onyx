import json
import os
import subprocess
import requests
import sys
import random
from dotenv import load_dotenv

# ==========================================
# 1. CONFIGURATION & ENVIRONMENT VARIABLES
# ==========================================
load_dotenv()

TELEGRAM_CREAT_BOT_TOKEN = os.getenv("TELEGRAM_CREAT_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
MAKE_WEBHOOK_URL = "https://hook.eu1.make.com/mvudpjo9r7pdbfaqkydj66wwuc2939jq"
HISTORY_FILE = "history.json"

# ==========================================
# 2. DATA HANDLING FUNCTIONS
# ==========================================
def get_all_flights(json_path="data/flights.json"):
    if not os.path.exists(json_path):
        return None, f"[!] Error: Data file not found at {json_path}"
    
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    flights = data if isinstance(data, list) else data.get("flights", [])
    if not flights:
        return None, "[!] No active flights found in the data."
        
    return flights, "Success"

def get_smart_random_combo():
    """
    Generates a unique combination of videos and music, 
    ensuring it hasn't been used in the last 50 generations.
    """
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
        
        # Ensure combination is not in the recent history
        if combo_str not in history[-50:]:
            history.append(combo_str)
            with open(HISTORY_FILE, 'w') as f:
                json.dump(history[-50:], f)
            print(f"[+] Smart Randomizer selected: Part1={p1}, Part2={p2}, Part3={p3}, Music={music}")
            return p1, p2, p3, music

# ==========================================
# 3. VIDEO GENERATION (REMOTION)
# ==========================================
def generate_video_with_remotion(deal_data):
    print("[*] Starting Remotion video rendering via npm script...")
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
        print(f"[!] Video generation failed: {e}")
        return None

# ==========================================
# 4. EXTERNAL INTEGRATIONS (WEBHOOK & TELEGRAM)
# ==========================================
def send_to_make_webhook(video_path, deal_data, caption):
    """
    Sends the generated video and flight data directly to Make.com Webhook.
    Make.com will handle saving to Airtable and posting to Instagram.
    """
    print("[*] Uploading video and data to Make.com Webhook...")
    try:
        with open(video_path, 'rb') as video_file:
            files = {'video': video_file}
            data = {
                'caption': caption,
                'origin': deal_data.get('origin_iata', 'TBD'),
                'destination': deal_data.get('destination_iata', 'TBD'),
                'price': deal_data.get('price_raw', 'TBD'),
                'date': deal_data.get('departure_date_raw', 'TBD')
            }
            response = requests.post(MAKE_WEBHOOK_URL, data=data, files=files)
            
            if response.status_code == 200:
                print("[+] Successfully sent all data to Make.com!")
            else:
                print(f"[!] Make.com Webhook responded with status: {response.status_code}")
    except Exception as e:
        print(f"[!] Error sending to Make.com Webhook: {e}")

def send_to_telegram(video_path, caption):
    if not TELEGRAM_CREAT_BOT_TOKEN or not TELEGRAM_CHAT_ID: return
    print("[*] Sending video and caption to Telegram for backup...")
    url = f"https://api.telegram.org/bot{TELEGRAM_CREAT_BOT_TOKEN}/sendVideo"
    try:
        with open(video_path, 'rb') as video_file:
            requests.post(url, data={'chat_id': TELEGRAM_CHAT_ID, 'caption': caption}, files={'video': video_file})
            print("[+] Successfully sent video to Telegram!")
    except Exception as e:
        print(f"[!] Error sending to Telegram: {e}")

# ==========================================
# 5. CLEANUP & MAIN PROCESS
# ==========================================
def clean_server(video_path):
    print("[*] Cleaning up temporary files to save server disk space...")
    if video_path and os.path.exists(video_path):
        os.remove(video_path)
    os.system("rm -rf /tmp/remotion*")
    print("[+] Server is clean and ready for the next video!\n")

def process_empty_leg():
    flights, status = get_all_flights()
    if not flights: 
        print(status)
        return

    print("\n" + "="*85)
    print("   AVAILABLE FLIGHTS (Choose a number from the brackets)")
    print("="*85)
    
    # Render 3 columns with dates
    for i in range(0, len(flights), 3):
        line_str = ""
        for j in range(3):
            if i + j < len(flights):
                f = flights[i+j]
                idx = i + j + 1
                origin = f.get('origin_iata', '???').upper()
                dest = f.get('destination_iata', '???').upper()
                date_full = str(f.get('departure_date_raw', 'TBD'))
                date_short = date_full[:6].strip()
                price = str(f.get('price_raw', '???')).replace(' ', '')
                
                flight_str = f"[{idx:02d}] {origin}-{dest} {date_short} {price}"
                line_str += f"{flight_str:<28}"
        print(line_str)
        
    print("="*85)

    try:
        choice = int(input("\nEnter the flight number you want to generate: "))
    except ValueError:
        print("[!] Invalid input. Please enter a number.")
        sys.exit()

    if choice < 1 or choice > len(flights):
        print("[!] Invalid choice. Number out of range.")
        sys.exit()
        
    selected_deal = flights[choice - 1]

    print(f"\n[*] Processing flight from {selected_deal.get('origin_iata')} to {selected_deal.get('destination_iata')}...")

    origin_city = selected_deal.get("origin_city", selected_deal.get("origin_airport_name", "Unknown"))
    origin_code = selected_deal.get("origin_iata", "").upper()
    dest_city = selected_deal.get("destination_city", selected_deal.get("destination_airport_name", "Unknown"))
    dest_code = selected_deal.get("destination_iata", "").upper()

    date = selected_deal.get("departure_date_raw", "TBD")
    aircraft = selected_deal.get("aircraft_type", "Private Jet")
    seats = selected_deal.get("seats_available", "N/A")
    price_raw = selected_deal.get("price_raw", "Request Price")

    tweet_text = f"""🚨 VIP EMPTY LEG DEAL 🚨
🛫 {origin_city} ({origin_code}) ➡️ 🛬 {dest_city} ({dest_code})
🗓️ {date}
🛩️ {aircraft} | 💺 {seats} Seats
💰 {price_raw} (Total Aircraft)

🔗 Link in bio to book!
#PrivateJet #EmptyLegs #LuxuryTravel"""

    # 1. Generate Video
    video_path = generate_video_with_remotion(selected_deal)
    
    if video_path and os.path.exists(video_path):
        # 2. Send to Make.com Webhook (Airtable + Instagram)
        send_to_make_webhook(video_path, selected_deal, tweet_text)
        
        # 3. Send to Telegram (Backup)
        send_to_telegram(video_path, tweet_text)
        
        # 4. Clean up Server
        clean_server(video_path)

if __name__ == "__main__":
    process_empty_leg()
