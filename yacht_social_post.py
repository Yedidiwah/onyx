"""
Posts the current best yacht discount to the same Make.com webhook
cp.py already uses for jet deals - reuses the existing Facebook
automation instead of building a new one.

Turns the boat's listing photo into a short vertical video (Ken Burns
zoom + burned-in text) instead of posting a static image. A static
photo post got 5 views while the same day's video flight post got
203 - almost certainly because Reels/video gets algorithmic
distribution that plain photo posts don't. The "Follow" CTA is now
burned into the video itself instead of living only in the caption,
since watch-time data on the flights post showed most viewers bail
within 3-5 seconds and never read the caption at all.

Usage:
    python yacht_social_post.py                 # posts the current #1 discount
    python yacht_social_post.py --dry-run        # renders the video locally, does not post
"""
import json
import os
import subprocess
import sys
import tempfile

import requests
from dotenv import load_dotenv

load_dotenv()

MAKE_WEBHOOK_URL = os.getenv("MAKE_WEBHOOK_URL_YACHT")
TELEGRAM_CREAT_BOT_TOKEN = os.getenv("TELEGRAM_CREAT_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
YACHTS_JSON = "data/yachts.json"

FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
]


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
💰 {deal['original_price']} ➡️ {deal['total_price']} (-{deal['discount_pct']:.0f}%)

👉 Follow for a new yacht deal every day
🔗 Book this charter: {deal['booking_link']}

📍 {deal['from_location']}
🗓️ {deal['date_from']}

#YachtCharter #EmptyLeg #LuxuryTravel"""


def _find_font():
    for path in FONT_CANDIDATES:
        if os.path.exists(path):
            return path
    return None


def _escape_drawtext(text):
    return (
        str(text)
        .replace("\\", "\\\\")
        .replace(":", "\\:")
        .replace("'", "’")
        .replace("%", "\\%")
    )


def download_image(url, dest_path):
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    with open(dest_path, "wb") as f:
        f.write(response.content)


def make_video_from_image(image_path, out_path, title, subtitle, duration=8):
    font = _find_font()
    filters = [
        "scale=1080:1920:force_original_aspect_ratio=increase",
        "crop=1080:1920",
        f"zoompan=z='min(zoom+0.0012,1.15)':d={duration * 25}:s=1080x1920:fps=25",
    ]
    if font:
        title_txt = _escape_drawtext(title)
        subtitle_txt = _escape_drawtext(subtitle)
        filters.append(
            f"drawtext=fontfile={font}:text='{title_txt}':fontsize=64:"
            "fontcolor=white:borderw=4:bordercolor=black:x=(w-text_w)/2:y=140"
        )
        filters.append(
            f"drawtext=fontfile={font}:text='{subtitle_txt}':fontsize=46:"
            "fontcolor=white:borderw=3:bordercolor=black:x=(w-text_w)/2:y=240"
        )
        filters.append(
            f"drawtext=fontfile={font}:text='Follow ⮑ for a new deal every day':"
            "fontsize=40:fontcolor=white:borderw=3:bordercolor=black:"
            "x=(w-text_w)/2:y=h-160"
        )
    else:
        print("[!] No usable font found on this system - rendering video without text overlay.")

    cmd = [
        "ffmpeg", "-y", "-loop", "1", "-i", image_path,
        "-vf", ",".join(filters),
        "-t", str(duration), "-pix_fmt", "yuv420p", "-r", "25",
        out_path,
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        print("[!] ffmpeg failed:")
        print(e.stderr)
        raise


def upload_to_telegram_and_get_url(video_path, caption):
    if not TELEGRAM_CREAT_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("[!] Telegram credentials missing.")
        return None
    url = f"https://api.telegram.org/bot{TELEGRAM_CREAT_BOT_TOKEN}/sendVideo"
    with open(video_path, "rb") as f:
        res = requests.post(
            url,
            data={"chat_id": TELEGRAM_CHAT_ID, "caption": caption},
            files={"video": f},
        ).json()
    if not res.get("ok"):
        print(f"[!] Telegram upload failed: {res}")
        return None
    file_id = res["result"]["video"]["file_id"]
    file_res = requests.get(
        f"https://api.telegram.org/bot{TELEGRAM_CREAT_BOT_TOKEN}/getFile?file_id={file_id}"
    ).json()
    if not file_res.get("ok"):
        print(f"[!] Telegram getFile failed: {file_res}")
        return None
    return f"https://api.telegram.org/file/bot{TELEGRAM_CREAT_BOT_TOKEN}/{file_res['result']['file_path']}"


def send_to_make_webhook(deal, caption, video_url):
    data = {
        "caption": caption,
        "origin": deal.get("from_location", "TBD"),
        "price": deal.get("total_price", "TBD"),
        "date": deal.get("date_from", "TBD"),
        "video_url": video_url,
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
    title = deal["model"]
    subtitle = f"{deal['original_price']} -> {deal['total_price']} (-{deal['discount_pct']:.0f}%)"

    with tempfile.TemporaryDirectory() as tmp:
        image_path = os.path.join(tmp, "boat.jpg")
        video_path = os.path.join(tmp, "yacht_deal.mp4")

        print("[*] Downloading boat photo...")
        download_image(deal["image_url"], image_path)

        print("[*] Rendering video (Ken Burns zoom + text overlay)...")
        make_video_from_image(image_path, video_path, title, subtitle)

        if "--dry-run" in sys.argv:
            local_copy = "yacht_deal_preview.mp4"
            os.replace(video_path, local_copy)
            print(f"[+] Rendered preview saved to {local_copy} - inspect it, nothing was posted.")
            print(json.dumps({"caption": caption, **{k: deal.get(k) for k in ("from_location", "total_price", "date_from", "image_url")}}, indent=2, ensure_ascii=False))
            sys.exit(0)

        print("[*] Uploading video to Telegram to get a CDN URL...")
        video_url = upload_to_telegram_and_get_url(video_path, caption)
        if not video_url:
            print("[!] Could not get a video URL - aborting post.")
            sys.exit(1)

        print(f"[*] Posting top deal: {deal['model']} • {deal['name']} (-{deal['discount_pct']:.0f}%)")
        send_to_make_webhook(deal, caption, video_url)
        print("[+] Sent to Make.com webhook.")
