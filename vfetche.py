import csv
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import feedparser
import requests
from dateutil import parser as date_parser

try:
    import airportsdata
except ModuleNotFoundError:
    print("הספרייה airportsdata אינה מותקנת.")
    print(
        "הרץ: "
        "python -m pip install airportsdata"
    )
    sys.exit(1)


# ============================================================
# הגדרות
# ============================================================

# החלף בכתובת פיד ה-RSS האישי שלך.
RSS_URL = (
    "https://api.villiers.ai/feeds/empty-legs?id=ADHUHR"
)

REQUEST_TIMEOUT = 30

OUTPUT_DIRECTORY = Path("exports")
DATA_DIRECTORY = Path("data")

STATE_FILE = DATA_DIRECTORY / "villiers_state.json"

# בפיד הסימן $ אינו מגיע עם קוד מטבע.
# ברירת המחדל כאן היא USD.
DEFAULT_DOLLAR_CURRENCY = "USD"

RUN_TIME = datetime.now(
    timezone.utc
).replace(
    microsecond=0
)

FETCHED_AT = RUN_TIME.isoformat()

FILE_TIMESTAMP = RUN_TIME.strftime(
    "%Y-%m-%d_%H-%M-%S"
)

CURRENT_OUTPUT_FILE = OUTPUT_DIRECTORY / (
    f"villiers_empty_legs_current_"
    f"{FILE_TIMESTAMP}.csv"
)

ALL_OUTPUT_FILE = OUTPUT_DIRECTORY / (
    f"villiers_empty_legs_all_"
    f"{FILE_TIMESTAMP}.csv"
)

CHANGES_OUTPUT_FILE = OUTPUT_DIRECTORY / (
    f"villiers_empty_legs_changes_"
    f"{FILE_TIMESTAMP}.csv"
)


# ============================================================
# עמודות CSV
# ============================================================

CSV_FIELDS = [
    "source_id",
    "status",
    "change_type",
    "first_seen_at",
    "last_seen_at",
    "inactive_since",

    "title",
    "description",

    "aircraft_type",

    "origin_airport_raw",
    "origin_icao",
    "origin_iata",
    "origin_airport_name",
    "origin_city",
    "origin_country",

    "destination_airport_raw",
    "destination_icao",
    "destination_iata",
    "destination_airport_name",
    "destination_city",
    "destination_country",

    "departure_date_raw",
    "departure_date_iso",
    "departure_time",
    "arrival_time",
    "flight_duration",

    "price_raw",
    "price_amount",
    "price_currency",
    "price_currency_symbol",

    "seats_available",

    "tracking_link",
    "rss_link",
    "booking_link",

    "published",
    "fetched_at",
]


# השדות שמשפיעים על זיהוי עדכון בטיסה.
FINGERPRINT_FIELDS = [
    "title",
    "description",
    "aircraft_type",

    "origin_airport_raw",
    "origin_icao",
    "origin_iata",

    "destination_airport_raw",
    "destination_icao",
    "destination_iata",

    "departure_date_raw",
    "departure_date_iso",
    "departure_time",
    "arrival_time",
    "flight_duration",

    "price_raw",
    "price_amount",
    "price_currency",

    "seats_available",
    "tracking_link",
    "rss_link",
]


# ============================================================
# פונקציות טקסט
# ============================================================

def clean_value(value):
    """
    ממיר ערך לטקסט נקי.
    """

    if value is None:
        return ""

    return str(value).strip()


def clean_database_value(value):
    """
    מנקה ערכים ממאגר שדות התעופה.
    """

    cleaned = clean_value(value)

    if cleaned.casefold() in {
        "",
        "none",
        "null",
        "\\n",
    }:
        return ""

    return cleaned


# ============================================================
# טיפול בשדות תעופה
# ============================================================

def extract_icao_code(airport_text):
    """
    מחלץ קוד ICAO מתוך טקסט לדוגמה:

    KVGT - North Las Vegas Airport
    """

    airport_text = clean_value(
        airport_text
    ).upper()

    if not airport_text:
        return ""

    match = re.match(
        r"^\s*([A-Z0-9]{4})(?:\s|–|—|-|$)",
        airport_text,
    )

    if not match:
        return ""

    return match.group(1)


def extract_feed_airport_name(airport_text):
    """
    מחלץ את שם שדה התעופה מתוך הערך של VILLIERS.
    """

    airport_text = clean_value(airport_text)

    if not airport_text:
        return ""

    parts = re.split(
        r"\s+(?:-|–|—)\s+",
        airport_text,
        maxsplit=1,
    )

    if len(parts) == 2:
        return parts[1].strip()

    return ""


def get_airport_details(
    airport_text,
    airport_database,
):
    """
    ממיר את נתוני שדה התעופה למבנה מסודר.
    """

    raw_value = clean_value(airport_text)
    icao_code = extract_icao_code(raw_value)

    feed_airport_name = (
        extract_feed_airport_name(raw_value)
    )

    result = {
        "raw": raw_value,
        "icao": icao_code,
        "iata": "",
        "name": feed_airport_name,
        "city": "",
        "country": "",
    }

    if not icao_code:
        return result

    airport = airport_database.get(
        icao_code
    )

    if not airport:
        return result

    iata = clean_database_value(
        airport.get("iata")
    )

    database_name = clean_database_value(
        airport.get("name")
    )

    city = clean_database_value(
        airport.get("city")
    )

    country = clean_database_value(
        airport.get("country")
    )

    result["iata"] = iata
    result["city"] = city
    result["country"] = country

    if database_name:
        result["name"] = database_name

    return result


# ============================================================
# טיפול בתאריך
# ============================================================

def normalize_date(date_text):
    """
    ממיר תאריך מהפיד לפורמט YYYY-MM-DD.

    אם לא ניתן לפענח את התאריך,
    מוחזרת מחרוזת ריקה.
    """

    raw_date = clean_value(date_text)

    if not raw_date:
        return ""

    try:
        parsed_date = date_parser.parse(
            raw_date,
            fuzzy=True,
        )

        return parsed_date.date().isoformat()

    except (ValueError, TypeError, OverflowError):
        return ""


# ============================================================
# טיפול במחיר ובמטבע
# ============================================================

CURRENCY_SYMBOLS = {
    "£": "GBP",
    "€": "EUR",
    "$": DEFAULT_DOLLAR_CURRENCY,
    "₪": "ILS",
    "¥": "JPY",
}

CURRENCY_CODES = [
    "USD",
    "GBP",
    "EUR",
    "ILS",
    "AED",
    "CAD",
    "AUD",
    "NZD",
    "CHF",
    "JPY",
    "SGD",
    "HKD",
]


def detect_currency(price_text):
    """
    מזהה קוד מטבע וסמל מטבע.
    """

    price_text = clean_value(price_text)
    upper_price = price_text.upper()

    for currency_code in CURRENCY_CODES:
        if currency_code in upper_price:
            return currency_code, ""

    for symbol, currency_code in (
        CURRENCY_SYMBOLS.items()
    ):
        if symbol in price_text:
            return currency_code, symbol

    return "", ""


def normalize_number_string(number_text):
    """
    מנרמל מספר שעשוי להכיל פסיקים או נקודות.

    דוגמאות:
    6,396 -> 6396
    12,500.50 -> 12500.50
    12.500,50 -> 12500.50
    """

    number_text = clean_value(
        number_text
    )

    number_text = re.sub(
        r"[^\d,.\-]",
        "",
        number_text,
    )

    if not number_text:
        return ""

    has_comma = "," in number_text
    has_dot = "." in number_text

    if has_comma and has_dot:
        last_comma = number_text.rfind(",")
        last_dot = number_text.rfind(".")

        if last_dot > last_comma:
            # דוגמה: 12,500.50
            number_text = number_text.replace(
                ",",
                "",
            )
        else:
            # דוגמה: 12.500,50
            number_text = number_text.replace(
                ".",
                "",
            )
            number_text = number_text.replace(
                ",",
                ".",
            )

    elif has_comma:
        parts = number_text.split(",")

        if (
            len(parts) > 1
            and all(
                len(part) == 3
                for part in parts[1:]
            )
        ):
            number_text = "".join(parts)
        else:
            number_text = number_text.replace(
                ",",
                ".",
            )

    elif has_dot:
        parts = number_text.split(".")

        if (
            len(parts) > 1
            and all(
                len(part) == 3
                for part in parts[1:]
            )
        ):
            number_text = "".join(parts)

    return number_text


def parse_price(price_text):
    """
    מפריד מחיר גולמי, סכום, מטבע וסמל.
    """

    price_raw = clean_value(price_text)

    if not price_raw:
        return {
            "raw": "",
            "amount": "",
            "currency": "",
            "symbol": "",
        }

    currency, symbol = detect_currency(
        price_raw
    )

    amount = normalize_number_string(
        price_raw
    )

    return {
        "raw": price_raw,
        "amount": amount,
        "currency": currency,
        "symbol": symbol,
    }


# ============================================================
# מזהה ופענוח פריטי RSS
# ============================================================

def create_fallback_id(entry):
    """
    יוצר מזהה חלופי אם אין id בפיד.
    """

    identity_parts = [
        clean_value(
            entry.get(
                "villiers_originairport"
            )
        ),
        clean_value(
            entry.get(
                "villiers_destinationairport"
            )
        ),
        clean_value(
            entry.get(
                "villiers_departuredate"
            )
        ),
        clean_value(
            entry.get(
                "villiers_departuretime"
            )
        ),
        clean_value(
            entry.get(
                "villiers_aircrafttype"
            )
        ),
    ]

    identity_text = "|".join(
        identity_parts
    )

    return hashlib.sha256(
        identity_text.encode("utf-8")
    ).hexdigest()


def get_source_id(entry):
    """
    מחזיר מזהה ייחודי של הטיסה.
    """

    source_id = clean_value(
        entry.get("id")
        or entry.get("guid")
    )

    if source_id:
        return source_id

    return create_fallback_id(entry)


def get_description(entry):
    """
    קורא תיאור אם הוא קיים בפיד.
    """

    return clean_value(
        entry.get("summary")
        or entry.get("description")
    )


def convert_entry_to_row(
    entry,
    airport_database,
):
    """
    ממיר פריט RSS לשורה מסודרת.
    """

    origin = get_airport_details(
        entry.get(
            "villiers_originairport"
        ),
        airport_database,
    )

    destination = get_airport_details(
        entry.get(
            "villiers_destinationairport"
        ),
        airport_database,
    )

    price = parse_price(
        entry.get("villiers_price")
    )

    departure_date_raw = clean_value(
        entry.get(
            "villiers_departuredate"
        )
    )

    tracking_link = clean_value(
        entry.get(
            "villiers_trackinglink"
        )
    )

    rss_link = clean_value(
        entry.get("link")
    )

    # תמיד מעדיפים קישור אפיליאייט.
    booking_link = (
        tracking_link or rss_link
    )

    return {
        "source_id": get_source_id(entry),

        "status": "active",
        "change_type": "",

        "first_seen_at": "",
        "last_seen_at": FETCHED_AT,
        "inactive_since": "",

        "title": clean_value(
            entry.get("title")
        ),

        "description": get_description(
            entry
        ),

        "aircraft_type": clean_value(
            entry.get(
                "villiers_aircrafttype"
            )
        ),

        "origin_airport_raw": origin["raw"],
        "origin_icao": origin["icao"],
        "origin_iata": origin["iata"],
        "origin_airport_name": origin["name"],
        "origin_city": origin["city"],
        "origin_country": origin["country"],

        "destination_airport_raw": (
            destination["raw"]
        ),
        "destination_icao": (
            destination["icao"]
        ),
        "destination_iata": (
            destination["iata"]
        ),
        "destination_airport_name": (
            destination["name"]
        ),
        "destination_city": (
            destination["city"]
        ),
        "destination_country": (
            destination["country"]
        ),

        "departure_date_raw": (
            departure_date_raw
        ),
        "departure_date_iso": normalize_date(
            departure_date_raw
        ),
        "departure_time": clean_value(
            entry.get(
                "villiers_departuretime"
            )
        ),
        "arrival_time": clean_value(
            entry.get(
                "villiers_arrivaltime"
            )
        ),
        "flight_duration": clean_value(
            entry.get(
                "villiers_flightduration"
            )
        ),

        "price_raw": price["raw"],
        "price_amount": price["amount"],
        "price_currency": price["currency"],
        "price_currency_symbol": (
            price["symbol"]
        ),

        "seats_available": clean_value(
            entry.get(
                "villiers_seatsavailable"
            )
        ),

        "tracking_link": tracking_link,
        "rss_link": rss_link,
        "booking_link": booking_link,

        "published": clean_value(
            entry.get("published")
        ),

        "fetched_at": FETCHED_AT,
    }


# ============================================================
# זיהוי שינויים
# ============================================================

def create_fingerprint(row):
    """
    יוצר חתימה של נתוני הטיסה.

    שינוי במחיר, מועד, מושבים או מסלול
    ייצור חתימה שונה.
    """

    fingerprint_data = {
        field_name: row.get(
            field_name,
            "",
        )
        for field_name in FINGERPRINT_FIELDS
    }

    fingerprint_json = json.dumps(
        fingerprint_data,
        ensure_ascii=False,
        sort_keys=True,
    )

    return hashlib.sha256(
        fingerprint_json.encode("utf-8")
    ).hexdigest()


def load_state():
    """
    טוען את מצב הטיסות מההרצה הקודמת.
    """

    if not STATE_FILE.exists():
        return {}

    try:
        state_data = json.loads(
            STATE_FILE.read_text(
                encoding="utf-8"
            )
        )

        return state_data.get(
            "flights",
            {},
        )

    except (
        json.JSONDecodeError,
        OSError,
    ) as error:
        print(
            "אזהרה: לא ניתן לקרוא "
            "את קובץ המצב."
        )
        print(error)
        return {}


def save_state(flights):
    """
    שומר את מצב הטיסות בצורה אטומית.
    """

    DATA_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    state_data = {
        "updated_at": FETCHED_AT,
        "flights": flights,
    }

    temporary_file = STATE_FILE.with_suffix(
        ".tmp"
    )

    temporary_file.write_text(
        json.dumps(
            state_data,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    temporary_file.replace(
        STATE_FILE
    )


def process_entries(
    entries,
    airport_database,
    old_state,
):
    """
    משווה בין הפיד הנוכחי למצב הקודם.
    """

    current_rows = []
    change_rows = []
    new_state = {}
    seen_ids = set()

    counters = {
        "new": 0,
        "updated": 0,
        "reactivated": 0,
        "unchanged": 0,
        "removed": 0,
    }

    for entry in entries:
        row = convert_entry_to_row(
            entry,
            airport_database,
        )

        source_id = row["source_id"]
        seen_ids.add(source_id)

        fingerprint = create_fingerprint(
            row
        )

        previous_item = old_state.get(
            source_id
        )

        if previous_item is None:
            row["change_type"] = "new"
            row["first_seen_at"] = FETCHED_AT
            counters["new"] += 1

        else:
            previous_row = previous_item.get(
                "row",
                {},
            )

            previous_status = previous_row.get(
                "status"
            )

            previous_fingerprint = (
                previous_item.get(
                    "fingerprint"
                )
            )

            row["first_seen_at"] = (
                previous_row.get(
                    "first_seen_at"
                )
                or FETCHED_AT
            )

            if previous_status == "inactive":
                row["change_type"] = (
                    "reactivated"
                )
                counters["reactivated"] += 1

            elif (
                previous_fingerprint
                != fingerprint
            ):
                row["change_type"] = "updated"
                counters["updated"] += 1

            else:
                row["change_type"] = (
                    "unchanged"
                )
                counters["unchanged"] += 1

        row["status"] = "active"
        row["last_seen_at"] = FETCHED_AT
        row["inactive_since"] = ""
        row["fetched_at"] = FETCHED_AT

        current_rows.append(row)

        if row["change_type"] in {
            "new",
            "updated",
            "reactivated",
        }:
            change_rows.append(row.copy())

        new_state[source_id] = {
            "fingerprint": fingerprint,
            "row": row.copy(),
        }

    # טיסות שהיו בעבר אך נעלמו מהפיד.
    for source_id, previous_item in (
        old_state.items()
    ):
        if source_id in seen_ids:
            continue

        previous_row = previous_item.get(
            "row",
            {},
        ).copy()

        if not previous_row:
            continue

        previous_status = previous_row.get(
            "status"
        )

        if previous_status == "active":
            previous_row["status"] = "inactive"
            previous_row["change_type"] = "removed"
            previous_row["inactive_since"] = (
                FETCHED_AT
            )
            previous_row["fetched_at"] = (
                FETCHED_AT
            )

            counters["removed"] += 1
            change_rows.append(
                previous_row.copy()
            )

        else:
            previous_row["status"] = "inactive"
            previous_row["change_type"] = (
                "inactive"
            )

        new_state[source_id] = {
            "fingerprint": previous_item.get(
                "fingerprint",
                "",
            ),
            "row": previous_row,
        }

    all_rows = [
        item["row"]
        for item in new_state.values()
    ]

    return (
        current_rows,
        all_rows,
        change_rows,
        new_state,
        counters,
    )


# ============================================================
# שמירה ל-CSV
# ============================================================

def sort_rows(rows):
    """
    ממיין לפי תאריך ושעת יציאה.
    """

    return sorted(
        rows,
        key=lambda row: (
            row.get(
                "departure_date_iso",
                "9999-12-31",
            )
            or "9999-12-31",
            row.get(
                "departure_time",
                "99:99",
            )
            or "99:99",
            row.get(
                "source_id",
                "",
            ),
        ),
    )


def save_csv(file_path, rows):
    """
    שומר רשימת שורות בקובץ CSV.
    """

    file_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    rows = sort_rows(rows)

    with file_path.open(
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=CSV_FIELDS,
            extrasaction="ignore",
        )

        writer.writeheader()
        writer.writerows(rows)


# ============================================================
# RSS
# ============================================================

def download_rss():
    """
    מוריד את פיד ה-RSS.
    """

    response = requests.get(
        RSS_URL,
        headers={
            "User-Agent": (
                "VilliersEmptyLegReader/3.0"
            ),
            "Accept": (
                "application/rss+xml, "
                "application/atom+xml, "
                "application/xml, "
                "text/xml"
            ),
        },
        timeout=REQUEST_TIMEOUT,
    )

    response.raise_for_status()

    return response.content


def parse_rss(rss_content):
    """
    מפענח את תוכן ה-RSS.
    """

    feed = feedparser.parse(
        rss_content
    )

    if feed.bozo:
        print(
            "אזהרה בזמן קריאת הפיד:",
            feed.bozo_exception,
        )

    if not feed.entries:
        raise RuntimeError(
            "לא נמצאו טיסות בפיד."
        )

    return feed


def validate_feed(feed):
    """
    בודק שזהו פיד Empty Legs.
    """

    feed_title = clean_value(
        feed.feed.get("title")
    )

    if "empty leg" in feed_title.casefold():
        print(
            "הפיד זוהה כפיד Empty Legs."
        )
    else:
        print(
            "אזהרה: שם הפיד אינו מציין "
            "Empty Legs."
        )

    return feed_title


# ============================================================
# הדפסת סיכום
# ============================================================

def print_sample(rows):
    """
    מדפיס טיסה ראשונה לדוגמה.
    """

    if not rows:
        return

    sample = sort_rows(rows)[0]

    print()
    print("טיסה ראשונה לדוגמה:")

    print(
        f"מוצא: "
        f"{sample['origin_icao']} / "
        f"{sample['origin_iata'] or 'ללא IATA'} "
        f"- {sample['origin_airport_name']}"
    )

    print(
        f"יעד: "
        f"{sample['destination_icao']} / "
        f"{sample['destination_iata'] or 'ללא IATA'} "
        f"- {sample['destination_airport_name']}"
    )

    print(
        f"תאריך מקורי: "
        f"{sample['departure_date_raw']}"
    )

    print(
        f"תאריך ISO: "
        f"{sample['departure_date_iso']}"
    )

    print(
        f"שעת יציאה: "
        f"{sample['departure_time']}"
    )

    print(
        f"מחיר: "
        f"{sample['price_raw']}"
    )

    print(
        f"מחיר מנורמל: "
        f"{sample['price_amount']} "
        f"{sample['price_currency']}"
    )

    print(
        f"מטוס: "
        f"{sample['aircraft_type']}"
    )

    print(
        f"מושבים: "
        f"{sample['seats_available']}"
    )

    print(
        f"סטטוס שינוי: "
        f"{sample['change_type']}"
    )


def print_summary(
    feed_title,
    current_rows,
    all_rows,
    change_rows,
    counters,
):
    """
    מדפיס סיכום הפעלה.
    """

    print()
    print(f"שם הפיד: {feed_title}")

    print(
        f"טיסות פעילות בפיד: "
        f"{len(current_rows)}"
    )

    print(
        f"כל הטיסות שנשמרו בהיסטוריה: "
        f"{len(all_rows)}"
    )

    print(
        f"שינויים בהרצה הנוכחית: "
        f"{len(change_rows)}"
    )

    print()
    print("פירוט שינויים:")

    print(
        f"  חדשות: {counters['new']}"
    )

    print(
        f"  עודכנו: {counters['updated']}"
    )

    print(
        "  חזרו לפיד: "
        f"{counters['reactivated']}"
    )

    print(
        f"  ללא שינוי: "
        f"{counters['unchanged']}"
    )

    print(
        f"  נעלמו מהפיד: "
        f"{counters['removed']}"
    )

    print()
    print("קבצים שנוצרו:")

    print(
        f"  טיסות פעילות: "
        f"{CURRENT_OUTPUT_FILE.resolve()}"
    )

    print(
        f"  כל ההיסטוריה: "
        f"{ALL_OUTPUT_FILE.resolve()}"
    )

    print(
        f"  שינויים בלבד: "
        f"{CHANGES_OUTPUT_FILE.resolve()}"
    )

    print(
        f"  קובץ מצב: "
        f"{STATE_FILE.resolve()}"
    )


# ============================================================
# הפעלה
# ============================================================

def main():
    print(
        "טוען את מאגר שדות התעופה..."
    )

    airport_database = airportsdata.load(
        "ICAO"
    )

    print(
        f"נטענו {len(airport_database)} "
        "שדות תעופה."
    )

    print()
    print("מוריד את נתוני ה-RSS...")

    rss_content = download_rss()
    feed = parse_rss(rss_content)
    feed_title = validate_feed(feed)

    entries = list(feed.entries)

    print(
        f"נמצאו {len(entries)} "
        "פריטים בפיד."
    )

    old_state = load_state()

    (
        current_rows,
        all_rows,
        change_rows,
        new_state,
        counters,
    ) = process_entries(
        entries,
        airport_database,
        old_state,
    )

    save_csv(
        CURRENT_OUTPUT_FILE,
        current_rows,
    )

    save_csv(
        ALL_OUTPUT_FILE,
        all_rows,
    )

    save_csv(
        CHANGES_OUTPUT_FILE,
        change_rows,
    )

    save_state(new_state)

    print_sample(current_rows)

    print_summary(
        feed_title,
        current_rows,
        all_rows,
        change_rows,
        counters,
    )


if __name__ == "__main__":
    try:
        main()

    except requests.Timeout:
        print(
            "שגיאה: הבקשה ל-RSS חרגה "
            "מזמן ההמתנה."
        )

    except requests.RequestException as error:
        print(
            f"שגיאה בהורדת ה-RSS: {error}"
        )

    except PermissionError as error:
        print(
            "שגיאה: אין הרשאה לכתוב קובץ."
        )
        print(
            "בדוק שהקובץ אינו פתוח ב-Excel."
        )
        print(error)

    except Exception as error:
        print(f"שגיאה: {error}")
