#!/bin/bash
cd /root/onyx
source venv/bin/activate

# 1. Fetch new flights
python scripts/update_site.py --rss

# 2. Send Telegram alerts
python telegram/vtelegram.py

# 3. Push updates back to GitHub
git add .
git commit -m "Auto-update flights data from server"
git push origin main
