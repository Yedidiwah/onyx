#!/bin/bash
cd /root/onyx
source venv/bin/activate

# 1. Update site and flights data
python scripts/update_site.py --rss

# 2. Send Telegram alerts
python vtelegram.py

# 3. Push updates back to GitHub
git add .
git commit -m "Auto-update flights data and telegram alerts from server"
git push origin main
