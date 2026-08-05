"use strict";

const TELEGRAM_BOT_USERNAME = "OnyxAirRadar_bot";
const FLIGHTS_DATA_URL = "data/flights.json";

const state = {
    flights: [],
    filteredFlights: [],
    metadata: {},
};

const elements = {
    origin: document.querySelector("#origin-filter"),
    destination: document.querySelector("#destination-filter"),
    dateFrom: document.querySelector("#date-from"),
    dateTo: document.querySelector("#date-to"),
    minimumSeats: document.querySelector("#minimum-seats"),
    aircraft: document.querySelector("#aircraft-filter"),
    currency: document.querySelector("#currency-filter"),
    maximumPrice: document.querySelector("#maximum-price"),
    sort: document.querySelector("#sort-filter"),

    clearFilters: document.querySelector("#clear-filters"),
    emptyClearFilters: document.querySelector(
        "#empty-clear-filters"
    ),

    telegramLink: document.querySelector(
        "#filtered-telegram-link"
    ),

    flightGrid: document.querySelector("#flight-grid"),
    loadingState: document.querySelector("#loading-state"),
    errorState: document.querySelector("#error-state"),
    errorMessage: document.querySelector("#error-message"),
    emptyState: document.querySelector("#empty-state"),
    retryLoading: document.querySelector("#retry-loading"),

    resultsStatus: document.querySelector("#results-status"),
    lastUpdated: document.querySelector("#last-updated"),

    heroFlightCount: document.querySelector(
        "#hero-flight-count"
    ),

    heroCountryCount: document.querySelector(
        "#hero-country-count"
    ),

    currentYear: document.querySelector("#current-year"),
};

const countryDisplayNames = (
    typeof Intl.DisplayNames === "function"
        ? new Intl.DisplayNames(
            ["en"],
            { type: "region" }
        )
        : null
);


function escapeHtml(value) {
    return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}


function normalize(value) {
    return String(value ?? "")
        .trim()
        .toLocaleLowerCase("en");
}


function countryName(countryCode) {
    const code = String(countryCode ?? "")
        .trim()
        .toUpperCase();

    if (!code) {
        return "";
    }

    try {
        if (countryDisplayNames && code.length === 2) {
            return countryDisplayNames.of(code) || code;
        }
    } catch {
        return code;
    }

    return code;
}


function parseNumber(value) {
    const normalized = String(value ?? "")
        .replace(/[^\d.-]/g, "");

    const parsed = Number.parseFloat(normalized);

    return Number.isFinite(parsed)
        ? parsed
        : null;
}


function parseInteger(value) {
    const parsed = Number.parseInt(
        String(value ?? ""),
        10
    );

    return Number.isFinite(parsed)
        ? parsed
        : null;
}


function safeExternalUrl(value) {
    try {
        const url = new URL(String(value ?? ""));

        if (
            url.protocol === "https:"
            || url.protocol === "http:"
        ) {
            return url.href;
        }
    } catch {
        return "";
    }

    return "";
}


function airportCode(flight, side) {
    return (
        String(flight[`${side}_iata`] ?? "").trim()
        || String(flight[`${side}_icao`] ?? "").trim()
        || "—"
    ).toUpperCase();
}


function airportLongCode(flight, side) {
    const iata = String(
        flight[`${side}_iata`] ?? ""
    ).trim().toUpperCase();

    const icao = String(
        flight[`${side}_icao`] ?? ""
    ).trim().toUpperCase();

    return iata || icao;
}


function airportLabel(flight, side) {
    const city = String(
        flight[`${side}_city`] ?? ""
    ).trim();

    const airportName = String(
        flight[`${side}_airport_name`] ?? ""
    ).trim();

    const raw = String(
        flight[`${side}_airport_raw`] ?? ""
    ).trim();

    const country = countryName(
        flight[`${side}_country`]
    );

    const iata = String(
        flight[`${side}_iata`] ?? ""
    ).trim().toUpperCase();

    const icao = String(
        flight[`${side}_icao`] ?? ""
    ).trim().toUpperCase();

    const location = city || airportName || raw || "Unknown";
    const codes = [...new Set([iata, icao].filter(Boolean))];

    const locationWithCountry = country
        ? `${location}, ${country}`
        : location;

    return codes.length
        ? `${locationWithCountry} (${codes.join(" / ")})`
        : locationWithCountry;
}


function createAirportOptions(side) {
    const countries = new Map();
    const airports = new Map();

    for (const flight of state.flights) {
        const countryCode = String(
            flight[`${side}_country`] ?? ""
        ).trim().toUpperCase();

        if (countryCode) {
            countries.set(
                countryCode,
                countryName(countryCode)
            );
        }

        const code = airportLongCode(flight, side);

        if (code) {
            airports.set(
                code,
                airportLabel(flight, side)
            );
        }
    }

    const select = elements[side];
    const currentValue = select.value;

    select.innerHTML = "";

    const allOption = document.createElement("option");
    allOption.value = "all";
    allOption.textContent = (
        side === "origin"
            ? "All origins"
            : "All destinations"
    );

    select.append(allOption);

    const countryGroup = document.createElement("optgroup");
    countryGroup.label = "Countries";

    [...countries.entries()]
        .sort((a, b) => a[1].localeCompare(b[1]))
        .forEach(([code, name]) => {
            const option = document.createElement("option");

            option.value = `country:${code}`;
            option.textContent = `Anywhere in ${name}`;

            countryGroup.append(option);
        });

    select.append(countryGroup);

    const airportGroup = document.createElement("optgroup");
    airportGroup.label = "Specific airports";

    [...airports.entries()]
        .sort((a, b) => a[1].localeCompare(b[1]))
        .forEach(([code, label]) => {
            const option = document.createElement("option");

            option.value = `airport:${code}`;
            option.textContent = label;

            airportGroup.append(option);
        });

    select.append(airportGroup);

    if (
        [...select.options].some(
            option => option.value === currentValue
        )
    ) {
        select.value = currentValue;
    }
}


function createAircraftOptions() {
    const aircraft = new Set();

    for (const flight of state.flights) {
        const aircraftType = String(
            flight.aircraft_type ?? ""
        ).trim();

        if (aircraftType) {
            aircraft.add(aircraftType);
        }
    }

    elements.aircraft.innerHTML = (
        '<option value="all">All aircraft</option>'
    );

    [...aircraft]
        .sort((a, b) => a.localeCompare(b))
        .forEach(aircraftType => {
            const option = document.createElement("option");

            option.value = aircraftType;
            option.textContent = aircraftType;

            elements.aircraft.append(option);
        });
}


function createCurrencyOptions() {
    const currencies = new Set();

    for (const flight of state.flights) {
        const currency = String(
            flight.price_currency ?? ""
        ).trim().toUpperCase();

        if (currency) {
            currencies.add(currency);
        }
    }

    elements.currency.innerHTML = (
        '<option value="all">All currencies</option>'
    );

    [...currencies]
        .sort()
        .forEach(currency => {
            const option = document.createElement("option");

            option.value = currency;
            option.textContent = currency;

            elements.currency.append(option);
        });
}


function matchesRouteSelection(flight, side, selection) {
    if (!selection || selection === "all") {
        return true;
    }

    const [type, rawValue] = selection.split(":");
    const value = String(rawValue ?? "").toUpperCase();

    if (type === "country") {
        return String(
            flight[`${side}_country`] ?? ""
        ).toUpperCase() === value;
    }

    if (type === "airport") {
        const iata = String(
            flight[`${side}_iata`] ?? ""
        ).toUpperCase();

        const icao = String(
            flight[`${side}_icao`] ?? ""
        ).toUpperCase();

        return iata === value || icao === value;
    }

    return true;
}


function filterFlights() {
    const origin = elements.origin.value;
    const destination = elements.destination.value;
    const dateFrom = elements.dateFrom.value;
    const dateTo = elements.dateTo.value;

    const minimumSeats = parseInteger(
        elements.minimumSeats.value
    );

    const aircraft = elements.aircraft.value;
    const currency = elements.currency.value;

    const maximumPrice = parseNumber(
        elements.maximumPrice.value
    );

    state.filteredFlights = state.flights.filter(
        flight => {
            if (
                !matchesRouteSelection(
                    flight,
                    "origin",
                    origin
                )
            ) {
                return false;
            }

            if (
                !matchesRouteSelection(
                    flight,
                    "destination",
                    destination
                )
            ) {
                return false;
            }

            const departureDate = String(
                flight.departure_date_iso ?? ""
            );

            if (
                dateFrom
                && departureDate
                && departureDate < dateFrom
            ) {
                return false;
            }

            if (
                dateTo
                && departureDate
                && departureDate > dateTo
            ) {
                return false;
            }

            const seats = parseInteger(
                flight.seats_available
            );

            if (
                minimumSeats !== null
                && (
                    seats === null
                    || seats < minimumSeats
                )
            ) {
                return false;
            }

            if (
                aircraft !== "all"
                && normalize(flight.aircraft_type)
                    !== normalize(aircraft)
            ) {
                return false;
            }

            const flightCurrency = String(
                flight.price_currency ?? ""
            ).toUpperCase();

            if (
                currency !== "all"
                && flightCurrency !== currency
            ) {
                return false;
            }

            if (
                maximumPrice !== null
                && currency !== "all"
            ) {
                const amount = parseNumber(
                    flight.price_amount
                );

                if (
                    amount === null
                    || amount > maximumPrice
                ) {
                    return false;
                }
            }

            return true;
        }
    );

    sortFlights();
    renderFlights();
    updateTelegramLink();
}


function sortFlights() {
    const sortValue = elements.sort.value;

    const dateKey = flight => (
        `${flight.departure_date_iso ?? "9999-12-31"}`
        + `T${flight.departure_time || "23:59"}`
    );

    state.filteredFlights.sort((a, b) => {
        if (sortValue === "date-desc") {
            return dateKey(b).localeCompare(dateKey(a));
        }

        if (sortValue === "price-asc") {
            return (
                (parseNumber(a.price_amount) ?? Infinity)
                - (parseNumber(b.price_amount) ?? Infinity)
            );
        }

        if (sortValue === "price-desc") {
            return (
                (parseNumber(b.price_amount) ?? -Infinity)
                - (parseNumber(a.price_amount) ?? -Infinity)
            );
        }

        if (sortValue === "seats-desc") {
            return (
                (parseInteger(b.seats_available) ?? -1)
                - (parseInteger(a.seats_available) ?? -1)
            );
        }

        return dateKey(a).localeCompare(dateKey(b));
    });
}


function flightCardTemplate(flight) {
    const originCode = escapeHtml(
        airportCode(flight, "origin")
    );

    const destinationCode = escapeHtml(
        airportCode(flight, "destination")
    );

    const originCity = escapeHtml(
        flight.origin_city
        || flight.origin_airport_name
        || "Unknown origin"
    );

    const destinationCity = escapeHtml(
        flight.destination_city
        || flight.destination_airport_name
        || "Unknown destination"
    );

    const originCountry = escapeHtml(
        countryName(flight.origin_country)
    );

    const destinationCountry = escapeHtml(
        countryName(flight.destination_country)
    );

    const date = escapeHtml(
        flight.departure_date_raw
        || flight.departure_date_iso
        || "Not specified"
    );

    const departureTime = escapeHtml(
        flight.departure_time || "Not specified"
    );

    const arrivalTime = escapeHtml(
        flight.arrival_time || "Not specified"
    );

    const aircraft = escapeHtml(
        flight.aircraft_type || "Not specified"
    );

    const duration = escapeHtml(
        flight.flight_duration || "Not specified"
    );

    const seats = escapeHtml(
        flight.seats_available || "Not specified"
    );

    const price = escapeHtml(
        flight.price_raw || "Request price"
    );

    const originIcao = escapeHtml(
        flight.origin_icao || "Not specified"
    );

    const destinationIcao = escapeHtml(
        flight.destination_icao || "Not specified"
    );

    const bookingLink = safeExternalUrl(
        flight.booking_link
        || flight.tracking_link
        || flight.rss_link
    );

    const bookingButton = bookingLink
        ? `
            <a
                class="button button-primary"
                href="${escapeHtml(bookingLink)}"
                target="_blank"
                rel="sponsored noopener"
            >
                View and Book
            </a>
        `
        : `
            <span
                class="button button-secondary"
                aria-disabled="true"
            >
                Booking Link Unavailable
            </span>
        `;

    return `
        <article class="flight-card">
            <span class="flight-card-badge">
                Empty Leg
            </span>

            <div class="flight-route">
                <div class="flight-location">
                    <span class="flight-code">
                        ${originCode}
                    </span>

                    <span class="flight-city">
                        ${originCity}
                    </span>

                    <span class="flight-country">
                        ${originCountry}
                    </span>
                </div>

                <span
                    class="route-arrow"
                    aria-hidden="true"
                >
                    →
                </span>

                <div class="flight-location">
                    <span class="flight-code">
                        ${destinationCode}
                    </span>

                    <span class="flight-city">
                        ${destinationCity}
                    </span>

                    <span class="flight-country">
                        ${destinationCountry}
                    </span>
                </div>
            </div>

            <div class="flight-primary-details">
                <div class="detail-box">
                    <span>Departure</span>
                    <strong>${date}</strong>
                </div>

                <div class="detail-box">
                    <span>Time</span>
                    <strong>${departureTime}</strong>
                </div>

                <div class="detail-box">
                    <span>Aircraft</span>
                    <strong>${aircraft}</strong>
                </div>

                <div class="detail-box">
                    <span>Seats</span>
                    <strong>${seats}</strong>
                </div>
            </div>

            <div class="flight-price">
                <div>
                    <span class="flight-price-label">
                        Listed price
                    </span>

                    <strong class="flight-price-value">
                        ${price}
                    </strong>
                </div>
            </div>

            <details class="flight-details">
                <summary>
                    View full flight details
                </summary>

                <div class="extended-details">
                    <div class="extended-detail">
                        <span>Origin ICAO</span>
                        <strong>${originIcao}</strong>
                    </div>

                    <div class="extended-detail">
                        <span>Destination ICAO</span>
                        <strong>${destinationIcao}</strong>
                    </div>

                    <div class="extended-detail">
                        <span>Arrival</span>
                        <strong>${arrivalTime}</strong>
                    </div>

                    <div class="extended-detail">
                        <span>Estimated duration</span>
                        <strong>${duration}</strong>
                    </div>

                    <div class="extended-detail">
                        <span>Seats available</span>
                        <strong>${seats}</strong>
                    </div>
                </div>
            </details>

            <div class="flight-booking">
                ${bookingButton}

                <p class="flight-disclaimer">
                    Affiliate booking link. Details and
                    availability must be confirmed with Villiers.
                </p>
            </div>
        </article>
    `;
}


function renderFlights() {
    const flights = state.filteredFlights;

    elements.flightGrid.innerHTML = "";

    elements.emptyState.hidden = flights.length !== 0;
    elements.flightGrid.hidden = flights.length === 0;

    elements.resultsStatus.textContent = (
        `${flights.length} of ${state.flights.length} `
        + (
            flights.length === 1
                ? "flight matches"
                : "flights match"
        )
        + " your current filters."
    );

    if (!flights.length) {
        return;
    }

    elements.flightGrid.innerHTML = flights
        .map(flightCardTemplate)
        .join("");
}


function telegramSelectionPart(side, selection) {
    if (!selection || selection === "all") {
        return "";
    }

    const [type, rawValue] = selection.split(":");
    const value = String(rawValue ?? "")
        .replace(/[^A-Za-z0-9]/g, "")
        .toUpperCase();

    if (!value) {
        return "";
    }

    const sidePrefix = (
        side === "origin"
            ? "o"
            : "d"
    );

    if (type === "country") {
        return `${sidePrefix}-c${value}`;
    }

    if (type === "airport") {
        return `${sidePrefix}-a${value}`;
    }

    return "";
}


function updateTelegramLink() {
    const parts = [
        telegramSelectionPart(
            "origin",
            elements.origin.value
        ),

        telegramSelectionPart(
            "destination",
            elements.destination.value
        ),
    ].filter(Boolean);

    const payload = parts.length
        ? parts.join("_")
        : "all";

    elements.telegramLink.href = (
        `https://t.me/${TELEGRAM_BOT_USERNAME}`
        + `?start=${encodeURIComponent(payload)}`
    );
}


function clearFilters() {
    elements.origin.value = "all";
    elements.destination.value = "all";
    elements.dateFrom.value = "";
    elements.dateTo.value = "";
    elements.minimumSeats.value = "";
    elements.aircraft.value = "all";
    elements.currency.value = "all";
    elements.maximumPrice.value = "";
    elements.maximumPrice.disabled = true;
    elements.sort.value = "date-asc";

    filterFlights();
}


function bindEvents() {
    const filterElements = [
        elements.origin,
        elements.destination,
        elements.dateFrom,
        elements.dateTo,
        elements.minimumSeats,
        elements.aircraft,
        elements.currency,
        elements.maximumPrice,
        elements.sort,
    ];

    for (const element of filterElements) {
        element.addEventListener(
            "input",
            filterFlights
        );

        element.addEventListener(
            "change",
            filterFlights
        );
    }

    elements.currency.addEventListener(
        "change",
        () => {
            const hasCurrency = (
                elements.currency.value !== "all"
            );

            elements.maximumPrice.disabled = !hasCurrency;

            if (!hasCurrency) {
                elements.maximumPrice.value = "";
            }

            filterFlights();
        }
    );

    elements.clearFilters.addEventListener(
        "click",
        clearFilters
    );

    elements.emptyClearFilters.addEventListener(
        "click",
        clearFilters
    );

    elements.retryLoading.addEventListener(
        "click",
        loadFlights
    );
}


function updateStatistics() {
    const countries = new Set();

    for (const flight of state.flights) {
        if (flight.origin_country) {
            countries.add(
                String(flight.origin_country).toUpperCase()
            );
        }

        if (flight.destination_country) {
            countries.add(
                String(flight.destination_country).toUpperCase()
            );
        }
    }

    elements.heroFlightCount.textContent = (
        String(state.flights.length)
    );

    elements.heroCountryCount.textContent = (
        String(countries.size)
    );
}


function updateMetadata() {
    const generatedAt = (
        state.metadata.generated_at
        || state.metadata.updated_at
        || ""
    );

    if (!generatedAt) {
        elements.lastUpdated.textContent = (
            "Not provided"
        );
        return;
    }

    const date = new Date(generatedAt);

    if (Number.isNaN(date.getTime())) {
        elements.lastUpdated.textContent = (
            generatedAt
        );
        return;
    }

    elements.lastUpdated.textContent = (
        new Intl.DateTimeFormat(
            "en",
            {
                dateStyle: "medium",
                timeStyle: "short",
            }
        ).format(date)
    );
}


async function loadFlights() {
    elements.loadingState.hidden = false;
    elements.errorState.hidden = true;
    elements.emptyState.hidden = true;
    elements.flightGrid.hidden = true;

    try {
        const response = await fetch(
            `${FLIGHTS_DATA_URL}?v=${Date.now()}`,
            {
                cache: "no-store",
                credentials: "same-origin",
            }
        );

        if (!response.ok) {
            throw new Error(
                `Flight data request returned `
                + `${response.status}.`
            );
        }

        const payload = await response.json();

        const flights = Array.isArray(payload)
            ? payload
            : payload.flights;

        if (!Array.isArray(flights)) {
            throw new Error(
                "The flight data format is invalid."
            );
        }

        state.flights = flights.filter(
            flight => {
                const status = normalize(
                    flight.status || "active"
                );

                return !status || status === "active";
            }
        );

        state.metadata = Array.isArray(payload)
            ? {}
            : payload;

        createAirportOptions("origin");
        createAirportOptions("destination");
        createAircraftOptions();
        createCurrencyOptions();

        updateStatistics();
        updateMetadata();

        state.filteredFlights = [
            ...state.flights
        ];

        filterFlights();

        elements.loadingState.hidden = true;
        elements.errorState.hidden = true;

    } catch (error) {
        console.error(error);

        elements.loadingState.hidden = true;
        elements.flightGrid.hidden = true;
        elements.emptyState.hidden = true;
        elements.errorState.hidden = false;

        elements.errorMessage.textContent = (
            error instanceof Error
                ? error.message
                : "Please try again shortly."
        );

        elements.resultsStatus.textContent = (
            "Flight data could not be loaded."
        );
    }
}


function initialize() {
    elements.currentYear.textContent = (
        String(new Date().getFullYear())
    );

    bindEvents();
    updateTelegramLink();
    loadFlights();
}


initialize();
