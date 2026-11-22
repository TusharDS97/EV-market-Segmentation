"""Step 2: segment the EV makers, measure the market, and save charts + tables.

Run from the project folder:  python src/segment.py
Everything it writes goes to outputs/. The README quotes numbers from outputs/metrics.json.
"""
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import adjusted_rand_score, silhouette_score

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib

OUT = lib.ROOT / "outputs"
OUT.mkdir(exist_ok=True)
INK, MUTED, SURFACE, GRID = "#0b0b0b", "#52514e", "#fcfcfb", "#e6e5e1"
SEG_COLOUR = {"Market leaders": "#2a78d6", "Steady mid-sized sellers": "#eb6834", "New challengers": "#1baf7a",
              "Faded players": "#eda100", "Long tail (under 1,000 units)": "#b9b8b3"}
CAT_COLOUR = {"Two-wheeler": "#2a78d6", "Three-wheeler": "#eb6834", "Car / light vehicle": "#1baf7a", "Medium vehicle": "#eda100"}

plt.rcParams.update({"font.family": "DejaVu Sans", "axes.facecolor": SURFACE, "figure.facecolor": SURFACE,
                     "axes.edgecolor": GRID, "axes.labelcolor": MUTED, "xtick.color": MUTED, "ytick.color": MUTED,
                     "axes.spines.top": False, "axes.spines.right": False, "text.color": INK})


def tidy(ax):
    ax.grid(axis="y", color=GRID, lw=0.8); ax.set_axisbelow(True)


# ---------------------------------------------------------------- data
sales = lib.load_sales()
makers = lib.maker_table(sales)
seg, scaler, km, names = lib.fit_segments(makers)
est = seg[seg.established]
M = {}  # everything the README quotes

# ---------------------------------------------------------------- how big is the market
Y = lib.YCOLS
by_cat = sales.groupby("category")[Y].sum().rename(index=lib.CATEGORY_NAMES)
by_year = sales[Y].sum()
M["units_total"] = int(by_year.sum())
M["units_by_year"] = {int(k): int(v) for k, v in by_year.items()}
M["units_by_category_total"] = {k: int(v) for k, v in by_cat.sum(axis=1).items()}
M["growth_2022_to_2023_pct"] = round((by_year["2023"] / by_year["2022"] - 1) * 100, 1)
M["category_share_2023_pct"] = {k: round(v / by_year["2023"] * 100, 1) for k, v in by_cat["2023"].items()}
M["n_maker_spellings_raw"], M["n_makers"] = 1196, int(len(makers))
M["n_established"], M["n_long_tail"] = int(makers.established.sum()), int((~makers.established).sum())
M["established_share_of_units_pct"] = round(makers[makers.established].units.sum() / makers.units.sum() * 100, 1)
M["single_category_makers_pct"] = round((makers.n_categories == 1).mean() * 100, 1)

real = sales[sales.is_real_maker].groupby("maker")[Y].sum()
alltime = real.sum(axis=1).sort_values(ascending=False)
M["top5_share_all_time_pct"] = round(alltime.head(5).sum() / by_year.sum() * 100, 1)
M["top10_share_all_time_pct"] = round(alltime.head(10).sum() / by_year.sum() * 100, 1)
M["top5_share_2023_pct"] = round(real["2023"].nlargest(5).sum() / by_year["2023"] * 100, 1)
M["top10_names_all_time"] = {k: int(v) for k, v in alltime.head(10).items()}
M["other_or_test_units"] = int(sales[~sales.is_real_maker][Y].sum().sum())

# ---------------------------------------------------------------- choosing k, and checking it holds up
X = scaler.transform(est[lib.FEATURES])
rng = np.random.default_rng(0)
rows = []
for k in range(2, 8):
    full = KMeans(k, n_init=30, random_state=lib.SEED).fit(X)
    aris = []
    for _ in range(30):                                   # refit on a random 80% and compare on those same makers
        idx = rng.choice(len(X), int(len(X) * 0.8), replace=False)
        sub = KMeans(k, n_init=10, random_state=int(rng.integers(1e6))).fit(X[idx])
        aris.append(adjusted_rand_score(full.labels_[idx], sub.labels_))
    rows.append({"k": k, "silhouette": round(silhouette_score(X, full.labels_), 3), "stability_ari": round(float(np.mean(aris)), 3),
                 "inertia": round(float(full.inertia_), 1)})
ktab = pd.DataFrame(rows); ktab.to_csv(OUT / "choosing_k.csv", index=False)
M["choosing_k"] = rows
M["chosen_k"] = lib.K

# ---------------------------------------------------------------- the segments
order = lib.SEGMENT_ORDER + ["Long tail (under 1,000 units)"]
g = seg.groupby("segment").agg(makers=("units", "size"), units=("units", "sum"), median_units=("units", "median"),
                                recent_share=("recent_share", "mean"), now_vs_peak=("now_vs_peak", "median"),
                                growth_2023=("growth_2023", "median"), first_year=("first_year", "median")).reindex(order)
g["share_of_units_pct"] = (g.units / g.units.sum() * 100).round(1)
g["units_2023"] = seg.groupby("segment").units_2023.sum().reindex(order)
g["share_of_2023_pct"] = (g.units_2023 / g.units_2023.sum() * 100).round(1)
g.round(2).to_csv(OUT / "segment_profiles.csv")
M["segments"] = {s: {k: (round(float(v), 2) if pd.notna(v) else None) for k, v in r.items()} for s, r in g.iterrows()}
M["segment_category_mix"] = est.groupby("segment").main_category.value_counts().unstack(fill_value=0).to_dict("index")
seg.sort_values("units", ascending=False)[["units", "segment", "main_category", "first_year", "best_year", "units_2022", "units_2023",
                                           "units_2024_part", "now_vs_peak", "growth_2023", "recent_share"]].round(3).to_csv(OUT / "maker_segments.csv")

leaders = seg[seg.segment == "Market leaders"]
fallen = leaders[leaders.now_vs_peak < 0.6].sort_values("units", ascending=False)
M["leaders_fallen"] = {"count": int(len(fallen)), "of": int(len(leaders)),
                       "names": fallen.index.tolist(),
                       "top3": {n: {"now_vs_peak_pct": round(float(r.now_vs_peak) * 100), "best_year": int(r.best_year),
                                    "units_2022": int(r.units_2022), "units_2023": int(r.units_2023)} for n, r in fallen.head(3).iterrows()}}
M["leaders_top6"] = {n: int(u) for n, u in leaders.units.sort_values(ascending=False).head(6).items()}
M["challengers_top6"] = {n: int(u) for n, u in seg[seg.segment == "New challengers"].units.sort_values(ascending=False).head(6).items()}
M["fast_growers_2023"] = {n: round(float(np.exp(r.growth_2023)), 1) for n, r in
                          est[est.units_2023 >= 1000].sort_values("growth_2023", ascending=False).head(5).iterrows()}

# ---------------------------------------------------------------- context tables: registrations, chargers, plants
reg = pd.read_csv(lib.CLEAN / "ev_registrations_monthly.csv", parse_dates=["date"]).set_index("date")
allv = pd.read_csv(lib.CLEAN / "all_vehicle_registrations.csv").set_index("vehicle_class").total_registrations
ev_total = reg.sum()
two = ev_total[["Two Wheeler(Nt)", "Two Wheeler(T)"]].sum(); three = ev_total[["Three Wheeler(Nt)", "Three Wheeler(T)"]].sum(); lmv = ev_total["Light Motor Vehicle"]
two_all = allv[["Two Wheeler(Nt)", "Two Wheeler(T)"]].sum(); three_all = allv[["Three Wheeler(Nt)", "Three Wheeler(T)"]].sum(); lmv_all = allv["Light Motor Vehicle"]
M["ev_share_of_registered_vehicles_pct"] = {"Two-wheeler": round(two / two_all * 100, 2), "Three-wheeler": round(three / three_all * 100, 2),
                                           "Car / light vehicle": round(lmv / lmv_all * 100, 2)}
aug = reg[reg.index >= "2024-01-01"]
M["monthly_2024_last_month_units"] = int(aug.iloc[-1].sum()); M["monthly_2024_last_full_month_units"] = int(aug.iloc[-2].sum()); M["last_month"] = str(aug.index[-1].date())

st = pd.read_csv(lib.CLEAN / "charging_stations_by_state.csv"); loc = pd.read_csv(lib.CLEAN / "maker_locations.csv")
plants = loc.groupby("state").size().rename("maker_locations")
states = st.set_index("state").join(plants, how="outer").fillna(0).astype(int).sort_values("operational_stations", ascending=False)
states.to_csv(OUT / "states_chargers_and_makers.csv")
M["chargers_total"] = int(st.operational_stations.sum()); M["chargers_top5"] = {k: int(v) for k, v in states.operational_stations.head(5).items()}
M["chargers_top5_share_pct"] = round(states.operational_stations.head(5).sum() / st.operational_stations.sum() * 100, 1)
M["states_with_chargers"] = int(len(st)); M["maker_places_by_state"] = plants.sort_values(ascending=False).head(5).to_dict()
M["makers_in_states_with_no_charger_row"] = sorted(set(plants.index) - set(st.state))
json.dump(M, open(OUT / "metrics.json", "w"), indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o))

# ---------------------------------------------------------------- charts
# 1. the market
fig, ax = plt.subplots(figsize=(9, 4.8), dpi=160)
bottom = np.zeros(len(lib.YEARS)); xs = np.arange(len(lib.YEARS))
for c in ["Two-wheeler", "Three-wheeler", "Car / light vehicle"]:
    v = by_cat.loc[c].values / 1e3
    bars = ax.bar(xs, v, bottom=bottom, color=CAT_COLOUR[c], width=0.68, edgecolor=SURFACE, linewidth=1.5, label=c)
    bars[-1].set_hatch("////"); bars[-1].set_alpha(0.75)
    bottom += v
for i, t in enumerate(bottom):
    if i >= 5: ax.text(i, t + 20, f"{t/1e3:.2f}M" if t >= 1000 else f"{t:.0f}k", ha="center", fontsize=8.5, color=INK)
ax.set_xticks(xs, [str(y) if y != 2024 else "2024\n(to early Aug)" for y in lib.YEARS], fontsize=8.5)
ax.set_ylabel("EVs sold (thousands)"); tidy(ax)
ax.legend(frameon=False, loc="upper left", fontsize=9)
ax.set_title("India's EV sales by vehicle type, 2015 to 2024", loc="left", fontsize=12.5, fontweight="bold", pad=12)
fig.tight_layout(); fig.savefig(OUT / "01_market_by_vehicle_type.png", facecolor=SURFACE); plt.close(fig)

# 2. concentration
fig, ax = plt.subplots(figsize=(9, 4.6), dpi=160)
share = (alltime / by_year.sum() * 100).cumsum().values
ax.plot(np.arange(1, len(share) + 1), share, color="#2a78d6", lw=2.2)
ax.set_xscale("log"); ax.set_ylim(0, 105); tidy(ax)
for n in (5, 10, len(leaders)):
    ax.plot([n], [share[n - 1]], "o", color="#2a78d6", ms=7, mec=SURFACE, mew=2)
    ax.annotate(f"top {n}: {share[n-1]:.0f}% of all EVs sold", (n, share[n - 1]), textcoords="offset points",
                xytext=(10, -16), fontsize=9.5, color=INK)
ax.set_xlabel("Number of makers, biggest first (log scale)"); ax.set_ylabel("Cumulative share of units sold (%)")
ax.set_title("A few makers sell most of the EVs", loc="left", fontsize=12.5, fontweight="bold", pad=12)
fig.tight_layout(); fig.savefig(OUT / "02_concentration.png", facecolor=SURFACE); plt.close(fig)

# 3. segments map: size against how 2023 compared with 2022
fig, ax = plt.subplots(figsize=(9.5, 5.6), dpi=160)
ratio = lambda d: (d.units_2023 + 20) / (d.units_2022 + 20)
for s_ in lib.SEGMENT_ORDER:
    d = seg[seg.segment == s_]
    ax.scatter(d.units, ratio(d), s=34, color=SEG_COLOUR[s_], alpha=0.85, edgecolor=SURFACE, linewidth=0.8, label=f"{s_} ({len(d)})")
ax.set_xscale("log"); ax.set_yscale("log"); tidy(ax)
ax.axhline(1, color=MUTED, lw=1, ls=(0, (4, 3)))
ax.set_yticks([0.1, 0.3, 1, 3, 10, 30]); ax.set_yticklabels(["0.1x", "0.3x", "1x", "3x", "10x", "30x"])
ax.set_xlabel("Total EVs sold, 2015 to 2024 (log scale)"); ax.set_ylabel("2023 sales compared with 2022 (log scale)")
for n, dx, dy, ha in [("Ola Electric Technologies", -8, 8, "right"), ("Hero Electric Vehicles", 8, -4, "left"), ("Okinawa Autotech", 8, -12, "left"), ("Greaves Electric Mobility", 8, 6, "left")]:
    if n in seg.index:
        r = seg.loc[n]; ax.annotate(n.replace(" Technologies", ""), (r.units, (r.units_2023 + 20) / (r.units_2022 + 20)), textcoords="offset points", xytext=(dx, dy), fontsize=8.5, ha=ha)
ax.legend(frameon=False, fontsize=8.5, loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=4, handletextpad=0.2, columnspacing=1.2)
ax.set_title("The four segments of EV makers", loc="left", fontsize=12.5, fontweight="bold", pad=34)
fig.tight_layout(); fig.savefig(OUT / "03_segments_map.png", facecolor=SURFACE); plt.close(fig)

# 4. makers vs units by segment
fig, axes = plt.subplots(1, 2, figsize=(10, 4.4), dpi=160, sharey=True)
lab = ["Market\nleaders", "Steady\nmid-sized", "New\nchallengers", "Faded\nplayers", "Long tail"]
for ax, col, ttl in [(axes[0], "makers", "Number of makers"), (axes[1], "share_of_units_pct", "Share of all EVs sold (%)")]:
    vals = g[col].values; ax.barh(range(5), vals, color=[SEG_COLOUR[s_] for s_ in order], height=0.62)
    ax.set_yticks(range(5), lab, fontsize=9); ax.invert_yaxis(); ax.set_title(ttl, loc="left", fontsize=10.5, color=MUTED)
    for i, v in enumerate(vals): ax.text(v + max(vals) * 0.015, i, f"{v:,.0f}" if col == "makers" else f"{v:.1f}%", va="center", fontsize=9.5)
    ax.set_xlim(0, max(vals) * 1.18); ax.grid(False)
fig.suptitle("Few makers, most of the sales", x=0.01, ha="left", fontsize=12.5, fontweight="bold")
fig.tight_layout(); fig.savefig(OUT / "04_segment_sizes.png", facecolor=SURFACE); plt.close(fig)

# 5. how k was chosen
fig, ax = plt.subplots(figsize=(7.4, 4), dpi=160)
ax.plot(ktab.k, ktab.silhouette, "-o", color="#2a78d6", lw=2, ms=7, mec=SURFACE, mew=2, label="Silhouette (how separate the groups are)")
ax.plot(ktab.k, ktab.stability_ari, "-o", color="#eb6834", lw=2, ms=7, mec=SURFACE, mew=2, label="Stability (same groups on a re-sample)")
ax.axvline(lib.K, color=GRID, lw=6, zorder=0); tidy(ax); ax.set_ylim(0, 1.05); ax.set_xlabel("Number of segments (k)")
ax.legend(frameon=False, fontsize=8.5, loc="lower left"); ax.set_title("Choosing the number of segments", loc="left", fontsize=12, fontweight="bold", pad=10)
fig.tight_layout(); fig.savefig(OUT / "05_choosing_k.png", facecolor=SURFACE); plt.close(fig)

# 6. chargers
top = states.head(12).iloc[::-1]
fig, ax = plt.subplots(figsize=(8, 4.8), dpi=160)
ax.barh(top.index, top.operational_stations, color="#2a78d6", height=0.62)
for i, v in enumerate(top.operational_stations): ax.text(v + 25, i, f"{v:,}", va="center", fontsize=9)
ax.set_xlim(0, top.operational_stations.max() * 1.12); ax.grid(False); ax.set_xlabel("Operational public charging stations")
ax.set_title("Charging stations by state: the top 12", loc="left", fontsize=12.5, fontweight="bold", pad=12)
fig.tight_layout(); fig.savefig(OUT / "06_chargers_by_state.png", facecolor=SURFACE); plt.close(fig)

print(json.dumps({k: M[k] for k in ["units_total", "growth_2022_to_2023_pct", "top5_share_all_time_pct", "top10_share_all_time_pct", "top5_share_2023_pct",
                                      "n_established", "n_long_tail", "established_share_of_units_pct", "single_category_makers_pct"]}, indent=1))
print(ktab.to_string(index=False)); print(g.round(2).to_string())
print("fallen leaders:", M["leaders_fallen"]["count"], "of", M["leaders_fallen"]["of"], M["leaders_fallen"]["names"])
print(M["ev_share_of_registered_vehicles_pct"], M["chargers_total"], M["chargers_top5"], M["chargers_top5_share_pct"], M["makers_in_states_with_no_charger_row"], M["maker_places_by_state"])
