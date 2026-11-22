"""Shared logic: build one row per maker, cluster them, name the segments.

The Streamlit app and the analysis script both import from here, so the numbers
on the website are always the same as the numbers in the README.
"""
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
CLEAN = ROOT / "data" / "clean"
YEARS = list(range(2015, 2025))
YCOLS = [str(y) for y in YEARS]
LATEST_FULL_YEAR = 2023          # 2024 stops in early August, so it is not a full year
ESTABLISHED_MIN_UNITS = 1000     # below this a maker goes in the "long tail", not the clustering
FEATURES = ["log_units", "recent_share", "now_vs_peak", "growth_2023", "first_year"]
FEATURE_LABELS = {
    "log_units": "Size (log of total units sold)",
    "recent_share": "Share of sales that came in 2022-2024",
    "now_vs_peak": "2023 sales as a share of the maker's best year",
    "growth_2023": "Growth 2022 to 2023 (log ratio)",
    "first_year": "First year with sales",
}
K = 4
SEED = 42
SEGMENT_ORDER = ["Market leaders", "Steady mid-sized sellers", "New challengers", "Faded players"]
SEGMENT_BLURB = {
    "Market leaders": "The biggest sellers. A few dozen companies make up most of all EVs sold. Most are still at their best, but a few have fallen sharply.",
    "Steady mid-sized sellers": "Small to mid volumes, around since about 2017, and still selling close to their best year.",
    "New challengers": "Started around 2021 and grew very fast. Almost all of their sales are recent.",
    "Faded players": "Sold earlier on, but sales are now far below their best year. Some are really a rebrand (see the README).",
}
CATEGORY_NAMES = {"2W": "Two-wheeler", "3W": "Three-wheeler", "LMV": "Car / light vehicle", "MMV": "Medium vehicle"}


def load_sales() -> pd.DataFrame:
    return pd.read_csv(CLEAN / "ev_sales_by_maker_category.csv")


def maker_table(sales: pd.DataFrame) -> pd.DataFrame:
    """One row per real maker with the features used for clustering."""
    s = sales[sales["is_real_maker"]]
    t = s.groupby("maker")[YCOLS].sum()
    f = pd.DataFrame({"units": t.sum(axis=1)})
    f = f[f.units > 0].copy()
    t = t.loc[f.index]
    f["units_2022"], f["units_2023"] = t["2022"], t["2023"]
    f["units_2024_part"] = t["2024"]
    f["recent_share"] = t[["2022", "2023", "2024"]].sum(axis=1) / f.units
    f["first_year"] = t.gt(0).values.argmax(axis=1) + YEARS[0]
    full = t[[str(y) for y in YEARS if y <= LATEST_FULL_YEAR]]      # 2024 is partial, so it can't set the "best year"
    f["best_year"] = full.values.argmax(axis=1) + YEARS[0]
    f["now_vs_peak"] = (t["2023"] / full.max(axis=1)).fillna(0)
    f["growth_2023"] = np.log((t["2023"] + 20) / (t["2022"] + 20))   # +20 so a tiny maker doesn't blow the ratio up
    f["log_units"] = np.log10(f.units)
    cat = s.assign(units=s[YCOLS].sum(axis=1)).pivot_table(index="maker", columns="category", values="units", aggfunc="sum", fill_value=0)
    f["main_category"] = cat.reindex(f.index).idxmax(axis=1).map(CATEGORY_NAMES)
    f["n_categories"] = (cat.reindex(f.index) > 0).sum(axis=1)
    f["established"] = f.units >= ESTABLISHED_MIN_UNITS
    return f


def fit_segments(makers: pd.DataFrame, k: int = K, seed: int = SEED):
    """Cluster the established makers. Returns (table with a 'segment' column, scaler, kmeans, name_by_cluster)."""
    est = makers[makers.established]
    scaler = StandardScaler().fit(est[FEATURES])
    km = KMeans(k, n_init=30, random_state=seed).fit(scaler.transform(est[FEATURES]))
    names = name_clusters(est.assign(c=km.labels_))
    out = makers.copy()
    out["segment"] = "Long tail (under 1,000 units)"
    out.loc[est.index, "segment"] = pd.Series(km.labels_, index=est.index).map(names)
    return out, scaler, km, names


def name_clusters(est_with_c: pd.DataFrame) -> dict:
    """Name each cluster from its own profile, so the names follow the data and not the cluster numbers."""
    p = est_with_c.groupby("c").agg(median_units=("units", "median"), recent=("recent_share", "mean"),
                                   peak=("now_vs_peak", "mean"), first=("first_year", "mean"))
    names = {}
    names[p.median_units.idxmax()] = "Market leaders"
    rest = p.drop(index=list(names))
    names[rest.peak.idxmin()] = "Faded players"
    rest = p.drop(index=list(names))
    names[rest["first"].idxmax()] = "New challengers"
    names[p.drop(index=list(names)).index[0]] = "Steady mid-sized sellers"
    return names


def assign_new_maker(scaler, km, names, first_year, units_2022, units_2023, total_units, best_year_units, recent_units):
    """Which segment would a maker with these numbers fall into? Used by the app's 'check a maker' box."""
    row = pd.DataFrame([{
        "log_units": np.log10(max(total_units, 1)),
        "recent_share": min(recent_units / max(total_units, 1), 1.0),
        "now_vs_peak": min(units_2023 / max(best_year_units, 1), 1.0),
        "growth_2023": np.log((units_2023 + 20) / (units_2022 + 20)),
        "first_year": first_year,
    }])[FEATURES]
    return names[int(km.predict(scaler.transform(row))[0])]
