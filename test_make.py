import requests
import os

MAKE_WEBHOOK_URL = "https://hook.eu1.make.com/mvudpjo9r7pdbfaqkydj66wwuc2939jq"
DUMMY_FILE = "dummy_video.mp4"

print("[*] Creating a dummy video file...")
# יצירת קובץ דמה בשנייה אחת
with open(DUMMY_FILE, "w") as f:
    f.write("This is not a real video, just a test for Make.com!")

data = {
    'caption': '🚨 TEST POST 🚨\nTesting the Make.com Webhook connection!',
    'origin': 'TLV',
    'destination': 'JFK',
    'price': '$999',
    'date': '2026-12-31'
}

print("[*] Sending DUMMY data and file directly to Make.com...")
try:
    with open(DUMMY_FILE, 'rb') as f:
        files = {'video_file': (DUMMY_FILE, f, 'video/mp4')}
        response = requests.post(MAKE_WEBHOOK_URL, data=data, files=files)
        
    print(f"[*] Make.com Response Status: {response.status_code}")
    if response.status_code == 200:
        print("[+] SUCCESS! Make.com received the file. Go check your scenario!")
    else:
        print(f"[!] FAILED. Make.com returned: {response.text}")
        
except Exception as e:
    print(f"[!] Error: {e}")

# ניקוי קובץ הדמה
if os.path.exists(DUMMY_FILE):
    os.remove(DUMMY_FILE)
