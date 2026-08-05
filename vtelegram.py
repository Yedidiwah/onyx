import csv
import glob
import html
import json
import os
import re
import sys
import time
import unicodedata
from pathlib import Path

import pycountry
import telebot
from dotenv import load_dotenv


# ============================================================
# Configuration
# ============================================================

BASE_DIRECTORY = Path(__file__).resolve().parent
ENV_FILE = BASE_DIRECTORY / ".env"

load_dotenv(
    dotenv_path=ENV_FILE
)

BOT_TOKEN = os.getenv(
    "TELEGRAM_BOT_TOKEN"
)

if not BOT_TOKEN:
    raise RuntimeError(
        f"TELEGRAM_BOT_TOKEN was not found "
        f"in {ENV_FILE}"
    )

USERS_DB = BASE_DIRECTORY / "users_db.json"

FLIGHTS_CSV_PATTERN = str(
    BASE_DIRECTORY
    / "exports"
    / "villiers_empty_legs_current_*.csv"
)

# Leave a safety margin below Telegram's
# maximum message size.
TELEGRAM_MESSAGE_LIMIT = 3500

# Telegram limits the frequency of messages
# sent to the same private chat.
MESSAGE_DELAY_SECONDS = 1.1

bot = telebot.TeleBot(
    BOT_TOKEN
)


# ============================================================
# Country aliases
# ============================================================

COUNTRY_ALIASES = {
    "uk": "GB",
    "u k": "GB",
    "great britain": "GB",
    "united kingdom": "GB",

    "us": "US",
    "u s": "US",
    "usa": "US",
    "u s a": "US",
    "united states": "US",
    "united states of america": "US",

    "uae": "AE",
    "u a e": "AE",
    "united arab emirates": "AE",

    "south korea": "KR",
    "north korea": "KP",
    "russia": "RU",
    "vietnam": "VN",
}


# ============================================================
# File loading
# ============================================================

def load_users():
    """
    Loads all subscribed Telegram users.
    """

    if not USERS_DB.exists():
        print(
            f"Users database was not found: "
            f"{USERS_DB}"
        )
        return {}

    try:
        with USERS_DB.open(
            "r",
            encoding="utf-8",
        ) as file:
            data = json.load(file)

        if not isinstance(data, dict):
            print(
                "The users database must "
                "contain a JSON object."
            )
            return {}

        return data

    except json.JSONDecodeError as error:
        print(
            f"Invalid users database JSON: "
            f"{error}"
        )
        return {}

    except OSError as error:
        print(
            f"Failed to read users database: "
            f"{error}"
        )
        return {}


def get_latest_flights_csv():
    """
    Finds the newest current Empty Legs CSV.
    """

    files = glob.glob(
        FLIGHTS_CSV_PATTERN
    )

    if not files:
        return None

    latest_file = max(
        files,
        key=os.path.getmtime,
    )

    return Path(
        latest_file
    )


def load_flights(csv_file):
    """
    Loads all active flights from the CSV.
    """

    flights = []

    with csv_file.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as file:
        reader = csv.DictReader(
            file
        )

        for row in reader:
            status = str(
                row.get(
                    "status",
                    "active",
                )
            ).strip().casefold()

            if (
                status
                and status != "active"
            ):
                continue

            flights.append(
                row
            )

    flights.sort(
        key=lambda flight: (
            flight.get(
                "departure_date_iso",
                "",
            ),
            flight.get(
                "departure_time",
                "",
            ),
            flight.get(
                "origin_iata",
                "",
            ),
            flight.get(
                "destination_iata",
                "",
            ),
        )
    )

    return flights


# ============================================================
# Text helpers
# ============================================================

def normalize_text(value):
    """
    Normalizes text for matching.
    """

    value = str(
        value or ""
    ).strip()

    value = unicodedata.normalize(
        "NFKD",
        value,
    )

    value = "".join(
        character
        for character in value
        if not unicodedata.combining(
            character
        )
    )

    value = value.casefold()

    value = re.sub(
        r"[^a-z0-9]+",
        " ",
        value,
    )

    return " ".join(
        value.split()
    )


def escape(value):
    """
    Escapes text for Telegram HTML.
    """

    return html.escape(
        str(value or "")
    )


def is_not_set(value):
    """
    Checks whether a route preference
    represents an unrestricted location.
    """

    normalized = normalize_text(
        value
    )

    return normalized in {
        "",
        "not set",
        "none",
        "any",
        "all",
        "anywhere",
        "global",
        "anywhere global",
    }


# ============================================================
# Country helpers
# ============================================================

def get_country_codes(country_value):
    """
    Returns possible ISO codes for a
    country name.
    """

    country_value = str(
        country_value or ""
    ).strip()

    normalized_country = normalize_text(
        country_value
    )

    results = set()

    if not normalized_country:
        return results

    alias_code = COUNTRY_ALIASES.get(
        normalized_country
    )

    if alias_code:
        results.add(
            alias_code.upper()
        )

    try:
        country = pycountry.countries.lookup(
            country_value
        )

        results.add(
            country.alpha_2.upper()
        )

        results.add(
            country.alpha_3.upper()
        )

    except LookupError:
        pass

    return results


def get_country_name(country_value):
    """
    Converts an ISO country code to an
    English country name.
    """

    country_value = str(
        country_value or ""
    ).strip()

    if not country_value:
        return ""

    try:
        country = None

        if len(country_value) == 2:
            country = pycountry.countries.get(
                alpha_2=country_value.upper()
            )

        elif len(country_value) == 3:
            country = pycountry.countries.get(
                alpha_3=country_value.upper()
            )

        else:
            country = pycountry.countries.lookup(
                country_value
            )

        if country:
            return country.name

    except LookupError:
        pass

    return country_value


# ============================================================
# Route preference helpers
# ============================================================

def extract_preference_codes(preference):
    """
    Extracts IATA or ICAO codes from a
    preference.

    Examples:
    Rome, Italy (FCO)
    London (LHR)
    EGLL
    """

    preference = str(
        preference or ""
    ).upper()

    codes = set()

    parenthesized_codes = re.findall(
        r"\(([A-Z0-9]{3,4})\)",
        preference,
    )

    codes.update(
        parenthesized_codes
    )

    stripped_preference = (
        preference.strip()
    )

    if re.fullmatch(
        r"[A-Z0-9]{3,4}",
        stripped_preference,
    ):
        codes.add(
            stripped_preference
        )

    return codes


def get_location_data(
    flight,
    side,
):
    """
    Returns normalized airport information.

    side must be either:
    origin
    destination
    """

    return {
        "raw": str(
            flight.get(
                f"{side}_airport_raw",
                "",
            )
        ).strip(),

        "icao": str(
            flight.get(
                f"{side}_icao",
                "",
            )
        ).strip().upper(),

        "iata": str(
            flight.get(
                f"{side}_iata",
                "",
            )
        ).strip().upper(),

        "name": str(
            flight.get(
                f"{side}_airport_name",
                "",
            )
        ).strip(),

        "city": str(
            flight.get(
                f"{side}_city",
                "",
            )
        ).strip(),

        "country": str(
            flight.get(
                f"{side}_country",
                "",
            )
        ).strip().upper(),
    }


# ============================================================
# Route matching
# ============================================================

def match_country(
    requested_country,
    location,
):
    """
    Matches a country name against an
    airport country.
    """

    requested_country = str(
        requested_country or ""
    ).strip()

    requested_normalized = normalize_text(
        requested_country
    )

    location_country = str(
        location.get(
            "country",
            "",
        )
    ).strip().upper()

    requested_codes = get_country_codes(
        requested_country
    )

    if (
        location_country
        and location_country
        in requested_codes
    ):
        return True

    location_country_name = get_country_name(
        location_country
    )

    if (
        requested_normalized
        and requested_normalized
        == normalize_text(
            location_country_name
        )
    ):
        return True

    combined_location = normalize_text(
        " ".join(
            [
                location.get(
                    "raw",
                    "",
                ),
                location.get(
                    "name",
                    "",
                ),
                location.get(
                    "city",
                    "",
                ),
                location_country,
                location_country_name,
            ]
        )
    )

    return (
        bool(requested_normalized)
        and requested_normalized
        in combined_location
    )


def matches_location(
    preference,
    location,
):
    """
    Checks whether an airport matches one
    user preference.
    """

    preference = str(
        preference or ""
    ).strip()

    if is_not_set(preference):
        return True

    normalized_preference = normalize_text(
        preference
    )

    # Country wildcard:
    # Anywhere in France
    anywhere_match = re.match(
        r"^\s*anywhere\s+in\s+(.+?)\s*$",
        preference,
        flags=re.IGNORECASE,
    )

    if anywhere_match:
        requested_country = (
            anywhere_match.group(1).strip()
        )

        return match_country(
            requested_country,
            location,
        )

    # Exact IATA or ICAO code matching.
    preference_codes = (
        extract_preference_codes(
            preference
        )
    )

    location_codes = {
        location.get(
            "iata",
            "",
        ),
        location.get(
            "icao",
            "",
        ),
    }

    location_codes.discard("")

    # If the user selected a specific
    # airport code, require an exact match.
    if preference_codes:
        return bool(
            preference_codes
            & location_codes
        )

    # Remove a possible code from text.
    preference_without_code = re.sub(
        r"\([A-Z0-9]{3,4}\)",
        "",
        preference,
        flags=re.IGNORECASE,
    ).strip()

    preference_parts = [
        part.strip()
        for part
        in preference_without_code.split(",")
        if part.strip()
    ]

    requested_city = (
        preference_parts[0]
        if preference_parts
        else preference_without_code
    )

    requested_country = (
        preference_parts[1]
        if len(preference_parts) > 1
        else ""
    )

    requested_city_normalized = (
        normalize_text(
            requested_city
        )
    )

    location_city = normalize_text(
        location.get(
            "city",
            "",
        )
    )

    location_name = normalize_text(
        location.get(
            "name",
            "",
        )
    )

    location_raw = normalize_text(
        location.get(
            "raw",
            "",
        )
    )

    city_matches = False

    if requested_city_normalized:
        city_matches = (
            requested_city_normalized
            == location_city
            or requested_city_normalized
            in location_name
            or requested_city_normalized
            in location_raw
        )

    if requested_country:
        country_matches = match_country(
            requested_country,
            location,
        )

        return (
            city_matches
            and country_matches
        )

    if city_matches:
        return True

    # If the preference itself is a country.
    possible_country_codes = (
        get_country_codes(
            preference_without_code
        )
    )

    if possible_country_codes:
        if match_country(
            preference_without_code,
            location,
        ):
            return True

    # Generic airport-name fallback.
    return (
        bool(normalized_preference)
        and (
            normalized_preference
            in location_name
            or normalized_preference
            in location_raw
        )
    )


def flight_matches_user(
    flight,
    preferences,
):
    """
    Checks whether a flight matches the
    user's origin and destination.
    """

    origin_preference = preferences.get(
        "origin",
        "Not set",
    )

    destination_preference = (
        preferences.get(
            "destination",
            "Not set",
        )
    )

    origin_location = get_location_data(
        flight,
        "origin",
    )

    destination_location = get_location_data(
        flight,
        "destination",
    )

    origin_matches = matches_location(
        origin_preference,
        origin_location,
    )

    destination_matches = matches_location(
        destination_preference,
        destination_location,
    )

    return (
        origin_matches
        and destination_matches
    )


# ============================================================
# Airport display
# ============================================================

def format_airport(
    flight,
    side,
):
    """
    Formats an airport with city, country,
    IATA and ICAO codes.
    """

    city = str(
        flight.get(
            f"{side}_city",
            "",
        )
    ).strip()

    airport_name = str(
        flight.get(
            f"{side}_airport_name",
            "",
        )
    ).strip()

    airport_raw = str(
        flight.get(
            f"{side}_airport_raw",
            "",
        )
    ).strip()

    country_code = str(
        flight.get(
            f"{side}_country",
            "",
        )
    ).strip()

    iata = str(
        flight.get(
            f"{side}_iata",
            "",
        )
    ).strip().upper()

    icao = str(
        flight.get(
            f"{side}_icao",
            "",
        )
    ).strip().upper()

    country_name = get_country_name(
        country_code
    )

    location_name = (
        city
        or airport_name
        or airport_raw
        or "Unknown airport"
    )

    location_parts = [
        location_name
    ]

    if (
        country_name
        and normalize_text(
            country_name
        )
        not in normalize_text(
            location_name
        )
    ):
        location_parts.append(
            country_name
        )

    display_location = ", ".join(
        location_parts
    )

    codes = []

    if iata:
        codes.append(
            iata
        )

    if icao and icao != iata:
        codes.append(
            icao
        )

    result = escape(
        display_location
    )

    if codes:
        result += (
            " ("
            + escape(
                " / ".join(codes)
            )
            + ")"
        )

    return result


# ============================================================
# Flight formatting
# ============================================================

def format_flight(flight):
    """
    Creates one compact Telegram flight card.
    """

    origin = format_airport(
        flight,
        "origin",
    )

    destination = format_airport(
        flight,
        "destination",
    )

    departure_date = escape(
        flight.get(
            "departure_date_raw"
        )
        or flight.get(
            "departure_date_iso"
        )
        or "Not specified"
    )

    departure_time = escape(
        flight.get(
            "departure_time"
        )
        or "Not specified"
    )

    arrival_time = escape(
        flight.get(
            "arrival_time"
        )
        or "Not specified"
    )

    aircraft = escape(
        flight.get(
            "aircraft_type"
        )
        or "Not specified"
    )

    duration = escape(
        flight.get(
            "flight_duration"
        )
        or "Not specified"
    )

    price = escape(
        flight.get(
            "price_raw"
        )
        or "Request price"
    )

    seats = escape(
        flight.get(
            "seats_available"
        )
        or "Not specified"
    )

    booking_link = str(
        flight.get(
            "booking_link"
        )
        or flight.get(
            "tracking_link"
        )
        or flight.get(
            "rss_link"
        )
        or ""
    ).strip()

    # Always-visible information.
    message = (
        f"🛫 <b>{origin}</b>\n"
        f"🛬 <b>{destination}</b>\n"
        f"📅 <b>{departure_date}</b>"
        f"  |  🕒 <b>{departure_time}</b>\n"
    )

    # Expandable information.
    details = (
        "Tap to view full flight details\n\n"
        f"🕓 <b>Arrival:</b> "
        f"{arrival_time}\n"
        f"⏱ <b>Duration:</b> "
        f"{duration}\n"
        f"🛩 <b>Aircraft:</b> "
        f"{aircraft}\n"
        f"👥 <b>Seats Available:</b> "
        f"{seats}\n"
        f"💰 <b>Listed Price:</b> "
        f"{price}\n"
    )

    if booking_link:
        safe_link = html.escape(
            booking_link,
            quote=True,
        )

        details += (
            "\n"
            f"🔗 <a href=\"{safe_link}\">"
            "<b>View and Book This Flight</b>"
            "</a>\n"
        )

    message += (
        "<blockquote expandable>"
        f"{details}"
        "</blockquote>"
    )

    return message


# ============================================================
# Message grouping
# ============================================================

def display_preference(
    preference,
    empty_label,
):
    """
    Provides a friendly display value for
    an unrestricted preference.
    """

    if is_not_set(preference):
        return empty_label

    return str(
        preference
    )


def build_message_chunks(
    flights,
    preferences,
):
    """
    Splits flights into Telegram-safe
    messages.

    Returns a list of:
    message text, number of flights
    """

    origin_preference = display_preference(
        preferences.get(
            "origin",
            "Not set",
        ),
        "All origins",
    )

    destination_preference = (
        display_preference(
            preferences.get(
                "destination",
                "Not set",
            ),
            "All destinations",
        )
    )

    header = (
        "✨ <b>ONYX Current Empty Leg "
        "Opportunities</b> ✨\n\n"
        f"🛫 <b>Your origin:</b> "
        f"{escape(origin_preference)}\n"
        f"🛬 <b>Your destination:</b> "
        f"{escape(destination_preference)}\n"
        f"📊 <b>Matching flights:</b> "
        f"{len(flights)}\n\n"
    )

    continuation_header = (
        "✨ <b>ONYX Empty Legs "
        "— Continued</b> ✨\n\n"
    )

    chunks = []

    current_message = header
    current_flight_count = 0

    for flight in flights:
        flight_block = (
            format_flight(
                flight
            )
            + "\n──────────────\n\n"
        )

        prospective_length = (
            len(current_message)
            + len(flight_block)
        )

        if (
            prospective_length
            > TELEGRAM_MESSAGE_LIMIT
            and current_flight_count > 0
        ):
            chunks.append(
                (
                    current_message.rstrip(),
                    current_flight_count,
                )
            )

            current_message = (
                continuation_header
                + flight_block
            )

            current_flight_count = 1

        else:
            current_message += (
                flight_block
            )

            current_flight_count += 1

    if current_flight_count > 0:
        chunks.append(
            (
                current_message.rstrip(),
                current_flight_count,
            )
        )

    return chunks


# ============================================================
# Telegram sending
# ============================================================

def send_user_flights(
    chat_id,
    preferences,
    flights,
):
    """
    Sends all matching current flights to
    one Telegram user.

    Returns:
    sent flight count, failed flag
    """

    matching_flights = [
        flight
        for flight in flights
        if flight_matches_user(
            flight,
            preferences,
        )
    ]

    first_name = str(
        preferences.get(
            "first_name",
            "Traveler",
        )
    )

    if not matching_flights:
        print(
            f"No matches for "
            f"{first_name} ({chat_id})"
        )

        return 0, False

    chunks = build_message_chunks(
        matching_flights,
        preferences,
    )

    sent_messages = 0
    sent_flights = 0
    failed = False

    for (
        chunk_text,
        chunk_flight_count,
    ) in chunks:
        try:
            bot.send_message(
                chat_id,
                chunk_text,
                parse_mode="HTML",
                disable_web_page_preview=True,
            )

            sent_messages += 1

            sent_flights += (
                chunk_flight_count
            )

            time.sleep(
                MESSAGE_DELAY_SECONDS
            )

        except Exception as error:
            failed = True

            print(
                f"Failed to send to "
                f"{chat_id}: {error}"
            )

            break

    print(
        f"Sent {sent_flights} of "
        f"{len(matching_flights)} flights "
        f"in {sent_messages} messages to "
        f"{first_name} ({chat_id})"
    )

    return (
        sent_flights,
        failed,
    )


# ============================================================
# Main process
# ============================================================

def process_all_alerts():
    """
    Sends all current matching flights to
    all subscribed users.
    """

    try:
        bot_info = bot.get_me()

        print(
            f"Connected to Telegram bot: "
            f"@{bot_info.username} "
            f"(bot ID: {bot_info.id})"
        )

    except Exception as error:
        print(
            f"Could not connect to Telegram: "
            f"{error}"
        )
        return False

    latest_csv = get_latest_flights_csv()

    if latest_csv is None:
        print(
            "No current VILLIERS CSV "
            "file was found."
        )

        print(
            f"Expected file pattern: "
            f"{FLIGHTS_CSV_PATTERN}"
        )

        return False

    print(
        f"Reading flights from: "
        f"{latest_csv}"
    )

    try:
        flights = load_flights(
            latest_csv
        )

    except Exception as error:
        print(
            f"Failed to load flights: "
            f"{error}"
        )
        return False

    print(
        f"Loaded {len(flights)} active "
        "Empty Leg flights."
    )

    users = load_users()

    if not users:
        print(
            "No subscribed users were found."
        )
        return True

    print(
        f"Processing {len(users)} users."
    )

    total_flights_sent = 0
    successful_users = 0
    failed_users = 0

    for (
        chat_id,
        preferences,
    ) in users.items():
        sent_count, failed = (
            send_user_flights(
                chat_id,
                preferences,
                flights,
            )
        )

        total_flights_sent += (
            sent_count
        )

        if sent_count > 0:
            successful_users += 1

        if failed:
            failed_users += 1

    print()
    print(
        "Telegram processing complete."
    )

    print(
        f"Users who received flights: "
        f"{successful_users}"
    )

    print(
        f"Users with delivery errors: "
        f"{failed_users}"
    )

    print(
        f"Total flight entries delivered: "
        f"{total_flights_sent}"
    )

    # A single unavailable user should not
    # prevent processing of all other users.
    return True


# ============================================================
# Start
# ============================================================

if __name__ == "__main__":
    success = process_all_alerts()

    if success:
        sys.exit(0)

    sys.exit(1)
