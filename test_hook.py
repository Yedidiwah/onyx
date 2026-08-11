import requests
import os

MAKE_WEBHOOK_URL = "https://hook.eu1.make.com/mvudpjo9r7pdbfaqkydj66wwuc2939jq"

# יצירת קובץ וידאו פיקטיבי בשנייה
with open("fake_video.mp4", "w") as f:
    f.write("This is a dummy video file for Make.com to learn the structure.")

print("[*] Sending dummy data to Make.com...")

with open("fake_video.mp4", "rb") as video_file:
    files = {'video': video_file}
    data = {
        'caption': '🚨 VIP EMPTY LEG DEAL 🚨\nTest Route\n$10,000',
        'origin': 'TLV',
        'destination': 'JFK',
        'price': '$10,000',
        'date': '12/12/2026'
    }
    response = requests.post(MAKE_WEBHOOK_URL, data=data, files=files)
    
print(f"[+] Done! Status: {response.status_code}")

# מחיקת הקובץ הפיקטיבי
os.remove("fake_video.mp4")
