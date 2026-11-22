"""Step 1: read the five raw Excel files, tidy them, and write clean CSVs.

Run from the project folder:  python src/clean.py
"""
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW, CLEAN = ROOT / "data" / "raw", ROOT / "data" / "clean"
CLEAN.mkdir(parents=True, exist_ok=True)

YEARS = list(range(2015, 2025))
CAT_NAMES = {"2W": "Two-wheeler", "3W": "Three-wheeler", "LMV": "Car / light vehicle", "MMV": "Medium vehicle"}


def maker_key(name: str) -> str:
    """Merge spelling variants: 'AMPERE VEHICLES PRIVATE LIMITED' and 'AMPERE VEHICLES PVT LTD' are one company."""
    n = name.upper().replace('"', "").replace("&", " AND ")
    n = re.sub(r"[.,()\-/']", " ", n)
    n = re.sub(r"\b(PRIVATE|PVT)\b", "PVT", n)
    n = re.sub(r"\b(LIMITED|LTD)\b", "LTD", n)
    n = re.sub(r"\bINDIA\b", "", n)
    n = re.sub(r"\s+", " ", n).strip()
    n = re.sub(r"\b(PVT LTD|PVT|LTD)\b", "", n).strip()
    return re.sub(r"\s+", " ", n)


def pretty(name: str) -> str:
    small = {"AND", "OF"}
    words = [w if w in small else (w if len(w) <= 3 and w.isupper() and w in {"TVS", "EV", "MG", "BYD", "JBM", "JSW", "LLP", "YC"} else w.capitalize())
             for w in name.split()]
    return " ".join(words).replace(" AND ", " & ")


# Same company, different legal-entity or spelling. Checked by hand against the maker list.
# These are judgement calls, so they live here in plain sight where anyone can review them.
ALIASES = {
    "Hero Electric Vehicle": "Hero Electric Vehicles",
    "Y C Electric Vehicle": "YC Electric Vehicle",
    "M S Champion Poly Plast": "Champion Poly Plast",
    "Tata Motors": "Tata Motors (EV)",
    "Tata Motors Passenger Vehicles": "Tata Motors (EV)",
    "Tata Passenger Electric Mobility": "Tata Motors (EV)",
    "Mahindra & Mahindra": "Mahindra Group",
    "Mahindra Last Mile Mobility": "Mahindra Group",
    "Mahindra Electric Mobility": "Mahindra Group",
    "Mini Metro EV L L P": "Mini Metro",
    "Bestway Agencies": "Best Way Agencies",
    "Speego Vehicles": "Speego Vehicles Co",
    "Attolent Autogroup": "Attolent Auto Group",
    "Gkon Electric Motor Vehicles": "Goenka Electric Motor Vehicles",
    "Goenka Electric Motor Veh P L": "Goenka Electric Motor Vehicles",
    "J S Mobileon": "Js Mobileon",
    "Electrotherm I": "Electrotherm",
    "Soni E Vehicles": "Soni E Vehicle",
    "M S Hovel Cylinder": "Hovel Cylinder",
    "Mercedes Benz": "Mercedes Benz Ag",
    "Shri Ram Auto Tech": "M S Shriram Auto Tech",
}
# Rows that are not real makers: a bucket for everything small, and a test account.
NOT_A_MAKER = {"Others", "Nic Test Account 1"}


def clean_sales() -> pd.DataFrame:
    s = pd.read_excel(RAW / "ev_sales_by_maker_and_category.xlsx")
    s.columns = ["category" if c == "Cat" else "maker_raw" if c == "EV Maker" else int(c) for c in s.columns]
    s["maker_key"] = s["maker_raw"].map(maker_key)
    # one display name per company: the spelling with the most units
    s["units"] = s[YEARS].sum(axis=1)
    display = (s.sort_values("units", ascending=False).drop_duplicates("maker_key")
               .set_index("maker_key")["maker_raw"].map(lambda x: pretty(maker_key(x))))
    s["maker"] = s["maker_key"].map(display).replace(ALIASES)
    s["is_real_maker"] = ~s["maker"].isin(NOT_A_MAKER)
    long = (s.groupby(["maker", "category", "is_real_maker"], as_index=False)[YEARS].sum())
    return long


def clean_registrations() -> pd.DataFrame:
    c = pd.read_excel(RAW / "ev_registrations_by_class_monthly.xlsx").iloc[1:].copy()  # first row is all zeros
    c["Date"] = pd.to_datetime(c["Date"])
    c = c.sort_values("Date").reset_index(drop=True)
    c.columns = ["date"] + [re.sub(r"\s+", " ", x.strip().title()) for x in c.columns[1:]]
    return c


def clean_states() -> pd.DataFrame:
    o = pd.read_excel(RAW / "operational_charging_stations_by_state.xlsx")
    o.columns = ["state", "operational_stations"]
    return o


def clean_makers_place() -> pd.DataFrame:
    m = pd.read_excel(RAW / "ev_maker_by_place.xlsx")
    m.columns = ["maker", "place", "state"]
    return m.drop_duplicates().reset_index(drop=True)


def clean_all_vehicles() -> pd.DataFrame:
    v = pd.read_excel(RAW / "vehicle_registrations_all_classes.xlsx")
    v.columns = ["vehicle_class", "total_registrations"]
    v["vehicle_class"] = v["vehicle_class"].str.strip().str.title()
    return v


if __name__ == "__main__":
    sales = clean_sales()
    sales.to_csv(CLEAN / "ev_sales_by_maker_category.csv", index=False)
    clean_registrations().to_csv(CLEAN / "ev_registrations_monthly.csv", index=False)
    clean_states().to_csv(CLEAN / "charging_stations_by_state.csv", index=False)
    clean_makers_place().to_csv(CLEAN / "maker_locations.csv", index=False)
    clean_all_vehicles().to_csv(CLEAN / "all_vehicle_registrations.csv", index=False)
    raw_n = pd.read_excel(RAW / "ev_sales_by_maker_and_category.xlsx")["EV Maker"].nunique()
    print(f"Sales rows (maker x category): {len(sales):,}")
    print(f"Makers: {raw_n:,} spellings -> {sales.maker.nunique():,} companies after merging name variants")
    print("Not real makers (bucket/test rows):", sorted(NOT_A_MAKER & set(sales.maker)))
    print("Units 2015-2024:", f"{int(sales[YEARS].sum().sum()):,}")
