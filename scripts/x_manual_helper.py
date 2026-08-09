import json
import os

def generate_tweet():
    json_path = "data/flights.json"
    if not os.path.exists(json_path):
        print("❌ Data file not found.")
        return
    
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    flights = data if isinstance(data, list) else data.get("flights", [])
    if not flights:
        print("❌ No active flights found.")
        return
        
    valid_flights = []
    for flight in flights:
        try:
            price = float(str(flight.get("price_amount", "")).replace(',', ''))
            valid_flights.append((price, flight))
        except ValueError:
            continue
            
    if not valid_flights:
        print("❌ No priced flights found.")
        return
        
    valid_flights.sort(key=lambda x: x[0])
    best = valid_flights[0][1]
    
    origin = best.get("origin_city", "Unknown")
    dest = best.get("destination_city", "Unknown")
    date = best.get("departure_date_raw", "TBD")
    price = best.get("price_raw", "Request Price")
    link = best.get("booking_link") or "https://flywithonyx.com/"
    
    tweet = (
        f"🚨 Empty Leg Alert 🚨\n\n"
        f"✈️ {origin} ➡️ {dest}\n"
        f"📅 Date: {date}\n"
        f"💰 Price: {price}\n\n"
        f"Book now: {link}\n"
        f"Browse all live private flights: https://flywithonyx.com/\n\n"
        f"#PrivateJet #EmptyLegs #Aviation #LuxuryTravel #Onyx"
    )
    
    print("\n" + "="*50)
    print("👇 העתק והדבק את הטקסט הבא ל-X.COM 👇")
    print("="*50 + "\n")
    print(tweet)
    print("\n" + "="*50)

if __name__ == "__main__":
    generate_tweet()
