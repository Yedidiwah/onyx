import json
import os
import tweepy
from dotenv import load_dotenv

# טעינת המפתחות מקובץ ה-.env
load_dotenv()

API_KEY = os.getenv("X_API_KEY")
API_SECRET = os.getenv("X_API_SECRET")
ACCESS_TOKEN = os.getenv("X_ACCESS_TOKEN")
ACCESS_TOKEN_SECRET = os.getenv("X_ACCESS_TOKEN_SECRET")

def get_best_deal(json_path="data/flights.json"):
    if not os.path.exists(json_path):
        return None, f"❌ Error: Data file not found at {json_path}"
        
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    flights = data if isinstance(data, list) else data.get("flights", [])
    if not flights:
        return None, "❌ No active flights found in the data."
        
    valid_flights = []
    for flight in flights:
        try:
            raw_price = str(flight.get("price_amount", "")).replace(',', '')
            price = float(raw_price)
            valid_flights.append((price, flight))
        except ValueError:
            continue
    
    if not valid_flights:
        return None, "❌ No priced flights found to generate a deal."
        
    # מיון הטיסות מהזולה ליקרה
    valid_flights.sort(key=lambda x: x[0])
    return valid_flights[0][1], "Success"

def post_to_x():
    if not all([API_KEY, API_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET]):
        print("❌ Error: Missing Twitter API credentials in .env file.")
        return

    best_deal, status = get_best_deal()
    
    if not best_deal:
        print(status)
        return
        
    origin_city = best_deal.get("origin_city", best_deal.get("origin_airport_name", "Unknown"))
    origin_code = best_deal.get("origin_iata", "").upper()
    dest_city = best_deal.get("destination_city", best_deal.get("destination_airport_name", "Unknown"))
    dest_code = best_deal.get("destination_iata", "").upper()
    
    date = best_deal.get("departure_date_raw", best_deal.get("departure_date_iso", "TBD"))
    time = best_deal.get("departure_time", "TBD")
    seats = best_deal.get("seats_available", "N/A")
    aircraft = best_deal.get("aircraft_type", "Private Jet")
    price_raw = best_deal.get("price_raw", "Request Price")
    
    booking_link = best_deal.get("booking_link") or best_deal.get("tracking_link") or best_deal.get("rss_link") or "https://flywithonyx.com/"
    
    tweet_text = f"""🚨 EMPTY LEG DEAL 🚨

🛫 {origin_city} ({origin_code}) ➡️ 🛬 {dest_city} ({dest_code})
🗓️ {date}, {time}
🛩️ {aircraft} | 💺 {seats} Seats
💰 {price_raw} (Total Aircraft!)

🔗 Book this flight: {booking_link}
🌐 Browse all live deals: https://flywithonyx.com/

#PrivateJet #EmptyLegs #Affiliate"""

    try:
        client = tweepy.Client(
            consumer_key=API_KEY,
            consumer_secret=API_SECRET,
            access_token=ACCESS_TOKEN,
            access_token_secret=ACCESS_TOKEN_SECRET
        )
        
        response = client.create_tweet(text=tweet_text)
        print(f"✅ SUCCESS! Tweet posted automatically: https://x.com/user/status/{response.data['id']}")
        
    except Exception as e:
        print(f"❌ Failed to post tweet. Error: {e}")

if __name__ == "__main__":
    post_to_x()

