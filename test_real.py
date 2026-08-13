import os
import requests
from dotenv import load_dotenv

load_dotenv()
TELEGRAM_CREAT_BOT_TOKEN = os.getenv("TELEGRAM_CREAT_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
MAKE_WEBHOOK_URL = "https://hook.eu1.make.com/mvudpjo9r7pdbfaqkydj66wwuc2939jq"
# הנתיב המדויק אליו העלית את הקובץ הרגע
VIDEO_PATH = "/root/onyx/video-generator/public/test.mp4"

def test_real_flow():
    if not os.path.exists(VIDEO_PATH):
        print(f"[!] Error: File not found at {VIDEO_PATH}")
        return

    print("[*] Uploading REAL test video to Telegram CDN...")
    url = f"https://api.telegram.org/bot{TELEGRAM_CREAT_BOT_TOKEN}/sendVideo"
    caption = "🚨 REAL VIDEO TEST 🚨\nTesting the Telegram to Make.com flow!"

    try:
        with open(VIDEO_PATH, 'rb') as f:
            response = requests.post(url, data={'chat_id': TELEGRAM_CHAT_ID, 'caption': caption}, files={'video': f})
        
        res_data = response.json()
        if res_data.get("ok"):
            print("[+] Uploaded to Telegram! Extracting direct link...")
            file_id = res_data['result']['video']['file_id']
            get_file_url = f"https://api.telegram.org/bot{TELEGRAM_CREAT_BOT_TOKEN}/getFile?file_id={file_id}"
            file_res = requests.get(get_file_url).json()
            
            if file_res.get("ok"):
                file_path = file_res['result']['file_path']
                direct_url = f"https://api.telegram.org/file/bot{TELEGRAM_CREAT_BOT_TOKEN}/{file_path}"
                
                print("[*] Sending Video URL to Make.com Webhook...")
                data = {
                    'caption': caption,
                    'origin': 'TST',
                    'destination': 'TST',
                    'price': '$999',
                    'date': '2026-12-31',
                    'video_url': direct_url
                }
                make_res = requests.post(MAKE_WEBHOOK_URL, json=data)
                
                if make_res.status_code == 200:
                    print("[+] SUCCESS! Make.com received the data. Go check Instagram!")
                else:
                    print(f"[!] Make.com returned status: {make_res.status_code}")
        else:
            print(f"[!] Telegram upload failed: {res_data}")
    except Exception as e:
        print(f"[!] Error: {e}")

if __name__ == "__main__":
    test_real_flow()
