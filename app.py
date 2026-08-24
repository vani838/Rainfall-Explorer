from flask import Flask, render_template, request, jsonify, send_file
import xarray as xr
import pandas as pd
import numpy as np
import os
import requests
from io import BytesIO


from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Border, Side, Alignment


# ==================================================
# FLASK APP
# ==================================================

app = Flask(__name__)


# ==================================================
# DATASET CONFIGURATION
# ==================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATASET_PATH = os.path.join(
    BASE_DIR,
    "final_merged.nc"
)


print("="*60)
print("🌧 Rainfall Explorer v3")
print("Loading Rainfall Dataset...")
print("="*60)


try:

    ds = xr.open_dataset(
        DATASET_PATH,
        engine="netcdf4"
    )

    rain = ds["RAINFALL"]


    print("✅ Dataset Loaded Successfully")
    print(ds)

    print("\nTotal Records :", len(ds.TIME))
    print("Latitude Grid :", len(ds.LATITUDE))
    print("Longitude Grid:", len(ds.LONGITUDE))


except Exception as e:

    print("❌ Dataset Loading Failed")
    print(e)
    raise



# ==================================================
# HOME PAGE
# ==================================================

@app.route("/")
def home():

    return render_template("index.html")



# ==================================================
# HELPER FUNCTIONS
# ==================================================


def get_point(lat, lon):

    return rain.sel(
        LATITUDE=lat,
        LONGITUDE=lon,
        method="nearest"
    )



def rainfall_category(value):

    if value <= 2.5:
        return "No Rain"

    elif value <= 15:
        return "Light Rain"

    elif value <= 65:
        return "Moderate Rain"

    else:
        return "Heavy Rain"



def calculate_statistics(data):

    avg = float(data.mean().values)
    maximum = float(data.max().values)
    minimum = float(data.min().values)

    return avg, maximum, minimum



def validate_coordinates(lat, lon):

    if lat < 6.5 or lat > 38.5:
        return False

    if lon < 66.5 or lon > 100:
        return False

    return True

# ==================================================
# LIVE RAINFALL DATA
# ==================================================

def get_live_rainfall(lat, lon, date):

    url = "https://api.open-meteo.com/v1/forecast"

    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "precipitation,rain",
        "start_date": date,
        "end_date": date,
        "timezone": "Asia/Kolkata"
    }

    response = requests.get(
        url,
        params=params,
        timeout=15
    )

    response.raise_for_status()

    data = response.json()

    print("\n========== LIVE API DEBUG ==========")
    print("Requested Date :", date)
    print("Requested Lat  :", lat)
    print("Requested Lon  :", lon)
    print("API Timezone   :", data.get("timezone"))
    print("API Latitude   :", data.get("latitude"))
    print("API Longitude  :", data.get("longitude"))

    hourly = data.get("hourly")

    if not hourly:
        raise ValueError("No live rainfall data available")

    times = hourly.get("time", [])
    precipitation = hourly.get("precipitation", [])
    rain = hourly.get("rain", [])

    print("Number of hours:", len(times))

    print("\nHourly precipitation:")

    for t, p in zip(times, precipitation):
        print(t, "→", p, "mm")

    if not precipitation:
        raise ValueError("Rainfall data not available")

    total_precipitation = sum(
        value for value in precipitation
        if value is not None
    )

    print("\nTOTAL PRECIPITATION:", total_precipitation)
    print("====================================\n")

    return {
        "rainfall": round(float(total_precipitation), 2),
        "rain": round(
            float(sum(
                value for value in rain
                if value is not None
            )),
            2
        ),
        "latitude": lat,
        "longitude": lon,
        "date": date
    }
    
# ==================================================
# EXCEL DOWNLOAD REPORT
# HISTORICAL + LIVE / FORECAST
# ==================================================

@app.route("/download_excel", methods=["POST"])
def download_excel():

    print("========== EXCEL DOWNLOAD ==========")

    try:

        data = request.get_json()

        lat = float(data["latitude"])
        lon = float(data["longitude"])

        start_date = data["start_date"]
        end_date = data["end_date"]

        start = pd.to_datetime(start_date)
        end = pd.to_datetime(end_date)

        dataset_end = pd.Timestamp("2024-12-31")

        print("Latitude :", lat)
        print("Longitude:", lon)
        print("Start    :", start_date)
        print("End      :", end_date)

        # ==================================================
        # COMMON DATA VARIABLES
        # ==================================================

        data_source = ""
        nearest_lat = lat
        nearest_lon = lon

        dates = []
        values = []

        # ==================================================
        # LIVE / FORECAST DATA
        # ==================================================

        if end > dataset_end:

            print("========== EXCEL: OPEN-METEO ==========")

            url = "https://api.open-meteo.com/v1/forecast"

            params = {
                "latitude": lat,
                "longitude": lon,
                "hourly": "precipitation",
                "start_date": start_date,
                "end_date": end_date,
                "timezone": "Asia/Kolkata"
            }

            response = requests.get(
                url,
                params=params,
                timeout=15
            )

            response.raise_for_status()

            api_data = response.json()

            hourly = api_data.get("hourly")

            if not hourly:
                raise ValueError(
                    "No Open-Meteo hourly data available"
                )

            times = hourly.get("time", [])

            precipitation = hourly.get(
                "precipitation",
                []
            )

            if not precipitation:
                raise ValueError(
                    "Precipitation data not available"
                )

            # API grid coordinates
            nearest_lat = float(
                api_data.get(
                    "latitude",
                    lat
                )
            )

            nearest_lon = float(
                api_data.get(
                    "longitude",
                    lon
                )
            )

            # ==================================================
            # SAME PRECIPITATION VALUES USED BY WEBSITE
            # ==================================================

            for time_value, rainfall_value in zip(
                times,
                precipitation
            ):

                if rainfall_value is None:
                    rainfall_value = 0.0

                dates.append(
                    pd.to_datetime(time_value)
                )

                values.append(
                    float(rainfall_value)
                )

            if not values:

                raise ValueError(
                    "No valid precipitation values found"
                )

            data_source = "Open-Meteo"

            print(
                "OPEN-METEO TOTAL:",
                round(sum(values), 2)
            )

            print(
                "NUMBER OF RECORDS:",
                len(values)
            )

        # ==================================================
        # HISTORICAL NETCDF DATA
        # ==================================================

        else:

            print(
                "========== EXCEL: HISTORICAL NETCDF =========="
            )

            rainfall = rain.sel(
                LATITUDE=lat,
                LONGITUDE=lon,
                method="nearest"
            )

            rainfall = rainfall.sel(
                TIME=slice(
                    start_date,
                    end_date
                )
            )

            if rainfall.size == 0:

                return jsonify({
                    "error":
                    "No rainfall data found"
                }), 404

            nearest_lat = float(
                rainfall.LATITUDE.values.item()
            )

            nearest_lon = float(
                rainfall.LONGITUDE.values.item()
            )

            historical_times = pd.to_datetime(
                rainfall.TIME.values
            )

            historical_values = (
                rainfall.values.flatten()
            )

            for time_value, rainfall_value in zip(
                historical_times,
                historical_values
            ):

                if pd.isna(rainfall_value):
                    continue

                dates.append(
                    pd.to_datetime(time_value)
                )

                values.append(
                    float(rainfall_value)
                )

            if not values:

                return jsonify({
                    "error":
                    "No valid rainfall data found"
                }), 404

            data_source = "IMD Historical NetCDF"

        # ==================================================
        # COMMON DATAFRAME
        # ==================================================

        df = pd.DataFrame({
            "Date": dates,
            "Rainfall": values
        })

        df["Date"] = pd.to_datetime(
            df["Date"]
        )

        df["Rainfall"] = pd.to_numeric(
            df["Rainfall"],
            errors="coerce"
        )

        df = df.dropna(
            subset=["Rainfall"]
        )

        if df.empty:

            return jsonify({
                "error":
                "No valid rainfall data found"
            }), 404

        # ==================================================
        # OVERALL STATISTICS
        # ==================================================

        total_rainfall = float(
            df["Rainfall"].sum()
        )

        avg = float(
            df["Rainfall"].mean()
        )

        maximum = float(
            df["Rainfall"].max()
        )

        minimum = float(
            df["Rainfall"].min()
        )

        wet_days = int(
            (
                df["Rainfall"] > 0.1
            ).sum()
        )

        total_records = len(df)

        print(
            "TOTAL RAINFALL:",
            round(total_rainfall, 2)
        )

        print(
            "AVERAGE:",
            round(avg, 2)
        )

        print(
            "MAXIMUM:",
            round(maximum, 2)
        )

        print(
            "MINIMUM:",
            round(minimum, 2)
        )

        # ==================================================
        # CREATE WORKBOOK
        # ==================================================

        wb = Workbook()

        # ==================================================
        # EXCEL PROFESSIONAL STYLING
        # ==================================================

        from openpyxl.styles import Font, PatternFill, Border, Side, Alignment
        from openpyxl.formatting.rule import CellIsRule

        # ---------- COLORS ----------
        dark_blue = "1F4E78"
        medium_blue = "5B9BD5"
        light_blue = "D9EAF7"
        very_light_blue = "EAF3F8"

        dark_green = "548235"
        light_green = "E2F0D9"

        dark_orange = "C65911"
        light_orange = "FCE4D6"

        dark_red = "C00000"
        light_red = "F4CCCC"

        dark_gray = "404040"
        light_gray = "F2F2F2"
        white = "FFFFFF"

        # ---------- FONTS ----------
        title_font = Font(
            name="Calibri",
            size=18,
            bold=True,
            color=white
        )

        subtitle_font = Font(
            name="Calibri",
            size=12,
            bold=True,
            color=dark_blue
        )

        header_font = Font(
            name="Calibri",
            size=11,
            bold=True,
            color=white
        )

        bold_font = Font(
            name="Calibri",
            size=11,
            bold=True
        )

        normal_font = Font(
            name="Calibri",
            size=11
        )

        # ---------- FILLS ----------
        title_fill = PatternFill(
            "solid",
            fgColor=dark_blue
        )

        header_fill = PatternFill(
            "solid",
            fgColor=medium_blue
        )

        section_fill = PatternFill(
            "solid",
            fgColor=light_blue
        )

        alternate_fill = PatternFill(
            "solid",
            fgColor=very_light_blue
        )

        green_fill = PatternFill(
            "solid",
            fgColor=light_green
        )

        orange_fill = PatternFill(
            "solid",
            fgColor=light_orange
        )

        red_fill = PatternFill(
            "solid",
            fgColor=light_red
        )

        gray_fill = PatternFill(
            "solid",
            fgColor=light_gray
        )

        # ---------- BORDER ----------
        thin_side = Side(
            style="thin",
            color="B7B7B7"
        )

        medium_side = Side(
            style="medium",
            color=dark_blue
        )

        thin_border = Border(
            left=thin_side,
            right=thin_side,
            top=thin_side,
            bottom=thin_side
        )

        # ---------- ALIGNMENT ----------
        center_alignment = Alignment(
            horizontal="center",
            vertical="center"
        )

        left_alignment = Alignment(
            horizontal="left",
            vertical="center"
        )

        # ---------- GENERAL SHEET FUNCTION ----------
        def style_table_sheet(
            sheet,
            header_row=1,
            alternate_rows=True
        ):

            # Header
            for cell in sheet[header_row]:

                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = center_alignment
                cell.border = thin_border

            # Data rows
            for row_num in range(
                header_row + 1,
                sheet.max_row + 1
            ):

                for cell in sheet[row_num]:

                    cell.font = normal_font
                    cell.alignment = center_alignment
                    cell.border = thin_border

                    if (
                        alternate_rows
                        and row_num % 2 == 0
                    ):
                        cell.fill = alternate_fill

            # Header height
            sheet.row_dimensions[
                header_row
            ].height = 25

            # Freeze header
            sheet.freeze_panes = "A2"

            # Filter
            if sheet.max_row >= header_row:
                sheet.auto_filter.ref = (
                    f"A{header_row}:"
                    f"{chr(64 + sheet.max_column)}"
                    f"{sheet.max_row}"
                )

        # ---------- RAINFALL CATEGORY COLORS ----------
        def style_category_cell(cell):

            if cell.value == "No Rain":

                cell.fill = gray_fill
                cell.font = Font(
                    bold=True,
                    color=dark_gray
                )

            elif cell.value == "Light Rain":

                cell.fill = green_fill
                cell.font = Font(
                    bold=True,
                    color=dark_green
                )

            elif cell.value == "Moderate Rain":

                cell.fill = orange_fill
                cell.font = Font(
                    bold=True,
                    color=dark_orange
                )

            elif cell.value == "Heavy Rain":

                cell.fill = red_fill
                cell.font = Font(
                    bold=True,
                    color=dark_red
                )

        # ==================================================
        # SUMMARY SHEET
        # ==================================================

        ws = wb.active
        ws.title = "Summary"

        ws.append(
            ["RAINFALL EXPLORER"]
        )

        ws.append(
            [
                "Rainfall Analysis Report"
            ]
        )

        ws.append([])

        ws.append(
            [
                "Data Source",
                data_source
            ]
        )

        ws.append(
            [
                "Latitude",
                nearest_lat
            ]
        )

        ws.append(
            [
                "Longitude",
                nearest_lon
            ]
        )

        ws.append(
            [
                "Period",
                f"{start_date} to {end_date}"
            ]
        )

        ws.append([])

        ws.append(
            ["Statistics"]
        )

        # ==================================================
        # SUMMARY VALUES
        # ==================================================

        if data_source == "Open-Meteo":

            # For a single date, this is exactly
            # the same total shown by the website.

            if start_date == end_date:

                summary_average = total_rainfall

            else:

                summary_average = avg

        else:

            summary_average = avg

        rows = [

            [
                "Average Daily Rainfall (mm)",
                round(
                    summary_average,
                    2
                )
            ],

            [
                "Total Rainfall (mm)",
                round(
                    total_rainfall,
                    2
                )
            ],

            [
                "Maximum Rainfall (mm)",
                round(
                    maximum,
                    2
                )
            ],

            [
                "Minimum Rainfall (mm)",
                round(
                    minimum,
                    2
                )
            ],

            [
                "Wet Days / Records",
                wet_days
            ],

            [
                "Total Records",
                total_records
            ]

        ]

        for row in rows:
            ws.append(row)

        ws.column_dimensions["A"].width = 35
        ws.column_dimensions["B"].width = 30

        # ==================================================
        # MONTHLY SUMMARY
        # ==================================================

        monthly_ws = wb.create_sheet(
            "Monthly Summary"
        )

        monthly_ws.append(
            [
                "Month",
                "Total Rainfall",
                "Average",
                "Maximum",
                "Minimum",
                "Wet Days"
            ]
        )

        months = [
            "January",
            "February",
            "March",
            "April",
            "May",
            "June",
            "July",
            "August",
            "September",
            "October",
            "November",
            "December"
        ]

        df["MonthNumber"] = (
            df["Date"].dt.month
        )

        for m in range(1, 13):

            month_data = df[
                df["MonthNumber"] == m
            ]["Rainfall"]

            if not month_data.empty:

                total = float(
                    month_data.sum()
                )

                avg_month = float(
                    month_data.mean()
                )

                max_month = float(
                    month_data.max()
                )

                min_month = float(
                    month_data.min()
                )

                wet_days_month = int(
                    (
                        month_data > 0.1
                    ).sum()
                )

            else:

                total = 0.0
                avg_month = 0.0
                max_month = 0.0
                min_month = 0.0
                wet_days_month = 0

            monthly_ws.append(
                [
                    months[m - 1],
                    round(total, 2),
                    round(avg_month, 2),
                    round(max_month, 2),
                    round(min_month, 2),
                    wet_days_month
                ]
            )

        for col in "ABCDEF":
            monthly_ws.column_dimensions[
                col
            ].width = 22

        # ==================================================
        # YEARLY DATA
        # ==================================================

        yearly_ws = wb.create_sheet(
            "Yearly Data"
        )

        yearly_ws.append(
            [
                "Year",
                "Total Rainfall (mm)",
                "Average (mm)",
                "Maximum (mm)",
                "Minimum (mm)",
                "Wet Days"
            ]
        )

        df["Year"] = (
            df["Date"].dt.year
        )

        years = sorted(
            df["Year"].unique()
        )

        for year in years:

            year_data = df[
                df["Year"] == year
            ]["Rainfall"]

            if year_data.empty:
                continue

            yearly_ws.append(
                [
                    int(year),

                    round(
                        float(
                            year_data.sum()
                        ),
                        2
                    ),

                    round(
                        float(
                            year_data.mean()
                        ),
                        2
                    ),

                    round(
                        float(
                            year_data.max()
                        ),
                        2
                    ),

                    round(
                        float(
                            year_data.min()
                        ),
                        2
                    ),

                    int(
                        (
                            year_data > 0.1
                        ).sum()
                    )
                ]
            )

        for col in "ABCDEF":
            yearly_ws.column_dimensions[
                col
            ].width = 22

        # ==================================================
        # DAILY DATA
        # ==================================================

        daily_ws = wb.create_sheet(
            "Daily Data"
        )

        daily_ws.append(
            [
                "Date",
                "Year",
                "Month",
                "Day",
                "Rainfall (mm)",
                "Category"
            ]
        )

        # ==================================================
        # CATEGORY FUNCTION
        # ==================================================

        def get_category(value):

            if value <= 2.5:
                return "No Rain"

            elif value <= 15:
                return "Light Rain"

            elif value <= 65:
                return "Moderate Rain"

            else:
                return "Heavy Rain"

        # ==================================================
        # LIVE DATA
        # ==================================================

        if data_source == "Open-Meteo":

            # For live Open-Meteo data,
            # keep hourly records.

            for date, value in zip(
                df["Date"],
                df["Rainfall"]
            ):

                value = float(value)

                daily_ws.append(
                    [
                        date.strftime(
                            "%Y-%m-%d %H:%M"
                        ),

                        date.year,

                        date.strftime(
                            "%B"
                        ),

                        date.day,

                        round(
                            value,
                            2
                        ),

                        get_category(
                            value
                        )
                    ]
                )

        # ==================================================
        # HISTORICAL DATA
        # ==================================================

        else:

            for date, value in zip(
                df["Date"],
                df["Rainfall"]
            ):

                value = float(value)

                daily_ws.append(
                    [
                        date.strftime(
                            "%Y-%m-%d"
                        ),

                        date.year,

                        date.strftime(
                            "%B"
                        ),

                        date.day,

                        round(
                            value,
                            2
                        ),

                        get_category(
                            value
                        )
                    ]
                )

        for col in "ABCDEF":

            daily_ws.column_dimensions[
                col
            ].width = 20

        print(
            "DAILY SHEET CREATED"
        )

        print(
            wb.sheetnames
        )

        # ==================================================
        # APPLY PROFESSIONAL FORMATTING
        # ==================================================

        # --------------------------------------------------
        # SUMMARY SHEET
        # --------------------------------------------------

        # Main title
        ws.merge_cells("A1:B1")

        ws["A1"].fill = title_fill
        ws["A1"].font = title_font
        ws["A1"].alignment = center_alignment
        ws["A1"].border = Border(
            top=medium_side,
            bottom=medium_side
        )

        ws.row_dimensions[1].height = 32

        # Subtitle
        ws.merge_cells("A2:B2")

        ws["A2"].font = subtitle_font
        ws["A2"].alignment = center_alignment

        # Information section
        for row_num in range(4, 8):

            ws[f"A{row_num}"].fill = section_fill
            ws[f"A{row_num}"].font = bold_font
            ws[f"A{row_num}"].border = thin_border

            ws[f"B{row_num}"].border = thin_border
            ws[f"B{row_num}"].alignment = center_alignment

        # Statistics heading
        ws["A9"].fill = header_fill
        ws["A9"].font = header_font
        ws["A9"].alignment = center_alignment

        ws.merge_cells("A9:B9")

        # Statistics
        for row_num in range(
            10,
            ws.max_row + 1
        ):

            ws[f"A{row_num}"].font = bold_font
            ws[f"A{row_num}"].fill = section_fill
            ws[f"A{row_num}"].border = thin_border

            ws[f"B{row_num}"].border = thin_border
            ws[f"B{row_num}"].alignment = center_alignment

            # Highlight important values
            if row_num in [10, 11]:
                ws[f"B{row_num}"].fill = green_fill
                ws[f"B{row_num}"].font = Font(
                    bold=True
                )

            elif row_num == 12:
                ws[f"B{row_num}"].fill = orange_fill
                ws[f"B{row_num}"].font = Font(
                    bold=True
                )

            elif row_num == 13:
                ws[f"B{row_num}"].fill = section_fill

        # Summary widths
        ws.column_dimensions["A"].width = 38
        ws.column_dimensions["B"].width = 30

        ws.freeze_panes = "A4"


        # --------------------------------------------------
        # MONTHLY SUMMARY
        # --------------------------------------------------

        style_table_sheet(
            monthly_ws,
            header_row=1,
            alternate_rows=True
        )

        monthly_ws.freeze_panes = "A2"

        # Highlight rainfall columns
        for row_num in range(
            2,
            monthly_ws.max_row + 1
        ):

            monthly_ws[f"B{row_num}"].fill = section_fill
            monthly_ws[f"C{row_num}"].fill = alternate_fill

            monthly_ws[f"D{row_num}"].fill = orange_fill

            monthly_ws[f"E{row_num}"].fill = green_fill

            monthly_ws[f"F{row_num}"].fill = gray_fill

        # Month column
        for row_num in range(
            2,
            monthly_ws.max_row + 1
        ):

            monthly_ws[f"A{row_num}"].font = bold_font

        monthly_ws.column_dimensions["A"].width = 20
        monthly_ws.column_dimensions["B"].width = 22
        monthly_ws.column_dimensions["C"].width = 20
        monthly_ws.column_dimensions["D"].width = 20
        monthly_ws.column_dimensions["E"].width = 20
        monthly_ws.column_dimensions["F"].width = 18


        # --------------------------------------------------
        # YEARLY DATA
        # --------------------------------------------------

        style_table_sheet(
            yearly_ws,
            header_row=1,
            alternate_rows=True
        )

        for row_num in range(
            2,
            yearly_ws.max_row + 1
        ):

            yearly_ws[f"A{row_num}"].font = bold_font

            yearly_ws[f"B{row_num}"].fill = section_fill
            yearly_ws[f"C{row_num}"].fill = alternate_fill
            yearly_ws[f"D{row_num}"].fill = orange_fill
            yearly_ws[f"E{row_num}"].fill = green_fill
            yearly_ws[f"F{row_num}"].fill = gray_fill

        yearly_ws.freeze_panes = "A2"

        yearly_ws.column_dimensions["A"].width = 14
        yearly_ws.column_dimensions["B"].width = 24
        yearly_ws.column_dimensions["C"].width = 20
        yearly_ws.column_dimensions["D"].width = 20
        yearly_ws.column_dimensions["E"].width = 20
        yearly_ws.column_dimensions["F"].width = 18


        # --------------------------------------------------
        # DAILY DATA
        # --------------------------------------------------

        style_table_sheet(
            daily_ws,
            header_row=1,
            alternate_rows=True
        )

        daily_ws.freeze_panes = "A2"

        # Date column
        daily_ws.column_dimensions["A"].width = 23

        # Other columns
        daily_ws.column_dimensions["B"].width = 14
        daily_ws.column_dimensions["C"].width = 16
        daily_ws.column_dimensions["D"].width = 12
        daily_ws.column_dimensions["E"].width = 18
        daily_ws.column_dimensions["F"].width = 20

        # Rainfall + category formatting
        for row_num in range(
            2,
            daily_ws.max_row + 1
        ):

            rainfall_cell = daily_ws[
                f"E{row_num}"
            ]

            category_cell = daily_ws[
                f"F{row_num}"
            ]

            rainfall_value = rainfall_cell.value

            if rainfall_value is not None:

                if rainfall_value <= 2.5:

                    rainfall_cell.fill = gray_fill

                elif rainfall_value <= 15:

                    rainfall_cell.fill = green_fill

                elif rainfall_value <= 65:

                    rainfall_cell.fill = orange_fill

                else:

                    rainfall_cell.fill = red_fill

                rainfall_cell.font = Font(
                    bold=True
                )

            style_category_cell(
                category_cell
            )

        # ==================================================
        # SAVE EXCEL
        # ==================================================

        excel_file = BytesIO()

        wb.save(
            excel_file
        )

        excel_file.seek(0)

        filename = (
            f"Rainfall_Report_"
            f"{nearest_lat}_"
            f"{nearest_lon}.xlsx"
        )

        print(
            "DATA SOURCE:",
            data_source
        )

        print(
            "EXCEL TOTAL:",
            round(
                total_rainfall,
                2
            )
        )

        print(
            "✅ Excel Generated"
        )

        return send_file(
            excel_file,
            as_attachment=True,
            download_name=filename,
            mimetype=(
                "application/"
                "vnd.openxmlformats-officedocument"
                ".spreadsheetml.sheet"
            )
        )

    except Exception as e:

        print(
            "Excel Error:",
            e
        )

        return jsonify(
            {
                "error": str(e)
            }
        ), 500

# ==================================================
# YEARLY RAINFALL SUMMARY API
# ==================================================

@app.route("/yearly_summary", methods=["POST"])
def yearly_summary():

    try:

        data = request.get_json()

        lat = float(data["latitude"])
        lon = float(data["longitude"])


        rainfall_point = get_point(
            lat,
            lon
        )


        yearly_data = (
            rainfall_point
            .groupby("TIME.year")
            .sum()
        )


        years = [
            int(y)
            for y in yearly_data.year.values
        ]


        # FIX 3: Flatten array to handle multi-dimensional data
        rainfall_values = [
            round(float(v),2)
            for v in yearly_data.values.flatten()
        ]



        return jsonify({

            "status":"success",

            "years":years,

            "rainfall":rainfall_values

        })


    except Exception as e:

        print("Yearly Error:",e)

        return jsonify({

            "status":"error",

            "message":str(e)

        }),500




# ==================================================
# SEASONAL RAINFALL ANALYSIS
# ==================================================

@app.route("/season_analysis", methods=["POST"])
def season_analysis():

    try:

        data=request.get_json()


        lat=float(data["latitude"])
        lon=float(data["longitude"])



        rainfall_point=get_point(
            lat,
            lon
        )


        time = rainfall_point.TIME.dt.month



        seasons={

            "Winter":
            [12,1,2],

            "Summer":
            [3,4,5],

            "Monsoon":
            [6,7,8,9],

            "Post-Monsoon":
            [10,11]

        }


        season_data={}

        for season_name,months_list in seasons.items():

            season_rainfall = rainfall_point.where(
                rainfall_point.TIME.dt.month.isin(months_list),
                drop=True
            )

            if season_rainfall.size > 0:
                season_data[season_name]={

                    "total":round(
                        float(
                            season_rainfall.sum().values
                        ),2
                    ),

                    "average":round(
                        float(
                            season_rainfall.mean().values
                        ),2
                    ),

                    "maximum":round(
                        float(
                            season_rainfall.max().values
                        ),2
                    )

                }
            else:
                season_data[season_name]={
                    "total": 0.0,
                    "average": 0.0,
                    "maximum": 0.0
                }


        return jsonify({

            "status":"success",

            "seasons":season_data

        })


    except Exception as e:

        print("Season Error:",e)

        return jsonify({

            "status":"error",

            "message":str(e)

        }),500




# ==================================================
# EXTREME RAINFALL EVENTS
# ==================================================

@app.route("/extreme_events", methods=["POST"])
def extreme_events():

    try:


        data=request.get_json()


        lat=float(data["latitude"])
        lon=float(data["longitude"])



        rainfall_point=get_point(
            lat,
            lon
        )



        max_value=float(
            rainfall_point.max().values
        )


        min_value=float(
            rainfall_point.min().values
        )



        max_index = rainfall_point.argmax(
            dim="TIME"
        )


        # FIX 4: Use pd.Timestamp with strftime for reliable date formatting
        max_date = pd.Timestamp(
            rainfall_point.TIME[max_index].values
        ).strftime("%Y-%m-%d")



        heavy_events=int(
            (
            rainfall_point.values > 100
            ).sum()
        )



        return jsonify({

            "status":"success",

            "maximum_rainfall":
            round(max_value,2),


            "maximum_date":
            max_date,


            "minimum_rainfall":
            round(min_value,2),


            "heavy_rain_events":
            heavy_events

        })



    except Exception as e:


        print("Extreme Error:",e)


        return jsonify({

            "status":"error",

            "message":str(e)

        }),500




# ==================================================
# RAINFALL TREND ANALYSIS
# ==================================================

@app.route("/rainfall_trend", methods=["POST"])
def rainfall_trend():

    try:


        data=request.get_json()


        lat=float(data["latitude"])
        lon=float(data["longitude"])



        rainfall_point=get_point(
            lat,
            lon
        )



        yearly = (
            rainfall_point
            .groupby("TIME.year")
            .sum()
        )


        years=np.array(
            yearly.year.values
        )


        # FIX 5: Flatten values array for proper trend calculation
        values=np.array(
            yearly.values.flatten()
        )



        # Linear trend calculation

        slope, intercept = np.polyfit(
            years,
            values,
            1
        )



        if slope > 0:

            trend="Increasing"

        else:

            trend="Decreasing"




        return jsonify({

            "status":"success",

            "trend":trend,

            "slope":round(
                float(slope),
                4
            ),


            "years":[
                int(y)
                for y in years
            ],


            "rainfall":[
                round(float(v),2)
                for v in values
            ]

        })



    except Exception as e:


        print("Trend Error:",e)


        return jsonify({

            "status":"error",

            "message":str(e)

        }),500
        

# ==================================================
# MAIN RAINFALL API
# ==================================================

@app.route("/get_rainfall", methods=["POST"])
def get_rainfall():

    try:

        data = request.get_json()


        if not data:

            return jsonify({

                "status":"error",

                "message":"No data received"

            }),400



        lat=float(
            data.get("lat")
        )

        lon=float(
            data.get("lon")
        )



        if not validate_coordinates(lat,lon):

            return jsonify({

                "status":"error",

                "message":
                "Coordinates outside dataset"

            }),400



        search_type=data.get(
            "searchType",
            "date"
        )



        rainfall_point=get_point(
            lat,
            lon
        )


                # ==============================
        # SINGLE DATE
        # ==============================
        if search_type == "date":

            date = data.get("date")

            if not date:
                return jsonify({
                    "status": "error",
                    "message": "Date required"
                }), 400

            selected_date = pd.to_datetime(date)
            dataset_end = pd.Timestamp("2024-12-31")

            # ==========================================
            # LIVE / FORECAST DATA
            # ==========================================
            if selected_date > dataset_end:

                live_data = get_live_rainfall(
                    lat,
                    lon,
                    date
                )

                rainfall_value = live_data["rainfall"]

                today = pd.Timestamp.now().strftime("%Y-%m-%d")

                if date > today:
                    data_type = "forecast"
                else:
                    data_type = "current"

                return jsonify({
                    "status": "success",
                    "latitude": live_data["latitude"],
                    "longitude": live_data["longitude"],
                    "average": rainfall_value,
                    "maximum": rainfall_value,
                    "minimum": rainfall_value,
                    "category": rainfall_category(
                        rainfall_value
                    ),
                    "data_source": "Open-Meteo",
                    "data_type": data_type,
                    "date": date
                })

            # ==========================================
            # HISTORICAL DATA
            # ==========================================

            rainfall_point = rainfall_point.sel(
                TIME=date,
                method="nearest"
            )

            average, maximum, minimum = calculate_statistics(
                rainfall_point
            )

            nearest_lat = float(
                rainfall_point.LATITUDE.values.item()
            )

            nearest_lon = float(
                rainfall_point.LONGITUDE.values.item()
            )

            return jsonify({
                "status": "success",
                "latitude": nearest_lat,
                "longitude": nearest_lon,
                "average": round(average, 2),
                "maximum": round(maximum, 2),
                "minimum": round(minimum, 2),
                "category": rainfall_category(
                    average
                ),
                "data_source": "IMD Daily Rainfall Dataset",
                "data_type": "historical",
                "date": date
            })
            

                
    
    
        # ==============================
        # MONTH
        # ==============================

        elif search_type=="month":


            month=data.get("month")


            rainfall_point=rainfall_point.sel(

                TIME=slice(

                    f"{month}-01",

                    f"{month}-31"

                )

            )




        # ==============================
        # YEAR
        # ==============================

        elif search_type=="year":


            year=data.get("year")


            rainfall_point=rainfall_point.sel(

                TIME=slice(

                    f"{year}-01-01",

                    f"{year}-12-31"

                )

            )




        # ==============================
        # DATE RANGE
        # ==============================

        elif search_type=="dateRange":


            start=data.get(
                "fromDate"
            )

            end=data.get(
                "toDate"
            )


            rainfall_point=rainfall_point.sel(

                TIME=slice(
                    start,
                    end
                )

            )




        # ==============================
        # YEAR RANGE
        # ==============================

        elif search_type=="yearRange":


            start=data.get(
                "startYear"
            )

            end=data.get(
                "endYear"
            )


            rainfall_point=rainfall_point.sel(

                TIME=slice(

                    f"{start}-01-01",

                    f"{end}-12-31"

                )

            )




        # ==============================
        # STATISTICS
        # ==============================


        average,maximum,minimum = calculate_statistics(
            rainfall_point
        )



        # FIX 6: Use .item() for scalar extraction
        nearest_lat=float(
            rainfall_point.LATITUDE.values.item()
        )

        nearest_lon=float(
            rainfall_point.LONGITUDE.values.item()
        )



        return jsonify({
        "status": "success",

        "latitude": nearest_lat,

        "longitude": nearest_lon,

        "average": round(average, 2),

        "maximum": round(maximum, 2),

        "minimum": round(minimum, 2),

        "category": rainfall_category(
            average
        ),

        "data_source": "IMD Daily Rainfall Dataset",
        "data_type": "historical"
    })



    except Exception as e:


        print(
            "Rainfall API Error:",
            e
        )


        return jsonify({

            "status":"error",

            "message":str(e)

        }),500

# ==================================================
# RUN APPLICATION
# ==================================================

if __name__=="__main__":


    app.run(

        host="0.0.0.0",

        port=5503,

        debug=False

    )
    