import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import airportsdata
import pycountry


SCRIPT_DIRECTORY = Path(__file__).resolve().parent
SITE_ROOT = SCRIPT_DIRECTORY.parent

DEFAULT_OUTPUT_FILE = (
    SITE_ROOT
    / "data"
    / "airports.json"
)


def utc_now():
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
    )


def clean_value(value):
    if value is None:
        return ""

    value = str(value).strip()

    if value.casefold() in {
        "",
        "none",
        "null",
        "\\n",
    }:
        return ""

    return value


def get_country_name(country_code):
    country_code = clean_value(
        country_code
    ).upper()

    if not country_code:
        return ""

    try:
        country = None

        if len(country_code) == 2:
            country = pycountry.countries.get(
                alpha_2=country_code
            )

        elif len(country_code) == 3:
            country = pycountry.countries.get(
                alpha_3=country_code
            )

        if country:
            return country.name

    except LookupError:
        pass

    return country_code


def build_airports():
    print(
        "Loading global airport database..."
    )

    database = airportsdata.load(
        "ICAO"
    )

    airports = []
    countries = {}

    for icao_code, airport in database.items():
        icao = clean_value(
            icao_code
            or airport.get("icao")
        ).upper()

        iata = clean_value(
            airport.get("iata")
        ).upper()

        name = clean_value(
            airport.get("name")
        )

        city = clean_value(
            airport.get("city")
        )

        country_code = clean_value(
            airport.get("country")
        ).upper()

        if not icao:
            continue

        if not name and not city:
            continue

        country_name = get_country_name(
            country_code
        )

        if country_code:
            countries[country_code] = (
                country_name
                or country_code
            )

        airports.append(
            {
                "icao": icao,
                "iata": iata,
                "name": name,
                "city": city,
                "country_code": country_code,
                "country_name": (
                    country_name
                ),
            }
        )

    airports.sort(
        key=lambda airport: (
            airport["country_name"],
            airport["city"],
            airport["name"],
            airport["icao"],
        )
    )

    country_list = [
        {
            "code": country_code,
            "name": country_name,
        }
        for country_code, country_name
        in sorted(
            countries.items(),
            key=lambda item: item[1],
        )
    ]

    print(
        f"Prepared {len(airports)} airports "
        f"in {len(country_list)} countries."
    )

    return airports, country_list


def save_airports_json(
    output_file,
    airports,
    countries,
):
    output_file.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    payload = {
        "generated_at": utc_now(),
        "source": "airportsdata",
        "airport_count": len(airports),
        "country_count": len(countries),
        "countries": countries,
        "airports": airports,
    }

    temporary_file = output_file.with_suffix(
        ".tmp"
    )

    # Compact JSON keeps the global catalogue
    # significantly smaller for mobile users.
    temporary_file.write_text(
        json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )

    temporary_file.replace(
        output_file
    )

    print(
        f"Airport catalogue saved to: "
        f"{output_file.resolve()}"
    )


def parse_arguments():
    parser = argparse.ArgumentParser(
        description=(
            "Build the public ONYX Radar "
            "airport catalogue."
        )
    )

    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT_FILE),
    )

    return parser.parse_args()


def main():
    arguments = parse_arguments()

    output_file = Path(
        arguments.output
    )

    airports, countries = (
        build_airports()
    )

    save_airports_json(
        output_file,
        airports,
        countries,
    )


if __name__ == "__main__":
    try:
        main()

    except Exception as error:
        print(
            f"Airport catalogue generation "
            f"failed: {error}"
        )
        sys.exit(1)

    sys.exit(0)
