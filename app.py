"""EV market segmentation: a small Streamlit app.

Run locally:  streamlit run app.py
"""
import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
import lib  # noqa: E402

st.set_page_config(page_title="India EV Market Segments", page_icon="⚡", layout="wide")


@st.cache_data
def load_everything():
    sales = lib.load_sales()
    makers = lib.maker_table(sales)
    seg, scaler, km, names = lib.fit_segments(makers)
    metrics = json.load(open(ROOT / "outputs" / "metrics.json"))
    states = pd.read_csv(ROOT / "outputs" / "states_chargers_and_makers.csv")
    return sales, seg, metrics, states


@st.cache_resource
def load_model():
    makers = lib.maker_table(lib.load_sales())
    _, scaler, km, names = lib.fit_segments(makers)
    return scaler, km, names


sales, seg, M, states = load_everything()
OUT = ROOT / "outputs"

st.title("⚡ India's EV makers: who sells, who is growing, who has faded")
st.caption("I grouped about 1,150 EV makers into segments using their sales from 2015 to early August 2024. "
           "This is sales data about makers, not data about buyers.")

tab1, tab2, tab3, tab4, tab5 = st.tabs(["Market overview", "The segments", "Look up a maker", "Check a maker", "Charging stations"])

# ------------------------------------------------------------------ 1
with tab1:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("EVs sold, 2015 to Aug 2024", f"{M['units_total']/1e6:.2f} million")
    c2.metric("Growth, 2022 to 2023", f"{M['growth_2022_to_2023_pct']:.0f}%")
    c3.metric("Top 5 makers' share of 2023 sales", f"{M['top5_share_2023_pct']:.0f}%")
    c4.metric("Makers that sold at least 1,000 EVs", f"{M['n_established']}")
    st.image(str(OUT / "01_market_by_vehicle_type.png"))
    st.write("Two-wheelers and three-wheelers are almost all of the market. Cars are still a small slice. "
             "The hatched 2024 bar is only about seven months of data, so it is not a fall.")
    st.image(str(OUT / "02_concentration.png"))

# ------------------------------------------------------------------ 2
with tab2:
    st.subheader("Four kinds of EV maker")
    prof = pd.read_csv(OUT / "segment_profiles.csv", index_col=0)
    for name in lib.SEGMENT_ORDER:
        r = prof.loc[name]
        st.markdown(f"**{name}**: {int(r.makers)} makers, {r.share_of_units_pct:.1f}% of all EVs sold. {lib.SEGMENT_BLURB[name]}")
    st.image(str(OUT / "03_segments_map.png"))
    st.image(str(OUT / "04_segment_sizes.png"))
    shown = prof[["makers", "share_of_units_pct", "median_units", "first_year"]].rename(columns={
        "makers": "Makers", "share_of_units_pct": "Share of all EVs sold (%)", "median_units": "Typical maker's total units", "first_year": "Typical first year"})
    st.dataframe(shown)
    st.caption("Makers with under 1,000 units in total are kept out of the clustering and shown as the long tail.")

# ------------------------------------------------------------------ 3
with tab3:
    st.subheader("Look up a maker")
    pick_seg = st.selectbox("Segment", ["All"] + lib.SEGMENT_ORDER + ["Long tail (under 1,000 units)"])
    pool = seg if pick_seg == "All" else seg[seg.segment == pick_seg]
    pool = pool.sort_values("units", ascending=False)
    maker = st.selectbox("Maker (biggest first)", pool.index.tolist())
    r = seg.loc[maker]
    a, b, c = st.columns(3)
    a.metric("Segment", r.segment)
    b.metric("Total EVs sold", f"{int(r.units):,}")
    c.metric("Main vehicle type", r.main_category)
    yearly = sales[(sales.maker == maker) & sales.is_real_maker][lib.YCOLS].sum()
    yearly.index = [f"{y}*" if y == "2024" else y for y in yearly.index]
    st.bar_chart(yearly)
    st.caption("*2024 is only about seven months. Best year: "
               f"{int(r.best_year)}. First year with sales: {int(r.first_year)}.")
    peers = seg[(seg.segment == r.segment) & (seg.index != maker)].sort_values("units", ascending=False).head(8)
    if len(peers):
        st.write("Other makers in the same segment:")
        st.dataframe(peers[["units", "main_category", "first_year"]].rename(columns={"units": "Total units", "main_category": "Main type", "first_year": "First year"}))

# ------------------------------------------------------------------ 4
with tab4:
    st.subheader("Which segment would this maker fall into?")
    st.write("Type in a maker's numbers. The app finds the closest segment centre. Try it with a real maker's numbers from the lookup tab.")
    c1, c2 = st.columns(2)
    first_year = c1.number_input("First year with sales", 2015, 2024, 2021)
    total = c1.number_input("Total EVs sold so far", 1000, 2000000, 5000, step=500)
    best = c1.number_input("Units in the maker's best year", 1, 2000000, 2500, step=250)
    u22 = c2.number_input("Units sold in 2022", 0, 2000000, 800, step=100)
    u23 = c2.number_input("Units sold in 2023", 0, 2000000, 2500, step=100)
    recent = c2.number_input("Units sold in 2022 to 2024 combined", 0, 2000000, 4500, step=500)
    if st.button("Find the segment"):
        scaler, km, names = load_model()
        out = lib.assign_new_maker(scaler, km, names, first_year, u22, u23, total, best, recent)
        st.success(f"Closest segment: {out}")
        st.write(lib.SEGMENT_BLURB[out])
        if total < lib.ESTABLISHED_MIN_UNITS:
            st.warning("Under 1,000 units in total, the maker would count as long tail instead.")

# ------------------------------------------------------------------ 5
with tab5:
    st.subheader("Public charging stations by state")
    st.metric("Operational stations in the data", f"{M['chargers_total']:,}")
    st.write(f"The top five states have {M['chargers_top5_share_pct']:.0f}% of all stations.")
    st.bar_chart(states.set_index("state")["operational_stations"].sort_values(ascending=False).head(15))
    st.caption("There is no state-level sales data here, so I can't say whether stations match where people buy EVs.")
