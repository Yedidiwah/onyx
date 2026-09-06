import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()

MCP_TOKEN = os.getenv("VILLIERS_MCP_TOKEN")
MCP_URL = "https://mcp.villiers.ai/mcp"

def test_get_estimate():
    if not MCP_TOKEN:
        print("❌ חסר טוקן VILLIERS_MCP_TOKEN בקובץ ה-.env")
        return

    headers = {
        "Authorization": f"Bearer {MCP_TOKEN}",
        "Content-Type": "application/json"
    }

    # עדכנו את הפרמטרים לפי דרישת השרת: origin, destination ו-date
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "get_jet_estimate",
            "arguments": {
                "origin": "LHR",
                "destination": "NCE",
                "date": "2026-09-15"
            }
        }
    }

    print("⏳ שולח בקשת תמחור מעודכנת ל-Villiers (London -> Nice)...")
    
    try:
        response = requests.post(MCP_URL, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
        
        print("\n✅ התקבלה תשובה בהצלחה:")
        print(json.dumps(data, indent=2, ensure_ascii=False))
        
    except requests.exceptions.RequestException as e:
        print(f"\n❌ שגיאה בחיבור לשרת: {e}")
        if response.text:
            print(f"תוכן השגיאה: {response.text}")

if __name__ == "__main__":
    test_get_estimate()
