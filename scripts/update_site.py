import argparse
import csv
import glob
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import airportsdata
import feedparser
import requests
from dateutil import parser as date_parser
from dotenv import load_dotenv


# ============================================================
# Paths and configuration
# ============================================================

SCRIPT_DIRECTORY = Path(__file__).resolve().parent
SITE_ROOT = SCRIPT_DIRECTORY.parent

DEFAULT_OUTPUT_FILE = (
    SITE_ROOT
    / "data"
    / "flights.json"
)

DEFAULT_LOCAL_CSV_PATTERN = str(
    SITE_ROOT.parent
    / "exports"
    / "villiers_empty_legs_current_*.csv"
)

# Load a local .env from either the website
# folder or its parent folder.
load_dotenv(
    SITE_ROOT / ".env"
)

load_dotenv(
    SITE_ROOT.parent / ".env"
)

RSS_URL = os.getenv(
    "VILLIERS_RSS_URL",
    "",
).strip()

REQUEST_TIMEOUT = 30

DEFAULT_DOLLAR_CURRENCY = "USD"


# ============================================================
# Public fields
# ============================================================

PUBLIC_FIELDS = [
    "source_id",
    "status",

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


# ============================================================
# Currency configuration
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


# ============================================================
# Generic helpers
# ============================================================

def utc_now():
    """
    Returns the current UTC time.
    """

    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
    )


def clean_value(value):
    """
    Converts a value to clean text.
    """

    if value is None:
        return ""

    return str(value).strip()


def clean_database_value(value):
    """
    Cleans airport database values.
    """

    value = clean_value(value)

    if value.casefold() in {
        "",
        "none",
        "null",
        "\\n",
    }:
        return ""

    return value


def safe_public_url(value):
    """
    Allows only HTTP and HTTPS links.
    """

    value = clean_value(value)

    if not value:
        return ""

    try:
        parsed = urlparse(value)

        if parsed.scheme not in {
            "http",
            "https",
        }:
            return ""

        if not parsed.netloc:
            return ""

        return value

    except ValueError:
        return ""


# ============================================================
# Airport processing
# ============================================================

def extract_icao_code(airport_text):
    """
    Extracts an ICAO code from a Villiers
    airport value.
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


def extract_feed_airport_name(
    airport_text,
):
    """
    Extracts the airport name from:

    KVGT - North Las Vegas Airport
    """

    airport_text = clean_value(
        airport_text
    )

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
    Enriches one airport using its ICAO code.
    """

    raw_value = clean_value(
        airport_text
    )

    icao_code = extract_icao_code(
        raw_value
    )

    feed_name = extract_feed_airport_name(
        raw_value
    )

    result = {
        "raw": raw_value,
        "icao": icao_code,
        "iata": "",
        "name": feed_name,
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

    result["iata"] = clean_database_value(
        airport.get("iata")
    ).upper()

    database_name = clean_database_value(
        airport.get("name")
    )

    if database_name:
        result["name"] = database_name

    result["city"] = clean_database_value(
        airport.get("city")
    )

    result["country"] = (
        clean_database_value(
            airport.get("country")
        ).upper()
    )

    return result


# ============================================================
# Date processing
# ============================================================

def normalize_date(date_text):
    """
    Converts a date to YYYY-MM-DD.
    """

    date_text = clean_value(
        date_text
    )

    if not date_text:
        return ""

    try:
        parsed_date = date_parser.parse(
            date_text,
            fuzzy=True,
        )

        return parsed_date.date().isoformat()

    except (
        ValueError,
        TypeError,
        OverflowError,
    ):
        return ""


# ============================================================
# Price processing
# ============================================================

def detect_currency(price_text):
    """
    Detects currency code and symbol.
    """

    price_text = clean_value(
        price_text
    )

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


def normalize_number_string(
    number_text,
):
    """
    Normalizes common price formats.
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
            # 12,500.50
            number_text = number_text.replace(
                ",",
                "",
            )

        else:
            # 12.500,50
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
    Splits a price into public fields.
    """

    raw_price = clean_value(
        price_text
    )

    if not raw_price:
        return {
            "raw": "",
            "amount": "",
            "currency": "",
            "symbol": "",
        }

    currency, symbol = detect_currency(
        raw_price
    )

    amount = normalize_number_string(
        raw_price
    )

    return {
        "raw": raw_price,
        "amount": amount,
        "currency": currency,
        "symbol": symbol,
    }


# ============================================================
# RSS identifiers
# ============================================================

def create_fallback_id(entry):
    """
    Creates a stable ID if RSS has no ID.
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
    Returns the RSS item ID.
    """

    source_id = clean_value(
        entry.get("id")
        or entry.get("guid")
    )

    if source_id:
        return source_id

    return create_fallback_id(entry)


# ============================================================
# RSS conversion
# ============================================================

def convert_rss_entry(
    entry,
    airport_database,
    fetched_at,
):
    """
    Converts a Villiers RSS item to the
    website JSON schema.
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

    raw_date = clean_value(
        entry.get(
            "villiers_departuredate"
        )
    )

    price = parse_price(
        entry.get(
            "villiers_price"
        )
    )

    tracking_link = safe_public_url(
        entry.get(
            "villiers_trackinglink"
        )
    )

    rss_link = safe_public_url(
        entry.get("link")
    )

    booking_link = (
        tracking_link or rss_link
    )

    return {
        "source_id": get_source_id(entry),
        "status": "active",

        "title": clean_value(
            entry.get("title")
        ),

        "description": clean_value(
            entry.get("summary")
            or entry.get("description")
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

        "departure_date_raw": raw_date,
        "departure_date_iso": normalize_date(
            raw_date
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

        "fetched_at": fetched_at,
    }


# ============================================================
# RSS loading
# ============================================================

def load_from_rss(rss_url):
    """
    Downloads and parses the Villiers RSS.
    """

    if not rss_url:
        raise RuntimeError(
            "VILLIERS_RSS_URL is missing."
        )

    print(
        "Downloading Villiers RSS..."
    )

    response = requests.get(
        rss_url,
        headers={
            "User-Agent": (
                "ONYX-Radar-Website/1.0"
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

    feed = feedparser.parse(
        response.content
    )

    if feed.bozo:
        print(
            "RSS parser warning:",
            feed.bozo_exception,
        )

    if not feed.entries:
        raise RuntimeError(
            "No flights were found in the RSS."
        )

    airport_database = airportsdata.load(
        "ICAO"
    )

    fetched_at = utc_now()

    flights = [
        convert_rss_entry(
            entry,
            airport_database,
            fetched_at,
        )
        for entry in feed.entries
    ]

    feed_title = clean_value(
        feed.feed.get("title")
    )

    return flights, feed_title


# ============================================================
# CSV loading
# ============================================================

def sanitize_csv_row(row):
    """
    Keeps only fields intended for the
    public website.
    """

    public_row = {}

    for field in PUBLIC_FIELDS:
        public_row[field] = clean_value(
            row.get(field)
        )

    public_row["status"] = (
        public_row["status"]
        or "active"
    )

    public_row["tracking_link"] = (
        safe_public_url(
            public_row["tracking_link"]
        )
    )

    public_row["rss_link"] = safe_public_url(
        public_row["rss_link"]
    )

    public_row["booking_link"] = (
        safe_public_url(
            public_row["booking_link"]
        )
        or public_row["tracking_link"]
        or public_row["rss_link"]
    )

    return public_row


def load_from_csv(csv_pattern):
    """
    Loads the newest current flight CSV.
    """

    matching_files = glob.glob(
        csv_pattern
    )

    if not matching_files:
        raise RuntimeError(
            "No current flight CSV was found "
            f"for pattern: {csv_pattern}"
        )

    latest_file = Path(
        max(
            matching_files,
            key=os.path.getmtime,
        )
    )

    print(
        f"Reading local CSV: {latest_file}"
    )

    flights = []

    with latest_file.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as file:
        reader = csv.DictReader(file)

        for row in reader:
            public_row = sanitize_csv_row(
                row
            )

            if (
                public_row["status"].casefold()
                != "active"
            ):
                continue

            flights.append(public_row)

    if not flights:
        raise RuntimeError(
            "The CSV contains no active flights."
        )

    return (
        flights,
        "Villiers Empty Legs",
    )


# ============================================================
# Output
# ============================================================

def sort_flights(flights):
    """
    Sorts flights by date and time.
    """

    return sorted(
        flights,
        key=lambda flight: (
            flight.get(
                "departure_date_iso"
            )
            or "9999-12-31",

            flight.get(
                "departure_time"
            )
            or "23:59",

            flight.get(
                "source_id"
            )
            or "",
        ),
    )


def save_json(
    output_file,
    flights,
    source_title,
):
    """
    Saves the public website data atomically.
    """

    output_file.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    flights = sort_flights(
        flights
    )

    generated_at = utc_now()

    payload = {
        "generated_at": generated_at,
        "source": source_title,
        "provider": "Villiers Jets Limited",
        "publisher": "ONYX Radar",
        "flight_count": len(flights),

        "affiliate_disclosure": (
            "ONYX Radar is an independent "
            "affiliate participating in the "
            "Villiers affiliate programme and "
            "may receive a commission from "
            "qualifying bookings."
        ),

        "data_notice": (
            "Flight details, schedules, "
            "availability and listed prices "
            "are supplied by Villiers and may "
            "change without notice."
        ),

        "flights": flights,
    }

    temporary_file = output_file.with_suffix(
        ".tmp"
    )

    temporary_file.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    temporary_file.replace(
        output_file
    )

    print(
        f"Saved {len(flights)} flights."
    )

    print(
        f"Output: {output_file.resolve()}"
    )


# ============================================================
# Arguments
# ============================================================

def parse_arguments():
    parser = argparse.ArgumentParser(
        description=(
            "Create the public ONYX Radar "
            "flights.json file."
        )
    )

    parser.add_argument(
        "--rss",
        action="store_true",
        help=(
            "Download directly from the RSS "
            "URL in VILLIERS_RSS_URL."
        ),
    )

    parser.add_argument(
        "--csv-pattern",
        default="",
        help=(
            "Read the newest CSV matching "
            "this pattern."
        ),
    )

    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT_FILE),
        help="Output JSON path.",
    )

    return parser.parse_args()


# ============================================================
# Main
# ============================================================

def main():
    arguments = parse_arguments()

    output_file = Path(
        arguments.output
    )

    if arguments.rss:
        flights, source_title = load_from_rss(
            RSS_URL
        )

    else:
        csv_pattern = (
            arguments.csv_pattern
            or DEFAULT_LOCAL_CSV_PATTERN
        )

        matching_files = glob.glob(
            csv_pattern
        )

        if matching_files:
            flights, source_title = (
                load_from_csv(
                    csv_pattern
                )
            )

        elif RSS_URL:
            print(
                "No local CSV was found. "
                "Falling back to RSS."
            )

            flights, source_title = (
                load_from_rss(
                    RSS_URL
                )
            )

        else:
            raise RuntimeError(
                "No local CSV was found and "
                "VILLIERS_RSS_URL is missing."
            )

    save_json(
        output_file,
        flights,
        source_title,
    )


if __name__ == "__main__":
    try:
        main()

    except requests.Timeout:
        print(
            "Error: Villiers RSS request "
            "timed out."
        )
        sys.exit(1)

    except requests.RequestException as error:
        print(
            f"RSS request error: {error}"
        )
        sys.exit(1)

    except Exception as error:
        print(
            f"Website data update failed: "
            f"{error}"
        )
        sys.exit(1)

    sys.exit(0)