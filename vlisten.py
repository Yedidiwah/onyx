import html
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import telebot
from dotenv import load_dotenv
from telebot.types import (
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    WebAppInfo,
)


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

DB_FILE = BASE_DIRECTORY / "users_db.json"

WEBAPP_URL = (
    "https://yedidiwah.github.io/onyx/telegram/index.html?v=2.1"
)

bot = telebot.TeleBot(BOT_TOKEN)


# ============================================================
# Time
# ============================================================

def utc_now():
    """
    Returns the current UTC time in ISO
    format.
    """

    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
    )


# ============================================================
# Database
# ============================================================

def load_db():
    """
    Loads the users database.
    """

    if not DB_FILE.exists():
        return {}

    try:
        with DB_FILE.open(
            "r",
            encoding="utf-8",
        ) as file:
            data = json.load(file)

        if not isinstance(data, dict):
            print(
                "The users database must contain "
                "a JSON object."
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
            f"Failed to load users database: "
            f"{error}"
        )
        return {}


def save_db(db):
    """
    Saves the users database atomically.
    """

    temporary_file = DB_FILE.with_suffix(
        ".tmp"
    )

    with temporary_file.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            db,
            file,
            indent=4,
            ensure_ascii=False,
        )

    temporary_file.replace(
        DB_FILE
    )


# ============================================================
# User helpers
# ============================================================

def get_first_name(message):
    """
    Returns a safe fallback first name.
    """

    return (
        message.from_user.first_name
        or "Traveler"
    )


def ensure_user(db, message):
    """
    Creates or updates one user record.
    """

    chat_id = str(
        message.chat.id
    )

    first_name = get_first_name(
        message
    )

    if chat_id not in db:
        db[chat_id] = {
	    "first_name": first_name,
            "origin": "Not set",
            "destination": "Not set",
            "frequency_hours": 1,
            "last_sent_timestamp": 0,
            "status": "free",
            "registered_at": utc_now(),
            "preferences_updated_at": "",
        }

    else:
	db[chat_id]["first_name"] = first_name
        db[chat_id].setdefault("origin", "Not set")
        db[chat_id].setdefault("destination", "Not set")
        db[chat_id].setdefault("frequency_hours", 1)
        db[chat_id].setdefault("last_sent_timestamp", 0)
        db[chat_id].setdefault("status", "free")
        db[chat_id].setdefault("registered_at", utc_now())
        db[chat_id].setdefault("preferences_updated_at", "")

    return chat_id


# ============================================================
# Keyboard
# ============================================================

def main_menu_keyboard():
    """
    Creates the persistent bot keyboard.
    """

    markup = ReplyKeyboardMarkup(
        resize_keyboard=True
    )

    preferences_button = KeyboardButton(
        text="✈ Set Your Preferences",
        web_app=WebAppInfo(
            url=WEBAPP_URL
        ),
    )

    stop_button = KeyboardButton(
        text="🛑 Stop Alerts"
    )

    markup.add(
        preferences_button
    )

    markup.add(
        stop_button
    )

    return markup


# ============================================================
# Start and help
# ============================================================

@bot.message_handler(
    commands=["start", "help"]
)
def send_welcome(message):
    """
    Registers the user and displays the
    welcome message.
    """

    db = load_db()

    chat_id = ensure_user(
        db,
        message,
    )

    save_db(db)

    first_name = get_first_name(
        message
    )

    safe_name = html.escape(
        first_name
    )

    current_origin = db[chat_id].get(
        "origin",
        "Not set",
    )

    current_destination = db[chat_id].get(
        "destination",
        "Not set",
    )

    welcome_text = (
        f"Welcome to <b>ONYX</b>, "
        f"{safe_name}. 🛩\n\n"
        "You are subscribed to our private "
        "jet Empty Leg alerts.\n\n"
        "If no route is selected, you will "
        "receive all currently available "
        "Empty Leg opportunities.\n\n"
        "If you select an origin and "
        "destination, you will receive only "
        "flights matching your preferences."
    )

    if (
        current_origin != "Not set"
        or current_destination != "Not set"
    ):
        welcome_text += (
            "\n\n"
            f"🛫 <b>Current origin:</b> "
            f"{html.escape(str(current_origin))}\n"
            f"🛬 <b>Current destination:</b> "
            f"{html.escape(str(current_destination))}"
        )

    bot.send_message(
        message.chat.id,
        welcome_text,
        parse_mode="HTML",
        reply_markup=main_menu_keyboard(),
    )

    print(
        f"User started the bot: "
        f"{first_name} ({chat_id})"
    )


# ============================================================
# Chat ID
# ============================================================

@bot.message_handler(
    commands=["myid"]
)
def show_chat_id(message):
    """
    Displays the user's Telegram Chat ID.
    """

    chat_id = str(
        message.chat.id
    )

    bot.send_message(
        message.chat.id,
        "Your Telegram Chat ID is:\n"
        f"<code>{html.escape(chat_id)}</code>",
        parse_mode="HTML",
        reply_markup=main_menu_keyboard(),
    )

    print(
        f"Chat ID requested by "
        f"{get_first_name(message)}: "
        f"{chat_id}"
    )


# ============================================================
# Current preferences
# ============================================================

@bot.message_handler(
    commands=["preferences"]
)
def show_preferences(message):
    """
    Shows the user's current preferences.
    """

    chat_id = str(
        message.chat.id
    )

    db = load_db()

    if chat_id not in db:
        ensure_user(
            db,
            message,
        )
        save_db(db)

    user = db[chat_id]

    origin = html.escape(
        str(
            user.get(
                "origin",
                "Not set",
            )
        )
    )

    destination = html.escape(
        str(
            user.get(
                "destination",
                "Not set",
            )
        )
    )

    text = (
        "✈️ <b>Your Current Preferences</b>\n\n"
        f"🛫 <b>Origin:</b> {origin}\n"
        f"🛬 <b>Destination:</b> "
        f"{destination}\n\n"
        "If both preferences are not set, "
        "you will receive all current flights."
    )

    bot.send_message(
        message.chat.id,
        text,
        parse_mode="HTML",
        reply_markup=main_menu_keyboard(),
    )


# ============================================================
# Mini App data
# ============================================================

@bot.message_handler(
    content_types=["web_app_data"]
)
def handle_webapp_data(message):
    """
    Receives origin and destination from the
    Telegram Mini App.
    """

    chat_id = str(
        message.chat.id
    )

    try:
        raw_data = (
            message.web_app_data.data
        )

        preferences = json.loads(
            raw_data
        )

        if not isinstance(
            preferences,
            dict,
        ):
            raise ValueError(
                "Web App data must be "
                "a JSON object."
            )

        origin = str(
            preferences.get(
                "origin",
                "Not set",
            )
        ).strip()

        destination = str(
            preferences.get(
                "destination",
                "Not set",
            )
        ).strip()

	frequency_hours = preferences.get("frequency_hours", 1)

        if not origin:
            origin = "Not set"

        if not destination:
            destination = "Not set"



        db = load_db()

        ensure_user(
            db,
            message,
        )

	db[chat_id]["origin"] = origin
        db[chat_id]["destination"] = destination
        db[chat_id]["frequency_hours"] = frequency_hours
        db[chat_id]["preferences_updated_at"] = utc_now()

        save_db(db)

        safe_origin = html.escape(
            origin
        )

        safe_destination = html.escape(
            destination
        )

        summary = (
            "✅ <b>Your Preferences "
            "Have Been Updated</b>\n\n"
            f"🛫 <b>Origin:</b> "
            f"{safe_origin}\n"
            f"🛬 <b>Destination:</b> "
            f"{safe_destination}\n\n"
        )

        if (
            origin == "Not set"
            and destination == "Not set"
        ):
            summary += (
                "You will receive all current "
                "Empty Leg opportunities."
            )

        elif origin == "Not set":
            summary += (
                "You will receive current "
                "Empty Leg opportunities to "
                "your selected destination."
            )

        elif destination == "Not set":
            summary += (
                "You will receive current "
                "Empty Leg opportunities from "
                "your selected origin."
            )

        else:
            summary += (
                "You will receive current "
                "Empty Leg opportunities "
                "matching this route."
            )

        bot.send_message(
            message.chat.id,
            summary,
            parse_mode="HTML",
            reply_markup=main_menu_keyboard(),
        )

        print(
            f"Preferences updated for "
            f"{get_first_name(message)} "
            f"({chat_id}): "
            f"{origin} -> {destination}"
        )

    except json.JSONDecodeError as error:
        print(
            f"Invalid Web App JSON for "
            f"{chat_id}: {error}"
        )

        bot.send_message(
            message.chat.id,
            "⚠️ The preferences data was "
            "invalid. Please try again.",
            reply_markup=main_menu_keyboard(),
        )

    except Exception as error:
        print(
            f"Web App data error for "
            f"{chat_id}: {error}"
        )

        bot.send_message(
            message.chat.id,
            "⚠️ Error syncing your "
            "preferences. Please try again.",
            reply_markup=main_menu_keyboard(),
        )


# ============================================================
# Stop alerts
# ============================================================

@bot.message_handler(
    func=lambda message: (
        message.text == "🛑 Stop Alerts"
    )
)
def stop_alerts(message):
    """
    Removes the user from the alerts database.
    """

    chat_id = str(
        message.chat.id
    )

    db = load_db()

    if chat_id in db:
        del db[chat_id]
        save_db(db)

    bot.send_message(
        message.chat.id,
        "🛑 You have been removed from "
        "ONYX alerts.\n\n"
        "Send /start at any time to "
        "subscribe again.",
        reply_markup=ReplyKeyboardRemove(),
    )

    print(
        f"User removed from alerts: "
        f"{get_first_name(message)} "
        f"({chat_id})"
    )


# ============================================================
# Other messages
# ============================================================

@bot.message_handler(
    func=lambda message: True
)
def handle_text_input(message):
    """
    Handles unsupported text messages.
    """

    bot.send_message(
        message.chat.id,
        "Please use the ONYX Preferences "
        "menu below.",
        reply_markup=main_menu_keyboard(),
    )


# ============================================================
# Start listener
# ============================================================

def main():
    """
    Starts the Telegram registration listener.
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

    print(
        "ONYX listener is active."
    )

    print(
        "Press Ctrl+C to stop."
    )

    bot.infinity_polling(
        skip_pending=True,
        timeout=30,
        long_polling_timeout=30,
    )

    return True


if __name__ == "__main__":
    try:
        success = main()

        if success:
            sys.exit(0)

        sys.exit(1)

    except KeyboardInterrupt:
        print()
        print(
            "ONYX listener stopped."
        )
        sys.exit(0)

    except Exception as error:
        print(
            f"Listener error: {error}"
        )
        sys.exit(1)
