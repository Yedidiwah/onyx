"""
Posts the current best yacht discount to the same Make.com webhook
cp.py already uses for jet deals - reuses the existing Facebook
automation instead of building a new one.

Unlike cp.py, there's no rendered video for yachts - this sends the
boat's own listing photo as `image_url` instead of `video_url`.
Your Make.com scenario may need a small tweak to also read that field
if it currently only maps `video_url` to the Facebook post.

Usage:
    python yacht_social_post.py                 # posts the current #1 discount
    python yacht_social_post.py --dry-run        # prints the payload, does not post
"""
import json
import os
import sys

import requests
from dotenv import load_dotenv

load_dotenv()

MAKE_WEBHOOK_URL = os.getenv("MAKE_WEBHOOK_URL_YACHT")
YACHTS_JSON = "data/yachts.json"


def load_top_deal(path=YACHTS_JSON):
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    yachts = payload.get("yachts", [])
    if not yachts:
        return None
    return max(yachts, key=lambda d: d.get("discount_pct", 0))


def build_caption(deal):
    return f"""🚨 VIP YACHT CHARTER DEAL 🚨
🛥️ {deal['model']} • {deal['name']}
📍 {deal['from_location']}
🗓️ {deal['date_from']}
💰 {deal['original_price']} ➡️ {deal['total_price']} (-{deal['discount_pct']:.0f}%)

🔗 Book this charter: https://skippercity.com/online-boat-search/?ref=onyx

#YachtCharter #EmptyLeg #LuxuryTravel"""


def send_to_make_webhook(deal, caption):
    data = {
        "caption": caption,
        "origin": deal.get("from_location", "TBD"),
        "price": deal.get("total_price", "TBD"),
        "date": deal.get("date_from", "TBD"),
        "image_url": deal.get("image_url"),
    }
    response = requests.post(MAKE_WEBHOOK_URL, json=data)
    response.raise_for_status()
    return response


if __name__ == "__main__":
    deal = load_top_deal()
    if not deal:
        print("[!] No yacht deals found in data/yachts.json")
        sys.exit(1)

    caption = build_caption(deal)

    if "--dry-run" in sys.argv:
        print(json.dumps({"caption": caption, **{k: deal.get(k) for k in ("from_location", "total_price", "date_from", "image_url")}}, indent=2, ensure_ascii=False))
        sys.exit(0)

    print(f"[*] Posting top deal: {deal['model']} • {deal['name']} (-{deal['discount_pct']:.0f}%)")
    send_to_make_webhook(deal, caption)
    print("[+] Sent to Make.com webhook.")
