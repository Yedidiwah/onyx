"use strict";

const AIRPORTS_URL = "../data/airports.json";
const MAX_RESULTS = 18;

const telegram = (
    window.Telegram
    && window.Telegram.WebApp
);

const state = {
    airports: [],
    countries: [],
    telegramAvailable: false,
    loading: true,
    sending: false,

    route: {
        origin: {
            mode: "all",
            preference: "Not set",
            label: "All origins",
            valid: true,
        },

        destination: {
            mode: "all",
            preference: "Not set",
            label: "All destinations",
            valid: true,
        },
    },
};

const controls = {
    status: document.querySelector(
        "#status"
    ),

    saveButton: document.querySelector(
        "#save-button"
    ),

    externalNotice: document.querySelector(
        "#external-notice"
    ),

    summaryOrigin: document.querySelector(
        "#summary-origin"
    ),

    summaryDestination: document.querySelector(
        "#summary-destination"
    ),

    summaryDescription: document.querySelector(
        "#summary-description"
    ),

    frequency: document.querySelector(
        "#update-frequency"

    origin: {
        mode: document.querySelector(
            "#origin-mode"
        ),

        countryPanel: document.querySelector(
            "#origin-country-panel"
        ),

        country: document.querySelector(
            "#origin-country"
        ),

        airportPanel: document.querySelector(
            "#origin-airport-panel"
        ),

        search: document.querySelector(
            "#origin-airport-search"
        ),

        results: document.querySelector(
            "#origin-airport-results"
        ),

        selected: document.querySelector(
            "#origin-selected-airport"
        ),
    },

    destination: {
        mode: document.querySelector(
            "#destination-mode"
        ),

        countryPanel: document.querySelector(
            "#destination-country-panel"
        ),

        country: document.querySelector(
            "#destination-country"
        ),

        airportPanel: document.querySelector(
            "#destination-airport-panel"
        ),

        search: document.querySelector(
            "#destination-airport-search"
        ),

        results: document.querySelector(
            "#destination-airport-results"
        ),

        selected: document.querySelector(
            "#destination-selected-airport"
        ),
    },
};


function clean(value) {
    return String(value ?? "").trim();
}


function normalize(value) {
    return clean(value)
        .normalize("NFKD")
        .replace(
            /[\u0300-\u036f]/g,
            ""
        )
        .toLocaleLowerCase("en")
        .replace(
            /[^a-z0-9]+/g,
            " "
        )
        .trim();
}


function setStatus(message, type = "") {
    controls.status.textContent = message;
    controls.status.dataset.type = type;
}


function initializeTelegram() {
    if (!telegram) {
        state.telegramAvailable = false;
        controls.externalNotice.hidden = false;
        return;
    }

    try {
        telegram.ready();
        telegram.expand();

        telegram.setHeaderColor(
            "#070809"
        );

        telegram.setBackgroundColor(
            "#070809"
        );

        state.telegramAvailable = Boolean(
            telegram.initData
        );

        controls.externalNotice.hidden = (
            state.telegramAvailable
        );

    } catch (error) {
        console.error(error);

        state.telegramAvailable = false;
        controls.externalNotice.hidden = false;
    }
}


function airportCode(airport) {
    return (
        clean(airport.iata).toUpperCase()
        || clean(airport.icao).toUpperCase()
    );
}


function airportLabel(airport) {
    const location = (
        clean(airport.city)
        || clean(airport.name)
        || "Unknown airport"
    );

    const country = (
        clean(airport.country_name)
        || clean(airport.country_code)
    );

    const codes = [
        ...new Set(
            [
                clean(airport.iata).toUpperCase(),
                clean(airport.icao).toUpperCase(),
            ].filter(Boolean)
        ),
    ];

    const locationWithCountry = country
        ? `${location}, ${country}`
        : location;

    return codes.length
        ? (
            `${locationWithCountry} `
            + `(${codes.join(" / ")})`
        )
        : locationWithCountry;
}


function airportPreference(airport) {
    const location = (
        clean(airport.city)
        || clean(airport.name)
        || "Unknown airport"
    );

    const country = (
        clean(airport.country_name)
        || clean(airport.country_code)
    );

    const code = airportCode(
        airport
    );

    const locationWithCountry = country
        ? `${location}, ${country}`
        : location;

    return code
        ? `${locationWithCountry} (${code})`
        : locationWithCountry;
}


function prepareAirports(airports) {
    return airports.map(
        airport => {
            const prepared = {
                ...airport,
            };

            prepared._code = airportCode(
                airport
            );

            prepared._label = airportLabel(
                airport
            );

            prepared._preference = (
                airportPreference(
                    airport
                )
            );

            prepared._search = normalize(
                [
                    airport.iata,
                    airport.icao,
                    airport.name,
                    airport.city,
                    airport.country_code,
                    airport.country_name,
                ].join(" ")
            );

            return prepared;
        }
    );
}


function populateCountries(side) {
    const select = controls[side].country;

    select.innerHTML = "";

    const placeholder = (
        document.createElement("option")
    );

    placeholder.value = "";
    placeholder.textContent = (
        "Select a country"
    );

    select.append(
        placeholder
    );

    for (const country of state.countries) {
        const option = (
            document.createElement("option")
        );

        option.value = clean(
            country.code
        ).toUpperCase();

        option.textContent = clean(
            country.name
        );

        select.append(
            option
        );
    }
}


function setRouteAll(side) {
    state.route[side] = {
        mode: "all",
        preference: "Not set",
        label: (
            side === "origin"
                ? "All origins"
                : "All destinations"
        ),
        valid: true,
    };
}


function setRouteCountry(
    side,
    countryCode,
    countryName
) {
    if (!countryCode || !countryName) {
        state.route[side] = {
            mode: "country",
            preference: "",
            label: "Country not selected",
            valid: false,
        };

        return;
    }

    state.route[side] = {
        mode: "country",
        preference: (
            `Anywhere in ${countryName}`
        ),
        label: (
            `Anywhere in ${countryName}`
        ),
        valid: true,
    };
}


function setRouteAirport(
    side,
    airport
) {
    if (!airport) {
        state.route[side] = {
            mode: "airport",
            preference: "",
            label: "Airport not selected",
            valid: false,
        };

        return;
    }

    state.route[side] = {
        mode: "airport",
        preference: airport._preference,
        label: airport._label,
        valid: true,
    };
}


function hideResults(side) {
    const results = controls[side].results;

    results.hidden = true;

    controls[side].search.setAttribute(
        "aria-expanded",
        "false"
    );
}


function showResults(side) {
    controls[side].results.hidden = false;

    controls[side].search.setAttribute(
        "aria-expanded",
        "true"
    );
}


function scoreAirport(
    airport,
    normalizedQuery
) {
    const iata = normalize(
        airport.iata
    );

    const icao = normalize(
        airport.icao
    );

    const city = normalize(
        airport.city
    );

    const name = normalize(
        airport.name
    );

    if (
        iata === normalizedQuery
        || icao === normalizedQuery
    ) {
        return 0;
    }

    if (
        iata.startsWith(normalizedQuery)
        || icao.startsWith(normalizedQuery)
    ) {
        return 1;
    }

    if (city === normalizedQuery) {
        return 2;
    }

    if (city.startsWith(normalizedQuery)) {
        return 3;
    }

    if (name.startsWith(normalizedQuery)) {
        return 4;
    }

    return 5;
}


function findAirports(query) {
    const normalizedQuery = normalize(
        query
    );

    if (normalizedQuery.length < 2) {
        return [];
    }

    return state.airports
        .filter(
            airport => (
                airport._search.includes(
                    normalizedQuery
                )
            )
        )
        .sort(
            (a, b) => {
                const scoreDifference = (
                    scoreAirport(
                        a,
                        normalizedQuery
                    )
                    - scoreAirport(
                        b,
                        normalizedQuery
                    )
                );

                if (scoreDifference !== 0) {
                    return scoreDifference;
                }

                return a._label.localeCompare(
                    b._label
                );
            }
        )
        .slice(
            0,
            MAX_RESULTS
        );
}


function renderAirportResults(
    side,
    query
) {
    const resultsElement = (
        controls[side].results
    );

    resultsElement.innerHTML = "";

    const normalizedQuery = normalize(
        query
    );

    if (normalizedQuery.length < 2) {
        hideResults(side);
        return;
    }

    const matches = findAirports(
        query
    );

    if (!matches.length) {
        const message = (
            document.createElement("div")
        );

        message.className = (
            "no-results"
        );

        message.textContent = (
            "No matching airport was found."
        );

        resultsElement.append(
            message
        );

        showResults(side);
        return;
    }

    for (const airport of matches) {
        const button = (
            document.createElement("button")
        );

        button.type = "button";
        button.className = "airport-result";
        button.setAttribute(
            "role",
            "option"
        );

        const title = (
            document.createElement("strong")
        );

        title.textContent = airport._label;

        const subtitle = (
            document.createElement("span")
        );

        subtitle.textContent = clean(
            airport.name
        );

        button.append(
            title,
            subtitle
        );

        button.addEventListener(
            "click",
            () => {
                selectAirport(
                    side,
                    airport
                );
            }
        );

        resultsElement.append(
            button
        );
    }

    showResults(side);
}


function selectAirport(
    side,
    airport
) {
    const sideControls = controls[side];

    setRouteAirport(
        side,
        airport
    );

    sideControls.search.value = (
        airport._label
    );

    sideControls.selected.textContent = (
        `Selected: ${airport._label}`
    );

    sideControls.selected.hidden = false;

    hideResults(side);
    updateSummary();
}


function handleModeChange(side) {
    const sideControls = controls[side];
    const mode = sideControls.mode.value;

    sideControls.countryPanel.hidden = (
        mode !== "country"
    );

    sideControls.airportPanel.hidden = (
        mode !== "airport"
    );

    hideResults(side);

    if (mode === "all") {
        setRouteAll(side);
    }

    if (mode === "country") {
        sideControls.country.value = "";

        setRouteCountry(
            side,
            "",
            ""
        );
    }

    if (mode === "airport") {
        sideControls.search.value = "";
        sideControls.selected.hidden = true;

        setRouteAirport(
            side,
            null
        );
    }

    updateSummary();
}


function handleCountryChange(side) {
    const select = controls[side].country;

    const option = (
        select.options[
            select.selectedIndex
        ]
    );

    const code = clean(
        select.value
    );

    const name = (
        option
        ? clean(option.textContent)
        : ""
    );

    setRouteCountry(
        side,
        code,
        name
    );

    updateSummary();
}


function handleAirportInput(side) {
    const query = controls[side].search.value;

    setRouteAirport(
        side,
        null
    );

    controls[side].selected.hidden = true;

    renderAirportResults(
        side,
        query
    );

    updateSummary();
}


function updateSummary() {
    const origin = state.route.origin;
    const destination = (
        state.route.destination
    );

    controls.summaryOrigin.textContent = (
        origin.label
    );

    controls.summaryDestination.textContent = (
        destination.label
    );

    if (
        origin.mode === "all"
        && destination.mode === "all"
    ) {
        controls.summaryDescription.textContent = (
            "You will receive all current "
            + "Empty Leg opportunities."
        );

    } else if (origin.mode === "all") {
        controls.summaryDescription.textContent = (
            "You will receive Empty Leg "
            + "opportunities to the selected "
            + "destination."
        );

    } else if (destination.mode === "all") {
        controls.summaryDescription.textContent = (
            "You will receive Empty Leg "
            + "opportunities from the selected "
            + "origin."
        );

    } else {
        controls.summaryDescription.textContent = (
            "You will receive Empty Leg "
            + "opportunities matching this route."
        );
    }

    updateSaveButton();
}


function updateSaveButton() {
    const routeValid = (
        state.route.origin.valid
        && state.route.destination.valid
    );

    controls.saveButton.disabled = (
        state.loading
        || state.sending
        || !routeValid
    );
}


function savePreferences() {
    if (
        state.sending
        || state.loading
    ) {
        return;
    }

    if (
        !state.route.origin.valid
        || !state.route.destination.valid
    ) {
        setStatus(
            "Complete both route selections.",
            "error"
        );

        return;
    }

    if (!state.telegramAvailable) {
        controls.externalNotice.hidden = false;

        setStatus(
            "Open this page through the "
            + "ONYX Radar Telegram bot.",
            "error"
        );

        return;
    }

    const payload = {
        origin: state.route.origin.preference,
        destination: (
            state.route.destination.preference
        ),
	frequency_hours: parseInt(controls.frequency.value, 10) || 1,
    };

    state.sending = true;
    updateSaveButton();

    setStatus(
        "Sending your preferences…"
    );

    try {
        telegram.sendData(
            JSON.stringify(payload)
        );

        setStatus(
            "Preferences sent successfully.",
            "success"
        );

        window.setTimeout(
            () => {
                try {
                    telegram.close();
                } catch {
                    // Nothing else is required.
                }
            },
            700
        );

    } catch (error) {
        console.error(error);

        state.sending = false;
        updateSaveButton();

        setStatus(
            "Preferences could not be sent.",
            "error"
        );
    }
}


async function loadAirportCatalogue() {
    state.loading = true;
    updateSaveButton();

    try {
        const response = await fetch(
            `${AIRPORTS_URL}?v=${Date.now()}`,
            {
                cache: "no-store",
                credentials: "same-origin",
            }
        );

        if (!response.ok) {
            throw new Error(
                `Airport request returned `
                + `${response.status}.`
            );
        }

        const payload = await response.json();

        if (
            !Array.isArray(payload.airports)
            || !Array.isArray(payload.countries)
        ) {
            throw new Error(
                "Invalid airport data format."
            );
        }

        state.airports = prepareAirports(
            payload.airports
        );

        state.countries = (
            payload.countries
        );

        populateCountries("origin");
        populateCountries("destination");

        controls.origin.mode.disabled = false;
        controls.destination.mode.disabled = false;

        state.loading = false;

        setStatus(
            `${state.airports.length} airports `
            + `in ${state.countries.length} `
            + "countries are available.",
            "success"
        );

        updateSummary();

    } catch (error) {
        console.error(error);

        state.loading = true;

        setStatus(
            "The global airport catalogue "
            + "could not be loaded.",
            "error"
        );
    }
}


function bindEvents() {
    for (
        const side
        of ["origin", "destination"]
    ) {
        controls[side].mode.addEventListener(
            "change",
            () => handleModeChange(side)
        );

        controls[side].country.addEventListener(
            "change",
            () => handleCountryChange(side)
        );

        controls[side].search.addEventListener(
            "input",
            () => handleAirportInput(side)
        );

        controls[side].search.addEventListener(
            "keydown",
            event => {
                if (event.key === "Escape") {
                    hideResults(side);
                }
            }
        );
    }

    controls.saveButton.addEventListener(
        "click",
        savePreferences
    );

    document.addEventListener(
        "click",
        event => {
            for (
                const side
                of ["origin", "destination"]
            ) {
                const panel = (
                    controls[side].airportPanel
                );

                if (
                    !panel.contains(
                        event.target
                    )
                ) {
                    hideResults(side);
                }
            }
        }
    );
}


function initialize() {
    initializeTelegram();
    bindEvents();
    updateSummary();
    loadAirportCatalogue();
}


initialize();
