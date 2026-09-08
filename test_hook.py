import requests
MAKE_WEBHOOK_URL = "https://hook.eu1.make.com/mvudpjo9r7pdbfaqkydj66wwuc2939jq"
data = {
    'caption': '🚨 VIP EMPTY LEG DEAL 🚨\nTest Route',
    'origin': 'TLV',
    'destination': 'JFK',
    'price': '$10,000',
    'date': '12/12/2026',
    'video_url': 'https://tmpfiles.org/dl/12345/test.mp4'
}
requests.post(MAKE_WEBHOOK_URL, json=data)
print("[+] Dummy link sent to Make.com!")
