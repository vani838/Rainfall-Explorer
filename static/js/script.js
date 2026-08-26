const BACKEND_URL = "https://computing-wielder-flattery.ngrok-free.dev";

// =====================================================
// RAINFALL EXPLORER v2
// script.js - PART 1
// =====================================================

// -------------------------------
// GLOBAL VARIABLES
// -------------------------------

let map = null;
let marker = null;
let chart = null;
let heatLayer = null;

// -------------------------------
// LOADER
// -------------------------------

function showLoader() {

    const loader = document.getElementById("loader");

    if (loader) {

        loader.style.display = "flex";

    }

}

function hideLoader() {

    const loader = document.getElementById("loader");

    if (loader) {

        loader.style.display = "none";

    }

}

// -------------------------------
// INITIALIZE MAP
// -------------------------------

function initMap() {

    map = L.map("map").setView([22.9734, 78.6569], 5);

    L.tileLayer(

        "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",

        {

            attribution: "&copy; OpenStreetMap"

        }

    ).addTo(map);

    setTimeout(() => {

        map.invalidateSize();

    }, 300);

    map.on("click", async function (e) {

        const lat = Number(e.latlng.lat.toFixed(4));
        const lon = Number(e.latlng.lng.toFixed(4));

        document.getElementById("latitude").value = lat;
        document.getElementById("longitude").value = lon;

        if (marker) {

            map.removeLayer(marker);

        }

        marker = L.marker([lat, lon]).addTo(map);

        try {

            const response = await fetch(

                `https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lon}`

            );

            const place = await response.json();

            let location = "Unknown";

            if (place.address) {

                location =
                    place.address.city ||
                    place.address.town ||
                    place.address.village ||
                    place.address.state ||
                    place.display_name;

            }

            document.getElementById("location").value = location;
            document.getElementById("showLocation").innerHTML = location;

        }

        catch (err) {

            console.log(err);

            document.getElementById("location").value = "Unknown";
            document.getElementById("showLocation").innerHTML = "Unknown";

        }

    });

}

// =====================================================
// script.js - PART 2
// SEARCH TYPE + API CALL
// =====================================================

// ---------------------------------
// SEARCH TYPE
// ---------------------------------

function updateSearchType() {

    const type = document.getElementById("searchType").value;

    document.getElementById("dateBox").style.display = "none";
    document.getElementById("monthBox").style.display = "none";
    document.getElementById("yearBox").style.display = "none";
    document.getElementById("dateRangeBox").style.display = "none";
    document.getElementById("yearRangeBox").style.display = "none";

    switch (type) {

        case "date":
            document.getElementById("dateBox").style.display = "block";
            break;

        case "month":
            document.getElementById("monthBox").style.display = "block";
            break;

        case "year":
            document.getElementById("yearBox").style.display = "block";
            break;

        case "dateRange":
            document.getElementById("dateRangeBox").style.display = "block";
            break;

        case "yearRange":
            document.getElementById("yearRangeBox").style.display = "block";
            break;

    }

}

// ---------------------------------
// SEARCH API
// ---------------------------------

async function searchRainfall() {

    const lat = document.getElementById("latitude").value.trim();
    const lon = document.getElementById("longitude").value.trim();

    if (!lat || !lon) {

        alert("Please select a location from the map.");

        return;

    }

    const body = {

        lat: Number(lat),

        lon: Number(lon),

        searchType: document.getElementById("searchType").value,

        date: document.getElementById("date").value,

        month: document.getElementById("month").value,

        year: document.getElementById("year").value,

        fromDate: document.getElementById("fromDate").value,

        toDate: document.getElementById("toDate").value,

        startYear: document.getElementById("startYear").value,

        endYear: document.getElementById("endYear").value

    };

    showLoader();

    try {

        const response = await fetch(BACKEND_URL + "/get_rainfall", {

            method: "POST",

            headers: {

                "Content-Type": "application/json"

            },

            body: JSON.stringify(body)

        });

        const result = await response.json();

        hideLoader();

        if (result.status !== "success") {

            alert(result.message);

            return;

        }

        // ============================
// DATA SOURCE BADGE
// ============================

const sourceBadge = document.getElementById("dataSourceBadge");

if (sourceBadge) {

    if (result.data_type === "forecast") {

        sourceBadge.innerHTML =
            "🔮 Forecast Data • Open-Meteo";

    } else if (result.data_type === "historical") {

        sourceBadge.innerHTML =
            "📊 Historical Data • IMD (1901–2024)";

    } else {

        sourceBadge.innerHTML =
            "🟢 Current Data • Open-Meteo";
    }
}

        // Update Summary

        updateSummary(result);

        // Next Parts

        updateChart(result);

        changeWeather(result.average);

        createHeatmap([
            [
                result.latitude,
                result.longitude,
                result.average / 100
            ]
        ]);

    }

    catch (err) {

        hideLoader();

        console.error(err);

        alert("Unable to connect to Flask server.");

    }

}

// =====================================================
// script.js - PART 3
// CHART.JS
// =====================================================

// ---------------------------------
// UPDATE CHART
// ---------------------------------

function updateChart(data) {

    const ctx = document
        .getElementById("rainChart")
        .getContext("2d");

    // Destroy previous chart

    if (chart) {

        chart.destroy();

    }

    chart = new Chart(ctx, {

        type: "bar",

        data: {

            labels: [

                "Average",
                "Maximum",
                "Minimum"

            ],

            datasets: [

                {

                    label: "Rainfall (mm)",

                    data: [

                        Number(data.average),

                        Number(data.maximum),

                        Number(data.minimum)

                    ],

                    backgroundColor: [

                        "rgba(33,150,243,0.8)",

                        "rgba(76,175,80,0.8)",

                        "rgba(255,193,7,0.8)"

                    ],

                    borderColor: [

                        "#2196F3",

                        "#4CAF50",

                        "#FFC107"

                    ],

                    borderWidth: 2,

                    borderRadius: 10

                }

            ]

        },

        options: {

            responsive: true,

            maintainAspectRatio: false,

            plugins: {

                legend: {

                    display: false

                },

                title: {

                    display: true,

                    text: "Rainfall Statistics"

                }

            },

            scales: {

                y: {

                    beginAtZero: true,

                    title: {

                        display: true,

                        text: "Millimeters"

                    }

                }

            }

        }

    });

}

// ---------------------------------
// UPDATE SUMMARY
// ---------------------------------

function updateSummary(result){

    document.getElementById("avgRain").textContent =
        result.average + " mm";

    document.getElementById("maxRain").textContent =
        result.maximum + " mm";

    document.getElementById("minRain").textContent =
        result.minimum + " mm";

    document.getElementById("rainCategory").textContent =
        result.category;

}


// =====================================================
// script.js - PART 4
// WEATHER EFFECTS
// =====================================================

// ---------------------------------
// CHANGE WEATHER
// ---------------------------------

function changeWeather(rainfall) {
rainfall = Number(rainfall) || 0;

    const sunny = document.getElementById("sunnyVideo");
    const rain = document.getElementById("rainVideo");
    const storm = document.getElementById("stormVideo");

    const rainLayer = document.getElementById("rain");
    const lightning = document.getElementById("lightning");

    // Hide all videos
    sunny.style.display = "none";
    rain.style.display = "none";
    storm.style.display = "none";

    sunny.pause();
    rain.pause();
    storm.pause();

    rainLayer.style.display = "none";

    // --------------------------
    // SUNNY
    // --------------------------

    if (rainfall < 2) {

        sunny.style.display = "block";

        sunny.currentTime = 0;

        sunny.play().catch(() => {});

    }

    // --------------------------
    // RAIN
    // --------------------------

    else if (rainfall < 20) {

        rain.style.display = "block";

        rain.currentTime = 0;

        rain.play().catch(() => {});

        rainLayer.style.display = "block";

    }

    // --------------------------
    // STORM
    // --------------------------

    else {

        storm.style.display = "block";

        storm.currentTime = 0;

        storm.play().catch(() => {});

        rainLayer.style.display = "block";

        lightning.classList.add("flash");

        setTimeout(() => {

            lightning.classList.remove("flash");

        }, 400);

    }

}

// ---------------------------------
// CREATE RAIN EFFECT
// ---------------------------------

function createRain() {

    const rain = document.getElementById("rain");

    rain.innerHTML = "";

    for (let i = 0; i < 180; i++) {

        const drop = document.createElement("div");

        drop.className = "drop";

        drop.style.left = Math.random() * 100 + "vw";

        drop.style.animationDuration =
            (0.45 + Math.random() * 0.6) + "s";

        drop.style.animationDelay =
            Math.random() * 2 + "s";

        rain.appendChild(drop);

    }

}

// =====================================================
// script.js - PART 5
// HEATMAP + CSV + PDF + RESET
// =====================================================

// ---------------------------------
// HEATMAP
// ---------------------------------

function createHeatmap(points) {

    if (!map) return;

    if (heatLayer) {

        map.removeLayer(heatLayer);

    }

    heatLayer = L.heatLayer(points, {

        radius: 35,
        blur: 25,
        maxZoom: 8,
        max: 1.0

    }).addTo(map);

}

// ---------------------------------
// CSV DOWNLOAD
// ---------------------------------

function downloadCSV() {

    const avg = document.getElementById("avgRain").textContent;
    const max = document.getElementById("maxRain").textContent;
    const min = document.getElementById("minRain").textContent;
    const category = document.getElementById("rainCategory").textContent;
    const location = document.getElementById("showLocation").textContent;

    const csv =

`Location,Average,Maximum,Minimum,Category
${location},${avg},${max},${min},${category}`;

    const blob = new Blob([csv], {

        type: "text/csv"

    });

    const link = document.createElement("a");

    link.href = URL.createObjectURL(blob);

    link.download = "Rainfall_Report.csv";

    link.click();

}

// ---------------------------------
// PDF DOWNLOAD
// ---------------------------------

function downloadPDF() {

    const { jsPDF } = window.jspdf;

    const pdf = new jsPDF();

    pdf.setFontSize(18);

    pdf.text("Rainfall Explorer Report", 20, 20);

    pdf.setFontSize(12);

    pdf.text(
        "Location : " +
        document.getElementById("showLocation").textContent,
        20,
        40
    );

    pdf.text(
        "Average : " +
        document.getElementById("avgRain").textContent,
        20,
        55
    );

    pdf.text(
        "Maximum : " +
        document.getElementById("maxRain").textContent,
        20,
        70
    );

    pdf.text(
        "Minimum : " +
        document.getElementById("minRain").textContent,
        20,
        85
    );

    pdf.text(
        "Category : " +
        document.getElementById("rainCategory").textContent,
        20,
        100
    );

    pdf.save("Rainfall_Report.pdf");

}

// ---------------------------------
// RESET
// ---------------------------------

function resetDashboard() {

    document.getElementById("latitude").value = "";
    document.getElementById("longitude").value = "";
    document.getElementById("location").value = "";

    document.getElementById("showLocation").textContent =
        "Select a Location";

    document.getElementById("avgRain").textContent = "--";
    document.getElementById("maxRain").textContent = "--";
    document.getElementById("minRain").textContent = "--";

    document.getElementById("rainCategory").textContent =
        "Waiting for Search...";

    if (marker) {

        map.removeLayer(marker);

        marker = null;

    }

    if (heatLayer) {

        map.removeLayer(heatLayer);

        heatLayer = null;

    }

    if (chart) {

        chart.destroy();

        chart = null;

    }

    changeWeather(0);

}

// =====================================================
// script.js - PART 6
// INITIALIZATION + EVENT LISTENERS
// =====================================================

// ---------------------------------
// EVENTS
// ---------------------------------

document.addEventListener("DOMContentLoaded", function () {

    // Initialize Map
    initMap();

    // Create Rain Animation
    createRain();

    // Default Weather
    changeWeather(0);

    // Default Search Type
    updateSearchType();

    // Search Type Change
    document
        .getElementById("searchType")
        .addEventListener("change", updateSearchType);

    // Search Button
    document
        .getElementById("searchBtn")
        .addEventListener("click", searchRainfall);

    // Reset Button
    document
        .getElementById("resetBtn")
        .addEventListener("click", resetDashboard);

    // CSV Button
    document
        .getElementById("downloadCSV")
        .addEventListener("click", downloadCSV);

    // PDF Button
    document
        .getElementById("downloadPDF")
        .addEventListener("click", downloadPDF);

});

// ---------------------------------
// OPTIONAL: PRESS ENTER TO SEARCH
// ---------------------------------

document.addEventListener("keypress", function (e) {

    if (e.key === "Enter") {

        const active = document.activeElement;

        if (
            active.id === "latitude" ||
            active.id === "longitude" ||
            active.id === "date" ||
            active.id === "month" ||
            active.id === "year" ||
            active.id === "fromDate" ||
            active.id === "toDate" ||
            active.id === "startYear" ||
            active.id === "endYear"
        ) {

            searchRainfall();

        }

    }

});
function downloadExcel() {

    let startDate = "";
    let endDate = "";

    // Date Range
    if (document.getElementById("dateRangeBox").style.display !== "none") {

        startDate = document.getElementById("fromDate").value;
        endDate = document.getElementById("toDate").value;
    }

    // Year Range
    else if (document.getElementById("yearRangeBox").style.display !== "none") {

        const startYear = document.getElementById("startYear").value;
        const endYear = document.getElementById("endYear").value;

        startDate = `${startYear}-01-01`;
        endDate = `${endYear}-12-31`;
    }

    // Single Date
    else {

        startDate = document.getElementById("date").value;
        endDate = startDate;
    }

    console.log("Latitude:", document.getElementById("latitude").value);
    console.log("Longitude:", document.getElementById("longitude").value);
    console.log("Start Date:", startDate);
    console.log("End Date:", endDate);

    fetch(BACKEND_URL + "/download_excel", {

        method: "POST",

        headers: {
            "Content-Type": "application/json"
        },

        body: JSON.stringify({

            latitude: document.getElementById("latitude").value,
            longitude: document.getElementById("longitude").value,
            start_date: startDate,
            end_date: endDate

        })

    })

    .then(async (response) => {

        if (!response.ok) {
            throw new Error(await response.text());
        }

        return {
            blob: await response.blob(),
            headers: response.headers
        };

    })

    .then(({ blob, headers }) => {

        const url = window.URL.createObjectURL(blob);

        const a = document.createElement("a");

        let filename = "Rainfall_Report.xlsx";

        const disposition = headers.get("Content-Disposition");

        if (disposition && disposition.includes("filename=")) {

            filename = disposition
                .split("filename=")[1]
                .replace(/"/g, "");
        }

        a.href = url;
        a.download = filename;

        document.body.appendChild(a);
        a.click();

        a.remove();

        window.URL.revokeObjectURL(url);

    })

    .catch(error => {

        console.error(error);
        alert("Excel download failed");

    });

}
