"""
Pulls live yacht/boat charter listings from SkipperCity's Booking Manager
search widget (the same one embedded at skippercity.com/online-boat-search/)
and sorts them by discount percentage.

Not an official/documented API - this replays the same POST request the
public search page itself makes. Keep request frequency low (e.g. a
few times a day) and this is the same data any site visitor can already see.

Usage:
    pip install requests beautifulsoup4

    python skippercity_deals.py                      # best deals starting anytime in the next 30 days
    python skippercity_deals.py 12.09.2026 19.09.2026 # one specific charter week
"""
import json
import re
import sys
from datetime import date, datetime, timedelta, timezone

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.booking-manager.com/wbm2/page.html"
COMPANY_ID = "4630"  # SkipperCity's account on Booking Manager

# Deep links into booking-manager.com don't reliably carry SkipperCity's
# ?ref= affiliate attribution (verified: the widget's affiliateId stays
# empty even when ?ref is set on the embedding skippercity.com page), so
# every listing points back to the one link SkipperCity's own affiliate
# programme documents as tracked.
BOOKING_LINK = "https://skippercity.com/online-boat-search/?ref=onyx"

SORT_BY_DISCOUNT = "11"
SORT_DESCENDING = "-1"

DEFAULT_PAYLOAD = {
    "setlang": "en",
    "affiliateId": "",
    "filter_berths": "0-2000",
    "daterangepicker_end": "",
    "placeholderId": "",
    "postmethod": "GET",
    "flags": "1",
    "filter_heads": "0-2000",
    "filter_cabins": "0-2000",
    "filter_length_ft": "0-2000",
    "filter_offer_type": "",
    "companyid": COMPANY_ID,
    "filter_price": "0-1000000",
    "personsByGroup2": "0",
    "personsByGroup1": "0",
    "daterangepicker_start": "",
    "personsByGroup0": "2",
    "filter_service_type": "",
    "filter_yachtage": "",
    "filterlocationdistance": "",
    "filter_flexibility": "on_day",
    "filter_kind": "",
    "filter_country": "",
    "filter_region": "",
    "filter_base": "",
    "target": "_self",
    "action": "redisplay",
    "view": "SearchResult",
}


def fetch_page(date_from: str, date_to: str, results_per_page: int = 100, page: int = 1) -> str:
    """date_from / date_to format: DD.MM.YYYY"""
    payload = dict(DEFAULT_PAYLOAD)
    payload.update({
        "daterange": f"{date_from} - {date_to}",
        "resultsPerPage": str(results_per_page),
        "resultsPage": str(page),
        "sortBy": SORT_BY_DISCOUNT,
        "sortDirection": SORT_DESCENDING,
    })
    resp = requests.post(BASE_URL, data=payload, timeout=30,
                          headers={"User-Agent": "Mozilla/5.0"})
    resp.raise_for_status()
    resp.encoding = "utf-8"  # server omits charset; body is UTF-8 (e.g. the € sign) but requests guesses Latin-1
    return resp.text


def _field(card, label):
    th = card.find("th", string=lambda s: s and s.strip() == label)
    if not th:
        return None
    td = th.find_next("td")
    return td.get_text(" ", strip=True) if td else None


def total_results(html: str) -> int:
    text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
    m = re.search(r"([\d,]+)\s+available yachts found", text)
    return int(m.group(1).replace(",", "")) if m else 0


def _price_amount(price_text):
    """'1,250.00 €' -> 1250.0"""
    if not price_text:
        return None
    digits = re.sub(r"[^\d.]", "", price_text.replace(",", ""))
    return float(digits) if digits else None


def parse_deals(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    deals = []
    for card in soup.select("div.boat-card"):
        h2 = card.find("h2")
        if not h2:
            continue
        model, _, name = h2.get_text(" ", strip=True).partition("•")

        discount_text = _field(card, "Discount:")
        discount_pct = float(re.sub(r"[^\d.]", "", discount_text)) if discount_text else 0.0

        from_location = _field(card, "From:")
        to_location = _field(card, "to:")  # only present for one-way (river/canal) routes
        country = from_location.rsplit(",", 1)[-1].strip() if from_location and "," in from_location else None

        total_price = _field(card, "Total price:")

        deals.append({
            "model": model.strip(),
            "name": name.strip(),
            "type": _field(card, "Type:"),
            "service": _field(card, "Service:"),
            "year": _field(card, "Year:"),
            "length": _field(card, "Length:"),
            "berths": _field(card, "Berths:"),
            "cabins": _field(card, "Cabins:"),
            "date_from": _field(card, "Date:"),
            "from_location": from_location,
            "to_location": to_location if to_location and to_location != from_location else None,
            "country": country,
            "original_price": _field(card, "Price:"),
            "discount_pct": discount_pct,
            "total_price": total_price,
            "total_price_amount": _price_amount(total_price),
            "currency": "EUR",
            "booking_link": BOOKING_LINK,
        })
    return deals


def dedupe_best_per_boat(deals: list[dict]) -> list[dict]:
    """Keep only the best-discount occurrence of each boat (it can appear
    in several of the swept weekly windows with slightly different rates)."""
    best = {}
    for d in deals:
        key = (d["model"], d["name"], d["from_location"])
        if key not in best or d["discount_pct"] > best[key]["discount_pct"]:
            best[key] = d
    return list(best.values())


def deals_for_window(date_from: str, date_to: str) -> list[dict]:
    html = fetch_page(date_from, date_to, results_per_page=100, page=1)
    print(f"[i] {total_results(html)} yachts available for {date_from} - {date_to}", file=sys.stderr)
    return parse_deals(html)


def default_windows(horizon_days: int = 30, window_days: int = 7) -> list[tuple[str, str]]:
    """Charters are booked by the week, so a 30-day 'anytime soon' search is
    split into consecutive week-long windows starting today, rather than one
    30-day-long charter query (which would only match boats free the whole month)."""
    today = date.today()
    windows = []
    start = today
    while start < today + timedelta(days=horizon_days):
        end = start + timedelta(days=window_days)
        windows.append((start.strftime("%d.%m.%Y"), end.strftime("%d.%m.%Y")))
        start = end
    return windows


def find_best_discounts(top_n: int = 50, horizon_days: int = 30) -> list[dict]:
    """Best discounts starting anytime in the next `horizon_days` days,
    one entry per boat."""
    all_deals = []
    for date_from, date_to in default_windows(horizon_days):
        all_deals.extend(deals_for_window(date_from, date_to))
    deduped = dedupe_best_per_boat(all_deals)
    deduped.sort(key=lambda d: d["discount_pct"], reverse=True)
    return deduped[:top_n]


def build_feed(deals: list[dict]) -> dict:
    """Mirrors the shape of data/flights.json so the website can render
    both feeds the same way."""
    return {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "source": "SkipperCity Online Boat Search",
        "provider": "SkipperCity",
        "publisher": "ONYX Radar",
        "yacht_count": len(deals),
        "affiliate_disclosure": (
            "ONYX Radar is an independent affiliate participating in the "
            "SkipperCity affiliate programme and may receive a commission "
            "from qualifying bookings."
        ),
        "data_notice": (
            "Yacht details, availability and listed prices are sourced from "
            "SkipperCity's public search tool and may change without notice."
        ),
        "yachts": deals,
    }


if __name__ == "__main__":
    json_out = None
    args = sys.argv[1:]
    if "--json" in args:
        idx = args.index("--json")
        json_out = args[idx + 1]
        del args[idx:idx + 2]

    if len(args) == 0:
        results = find_best_discounts()
    elif len(args) == 2:
        results = dedupe_best_per_boat(deals_for_window(args[0], args[1]))
        results.sort(key=lambda d: d["discount_pct"], reverse=True)
        results = results[:50]
    else:
        print("Usage: python skippercity_deals.py [DD.MM.YYYY DD.MM.YYYY] [--json path/to/yachts.json]")
        sys.exit(1)

    if json_out:
        with open(json_out, "w", encoding="utf-8") as f:
            json.dump(build_feed(results), f, ensure_ascii=False, indent=2)
        print(f"[i] wrote {len(results)} deals to {json_out}", file=sys.stderr)
    else:
        for d in results:
            to_part = f" -> {d['to_location']}" if d["to_location"] else ""
            print(
                f"-{d['discount_pct']:.1f}%  {d['model']} • {d['name']}  "
                f"{d['original_price']} -> {d['total_price']}  "
                f"[{d['type']}, {d['berths']} berths]  "
                f"from {d['from_location']}{to_part}"
            )
