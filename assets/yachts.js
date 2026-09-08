"use strict";

const YACHTS_DATA_URL = "data/yachts.json";

const state = {
    yachts: [],
    filteredYachts: [],
    metadata: {},
};

const elements = {
    country: document.querySelector("#country-filter"),
    type: document.querySelector("#type-filter"),
    minimumDiscount: document.querySelector("#minimum-discount"),
    sort: document.querySelector("#sort-filter"),

    clearFilters: document.querySelector("#clear-filters"),
    emptyClearFilters: document.querySelector("#empty-clear-filters"),

    yachtGrid: document.querySelector("#yacht-grid"),
    loadingState: document.querySelector("#loading-state"),
    errorState: document.querySelector("#error-state"),
    errorMessage: document.querySelector("#error-message"),
    emptyState: document.querySelector("#empty-state"),
    retryLoading: document.querySelector("#retry-loading"),

    resultsStatus: document.querySelector("#results-status"),
    lastUpdated: document.querySelector("#last-updated"),

    heroYachtCount: document.querySelector("#hero-yacht-count"),
    heroCountryCount: document.querySelector("#hero-country-count"),
    heroTopDiscount: document.querySelector("#hero-top-discount"),

    currentYear: document.querySelector("#current-year"),
};


function escapeHtml(value) {
    return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}


function parseNumber(value) {
    const normalized = String(value ?? "").replace(/[^\d.-]/g, "");
    const parsed = Number.parseFloat(normalized);
    return Number.isFinite(parsed) ? parsed : null;
}


function safeExternalUrl(value) {
    try {
        const url = new URL(String(value ?? ""));
        if (url.protocol === "https:" || url.protocol === "http:") {
            return url.href;
        }
    } catch {
        return "";
    }
    return "";
}


function createSelectOptions(select, values, allLabel) {
    const currentValue = select.value;

    select.innerHTML = "";

    const allOption = document.createElement("option");
    allOption.value = "all";
    allOption.textContent = allLabel;
    select.append(allOption);

    [...values]
        .sort((a, b) => a.localeCompare(b))
        .forEach(value => {
            const option = document.createElement("option");
            option.value = value;
            option.textContent = value;
            select.append(option);
        });

    if ([...select.options].some(option => option.value === currentValue)) {
        select.value = currentValue;
    }
}


function createFilterOptions() {
    const countries = new Set();
    const types = new Set();

    for (const yacht of state.yachts) {
        if (yacht.country) {
            countries.add(yacht.country);
        }
        if (yacht.type) {
            types.add(yacht.type);
        }
    }

    createSelectOptions(elements.country, countries, "All countries");
    createSelectOptions(elements.type, types, "All boat types");
}


function filterYachts() {
    const country = elements.country.value;
    const type = elements.type.value;
    const minimumDiscount = parseNumber(elements.minimumDiscount.value);

    state.filteredYachts = state.yachts.filter(yacht => {
        if (country !== "all" && yacht.country !== country) {
            return false;
        }

        if (type !== "all" && yacht.type !== type) {
            return false;
        }

        if (minimumDiscount !== null && yacht.discount_pct < minimumDiscount) {
            return false;
        }

        return true;
    });

    sortYachts();
    renderYachts();
}


function sortYachts() {
    const sortValue = elements.sort.value;

    state.filteredYachts.sort((a, b) => {
        if (sortValue === "price-asc") {
            return (a.total_price_amount ?? Infinity) - (b.total_price_amount ?? Infinity);
        }

        if (sortValue === "price-desc") {
            return (b.total_price_amount ?? -Infinity) - (a.total_price_amount ?? -Infinity);
        }

        return (b.discount_pct ?? 0) - (a.discount_pct ?? 0);
    });
}


function yachtCardTemplate(yacht) {
    const model = escapeHtml(yacht.model || "Yacht");
    const name = escapeHtml(yacht.name || "");
    const type = escapeHtml(yacht.type || "Not specified");
    const service = escapeHtml(yacht.service || "Not specified");
    const year = escapeHtml(yacht.year || "Not specified");
    const length = escapeHtml(yacht.length || "Not specified");
    const berths = escapeHtml(yacht.berths || "Not specified");
    const cabins = escapeHtml(yacht.cabins || "Not specified");
    const dateFrom = escapeHtml(yacht.date_from || "Not specified");
    const fromLocation = escapeHtml(yacht.from_location || "Not specified");
    const originalPrice = escapeHtml(yacht.original_price || "");
    const totalPrice = escapeHtml(yacht.total_price || "Request price");
    const discount = Math.round(yacht.discount_pct || 0);

    const routeTo = yacht.to_location
        ? `
            <span class="route-arrow" aria-hidden="true">→</span>
            <div class="flight-location">
                <span class="flight-city">${escapeHtml(yacht.to_location)}</span>
            </div>
        `
        : "";

    const bookingLink = safeExternalUrl(yacht.booking_link);

    const bookingButton = bookingLink
        ? `
            <a class="button button-primary" href="${escapeHtml(bookingLink)}" target="_blank" rel="sponsored noopener">
                View on SkipperCity
            </a>
        `
        : `
            <span class="button button-secondary" aria-disabled="true">
                Booking Link Unavailable
            </span>
        `;

    return `
        <article class="flight-card">
            <span class="flight-card-badge yacht-discount-badge">
                -${discount}%
            </span>

            <div class="flight-route">
                <div class="flight-location">
                    <span class="flight-city">${model}${name ? " • " + name : ""}</span>
                </div>
            </div>

            <div class="flight-route">
                <div class="flight-location">
                    <span class="flight-city">${fromLocation}</span>
                </div>
                ${routeTo}
            </div>

            <div class="flight-primary-details">
                <div class="detail-box">
                    <span>Type</span>
                    <strong>${type}</strong>
                </div>

                <div class="detail-box">
                    <span>Service</span>
                    <strong>${service}</strong>
                </div>

                <div class="detail-box">
                    <span>Berths</span>
                    <strong>${berths}</strong>
                </div>

                <div class="detail-box">
                    <span>Cabins</span>
                    <strong>${cabins}</strong>
                </div>
            </div>

            <div class="flight-price">
                <div>
                    <span class="flight-price-label">
                        ${dateFrom}
                    </span>

                    ${originalPrice ? `<span class="yacht-original-price">${originalPrice}</span>` : ""}

                    <strong class="flight-price-value">
                        ${totalPrice}
                    </strong>
                </div>
            </div>

            <details class="flight-details">
                <summary>View full details</summary>

                <div class="extended-details">
                    <div class="extended-detail">
                        <span>Year</span>
                        <strong>${year}</strong>
                    </div>

                    <div class="extended-detail">
                        <span>Length</span>
                        <strong>${length}</strong>
                    </div>
                </div>
            </details>

            <div class="flight-booking">
                ${bookingButton}

                <p class="flight-disclaimer">
                    Affiliate booking link. Availability and final
                    price must be confirmed with SkipperCity.
                </p>
            </div>
        </article>
    `;
}


function renderYachts() {
    const yachts = state.filteredYachts;

    elements.yachtGrid.innerHTML = "";
    elements.emptyState.hidden = yachts.length !== 0;
    elements.yachtGrid.hidden = yachts.length === 0;

    elements.resultsStatus.textContent = (
        `${yachts.length} of ${state.yachts.length} `
        + (yachts.length === 1 ? "yacht matches" : "yachts match")
        + " your current filters."
    );

    if (!yachts.length) {
        return;
    }

    elements.yachtGrid.innerHTML = yachts.map(yachtCardTemplate).join("");
}


function clearFilters() {
    elements.country.value = "all";
    elements.type.value = "all";
    elements.minimumDiscount.value = "";
    elements.sort.value = "discount-desc";

    filterYachts();
}


function bindEvents() {
    const filterElements = [
        elements.country,
        elements.type,
        elements.minimumDiscount,
        elements.sort,
    ];

    for (const element of filterElements) {
        element.addEventListener("input", filterYachts);
        element.addEventListener("change", filterYachts);
    }

    elements.clearFilters.addEventListener("click", clearFilters);
    elements.emptyClearFilters.addEventListener("click", clearFilters);
    elements.retryLoading.addEventListener("click", loadYachts);
}


function updateStatistics() {
    const countries = new Set(
        state.yachts.map(yacht => yacht.country).filter(Boolean)
    );

    const topDiscount = state.yachts.reduce(
        (max, yacht) => Math.max(max, yacht.discount_pct || 0),
        0
    );

    elements.heroYachtCount.textContent = String(state.yachts.length);
    elements.heroCountryCount.textContent = String(countries.size);
    elements.heroTopDiscount.textContent = `${Math.round(topDiscount)}%`;
}


function updateMetadata() {
    const generatedAt = state.metadata.generated_at || "";

    if (!generatedAt) {
        elements.lastUpdated.textContent = "Not provided";
        return;
    }

    const date = new Date(generatedAt);

    if (Number.isNaN(date.getTime())) {
        elements.lastUpdated.textContent = generatedAt;
        return;
    }

    elements.lastUpdated.textContent = new Intl.DateTimeFormat(
        "en",
        { dateStyle: "medium", timeStyle: "short" }
    ).format(date);
}


async function loadYachts() {
    elements.loadingState.hidden = false;
    elements.errorState.hidden = true;
    elements.emptyState.hidden = true;
    elements.yachtGrid.hidden = true;

    try {
        const response = await fetch(
            `${YACHTS_DATA_URL}?v=${Date.now()}`,
            { cache: "no-store", credentials: "same-origin" }
        );

        if (!response.ok) {
            throw new Error(`Yacht data request returned ${response.status}.`);
        }

        const payload = await response.json();
        const yachts = Array.isArray(payload) ? payload : payload.yachts;

        if (!Array.isArray(yachts)) {
            throw new Error("The yacht data format is invalid.");
        }

        state.yachts = yachts;
        state.metadata = Array.isArray(payload) ? {} : payload;

        createFilterOptions();
        updateStatistics();
        updateMetadata();

        state.filteredYachts = [...state.yachts];
        filterYachts();

        elements.loadingState.hidden = true;
        elements.errorState.hidden = true;

    } catch (error) {
        console.error(error);

        elements.loadingState.hidden = true;
        elements.yachtGrid.hidden = true;
        elements.emptyState.hidden = true;
        elements.errorState.hidden = false;

        elements.errorMessage.textContent = (
            error instanceof Error ? error.message : "Please try again shortly."
        );

        elements.resultsStatus.textContent = "Yacht data could not be loaded.";
    }
}


function initialize() {
    elements.currentYear.textContent = String(new Date().getFullYear());

    bindEvents();
    loadYachts();
}


initialize();
