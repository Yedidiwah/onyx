import json
import os

def clean_airport_code(code):
    if not code:
        return ""
    code = str(code).strip().upper()
    if len(code) == 4 and code.startswith('K'):
        return code[1:]
    return code

def generate_tweets():
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
    
    # לוקח את 3 הטיסות הזולות ביותר (או כמה שיש אם יש פחות מ-3)
    top_flights = valid_flights[:3]
    
    print(f"\n🔥 נמצאו 3 הטיסות הזולות ביותר במערכת:\n")
    
    for i, (price_val, best) in enumerate(top_flights, 1):
        origin_city = best.get("origin_city", "Unknown")
        dest_city = best.get("destination_city", "Unknown")
        
        origin_raw = best.get("origin") or best.get("origin_code") or best.get("departure") or best.get("from") or ""
        origin_code = clean_airport_code(origin_raw)
        
        dest_raw = best.get("destination") or best.get("destination_code") or best.get("arrival") or best.get("to") or ""
        dest_code = clean_airport_code(dest_raw)
        
        link = best.get("booking_link") or "https://flywithonyx.com/"
        
        if (not origin_code or not dest_code) and "empty-legs/" in link:
            try:
                parts = link.split("empty-legs/")[1].split("-")
                if len(parts) >= 2:
                    if not origin_code:
                        origin_code = clean_airport_code(parts[0])
                    if not dest_code:
                        dest_code = clean_airport_code(parts[1])
            except Exception:
                pass

        date = best.get("departure_date_raw", "TBD")
        price = best.get("price_raw", "Request Price")
        seats = best.get("seats") or best.get("capacity") or best.get("passengers", "7")
        
        route_str = f"{origin_city} ({origin_code}) ➡️ {dest_city} ({dest_code})" if origin_code and dest_code else f"{origin_city} ➡️ {dest_city}"
        
        tweet = (
            f"🚨 Empty Leg Alert 🚨\n\n"
            f"✈️ Route: {route_str}\n"
            f"📅 Date: {date}\n"
            f"👥 Capacity: Up to {seats} passengers\n"
            f"💰 Price: {price}\n\n"
            f"Book now: {link}\n"
            f"Browse all live private flights: https://flywithonyx.com/\n\n"
            f"#PrivateJet #EmptyLegs #LuxuryTravel #Affiliate"
        )
        
        print("="*50)
        print(f"👇 ציוץ מספר {i} להעתקה 👇")
        print("="*50 + "\n")
        print(tweet)
        print("\n" + "="*50 + "\n")

if __name__ == "__main__":
    generate_tweets()
