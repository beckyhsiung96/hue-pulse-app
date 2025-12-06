import streamlit as st
import pandas as pd
import altair as alt
import os

# ================= CONFIGURATION =================
CSV_FILE = "FINAL_AUDIT_V4_PRODUCT.csv"
# =================================================

st.set_page_config(layout="wide", page_title="Hue Product Audit")

# Custom CSS for the "Scorecard" look
st.markdown("""
<style>
    .metric-container {
        background-color: #FFFFFF;
        border: 1px solid #E0E0E0;
        padding: 15px;
        border-radius: 10px;
        text-align: center;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .metric-label {
        font-size: 14px;
        font-weight: 600;
        color: #666;
        text-transform: uppercase;
        margin-bottom: 5px;
    }
    .metric-value {
        font-size: 32px;
        font-weight: 800;
        color: #333;
    }
    .metric-delta {
        font-size: 14px;
        font-weight: 500;
    }
    .positive { color: #28a745; }
    .negative { color: #dc3545; }
    .neutral { color: #6c757d; }
    
    /* Section Headers */
    h2 {
        font-size: 18px;
        color: #444;
        border-bottom: 2px solid #ff4b4b;
        padding-bottom: 10px;
        margin-top: 30px;
        margin-bottom: 20px;
    }
</style>
""", unsafe_allow_html=True)

# @st.cache_data
def load_data():
    if not os.path.exists(CSV_FILE): return None
    return pd.read_csv(CSV_FILE)

df = load_data()

# ================= SIDEBAR FILTERS =================
st.sidebar.header("🔍 Advanced Filters")

if df is not None:
    def checkbox_filter(label, col_name, icon=""):
        if col_name not in df.columns: return None
        options = sorted(df[col_name].dropna().unique().tolist())
        key_base = f"filter_{col_name}"
        
        # Expander acts as the "Dropdown"
        with st.sidebar.expander(f"{icon} {label}", expanded=False):
            # 1. Select All / Deselect All
            all_key = f"all_{key_base}"
            
            # Initialize Session State for these checkboxes if not exists
            if all_key not in st.session_state: st.session_state[all_key] = True
            for opt in options:
                opt_key = f"{key_base}_{opt}"
                if opt_key not in st.session_state: st.session_state[opt_key] = True

            # Callback to update all options when "Select All" is toggled
            def toggle_all():
                new_state = st.session_state[all_key]
                for opt in options:
                    st.session_state[f"{key_base}_{opt}"] = new_state
            
            st.checkbox("Select All", key=all_key, on_change=toggle_all)
            st.divider()
            
            # 2. Individual Checkboxes
            selected = []
            for opt in options:
                # We use session state keys to bind the value
                is_checked = st.checkbox(str(opt), key=f"{key_base}_{opt}")
                if is_checked:
                    selected.append(opt)
            
            return selected

    # 1. Execution Date
    sel_dates = checkbox_filter("Execution Date", "Audit_Date", "📅")
    if sel_dates is not None: df = df[df["Audit_Date"].isin(sel_dates)]

    # 2. Industry
    sel_ind = checkbox_filter("Industry", "Industry", "🏭")
    if sel_ind is not None: df = df[df["Industry"].isin(sel_ind)]

    # 3. Name Length
    sel_len = checkbox_filter("Name Length", "Name_Length", "📏")
    if sel_len is not None: df = df[df["Name_Length"].isin(sel_len)]

    # 4. Tagline
    sel_tag = checkbox_filter("Has Tagline", "Has_Tagline", "🏷️")
    if sel_tag is not None: df = df[df["Has_Tagline"].isin(sel_tag)]
    
    # --- LOGO COUNT SUMMARY ---
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🔢 Logo Count")
    
    hue_count = len(df[df['Source'] == 'Hue'])
    looka_count = len(df[df['Source'] == 'Looka'])
    
    if hue_count == looka_count:
        st.sidebar.caption(f"**{hue_count}** logos for each source")
    else:
        st.sidebar.caption(f"**{hue_count}** Hue logos")
        st.sidebar.caption(f"**{looka_count}** Looka logos")
   
else:
    st.error(f"Waiting for {CSV_FILE}...")
    st.stop()

# ================= DATA PREP (Scoped to Filters) =================
# Calculate Averages based on valid choices
score_cols = [c for c in df.columns if "_Score" in c]

if not df.empty:
    avg = df.groupby('Source')[score_cols].mean().round(2).T.reset_index()
    avg.columns = ['Category', 'Hue', 'Looka']
    if 'Hue' not in avg.columns: avg['Hue'] = 0
    if 'Looka' not in avg.columns: avg['Looka'] = 0
    avg['Gap'] = avg['Hue'] - avg['Looka']
else:
    st.warning("No data matches filters.")
    st.stop()

# Helper to render a custom metric card
def render_metric(col_obj, title, csv_col_name):
    row = avg[avg['Category'] == csv_col_name]
    if not row.empty:
        hue_val = row['Hue'].values[0]
        gap_val = row['Gap'].values[0]
        
        color_class = "positive" if gap_val > 0 else "negative" if gap_val < 0 else "neutral"
        sign = "+" if gap_val > 0 else ""
        
        col_obj.markdown(f"""
        <div class="metric-container">
            <div class="metric-label">{title}</div>
            <div class="metric-value">{hue_val}</div>
            <div class="metric-delta {color_class}">
                {sign}{gap_val:.2f} vs Looka
            </div>
        </div>
        """, unsafe_allow_html=True)

# ================= MAIN UI =================
st.title("🎨 Hue Product Quality Dashboard")

# ================= INSIGHTS (SCOPED) =================
with st.container():
    # Clean up category names for display
    avg['CleanCat'] = avg['Category'].str.replace('_Score', '').str.replace('IndustryRelevance', 'Relevance').str.title()
    
    # Sort by Gap to find extremes
    sorted_gaps = avg.sort_values('Gap')
    
    # 1. Biggest Gap (Lowest negative)
    worst = sorted_gaps.iloc[0]
    worst_cat = worst['CleanCat']
    worst_val = worst['Gap']
    
    # 2. Biggest Strength (Highest positive) - or "Least Bad" if all negative
    best = sorted_gaps.iloc[-1]
    best_cat = best['CleanCat']
    best_val = best['Gap']
    
    # Narrative Construction
    st.markdown("#### 💡 Audit Insights")
    
    c_insight1, c_insight2 = st.columns(2)
    
    with c_insight1:
        if worst_val < 0:
            st.error(f"📉 **Establish Parity:** Hue is struggling most with **{worst_cat}** ({worst_val:.2f} vs Looka). Focusing here will yield the biggest quality lift.")
        else:
            st.success("✅ **No Gaps:** Hue is leading or tied in every category!")

    with c_insight2:
        if best_val > 0:
            st.success(f"🏆 **Winning Edge:** Hue's standout strength is **{best_cat}** (+{best_val:.2f}). Leverage this in marketing!")
        elif best_val == 0:
            st.warning(f"⚖️ **Tough Market:** Hue is at best tied with Looka in **{best_cat}**.")
        else:
            st.warning(f"⚠️ **Trailing:** Even in its best category (**{best_cat}**), Hue is behind by {best_val:.2f}.")

    
    # (Chart moved to Deep Component Scan)

# --- SECTION 1: HIGH LEVEL AGGREGATION ---
st.markdown("#### 🧠 High Level Aggregation")
c1, c2, c3 = st.columns(3)

render_metric(c1, "Quality (Aesthetic)", "Quality_Score")
render_metric(c2, "Variety (Distinctness)", "Variety_Score")
render_metric(c3, "Industry Relevance", "IndustryRelevance_Score")

# --- SECTION 2: DEEP COMPONENT SCAN ---
st.markdown("#### 🔬 Deep Component Scan")
d1, d2, d3, d4, d5 = st.columns(5)

render_metric(d1, "Layout", "Layout_Score")
render_metric(d2, "Font", "Font_Score")
render_metric(d3, "Color", "Color_Score")
render_metric(d4, "Icon", "Icon_Score")
render_metric(d5, "Container", "Container_Score")

st.divider()

# --- MERGED CHART WITH SORTING ---
st.markdown("#### 📊 Head-to-Head Performance")

col_sort, col_chart = st.columns([1, 4])

with col_sort:
    sort_option = st.radio(
        "Sort By:",
        options=[
            "Gap: Biggest Struggle First",
            "Rating: Hue's Best",
            "Rating: Looka's Best"
        ]
    )

# Prepare sorted data
if "Struggle" in sort_option:
    # Gap ascending (negative gaps first)
    avg_sorted = avg.sort_values('Gap', ascending=True)
elif "Hue" in sort_option:
    # Hue descending
    avg_sorted = avg.sort_values('Hue', ascending=False)
else:
    # Looka descending
    avg_sorted = avg.sort_values('Looka', ascending=False)

sort_order = avg_sorted['CleanCat'].tolist()

# Prepare Altair data
chart_data = avg.melt(id_vars=['Category', 'CleanCat', 'Gap'], value_vars=['Hue', 'Looka'], var_name='Source', value_name='Score')

with col_chart:
    bars = alt.Chart(chart_data).mark_bar().encode(
        x=alt.X('CleanCat', axis=alt.Axis(labelAngle=0, title=None), sort=sort_order),
        y=alt.Y('Score', scale=alt.Scale(domain=[0, 5])),
        color=alt.Color('Source', scale=alt.Scale(domain=['Hue', 'Looka'], range=['#FF4B4B', '#333333'])),
        xOffset='Source',
        tooltip=['CleanCat', 'Source', 'Score', 'Gap']
    ).properties(height=320)
    
    st.altair_chart(bars, use_container_width=True)

st.write("") # Spacer


# --- SECTION 3: THE FIX LIST (UNCHANGED) ---
st.markdown("#### 🛠️ The Fix List (Actionable Tickets)")

tab1, tab2 = st.tabs(["🔥 Critical Failures (Score 1-2)", "📦 Full Raw Data"])

with tab1:
    st.markdown("Filter: **Hue** logos with Score **<= 2**. (Launch Blockers)")
    hue_df = df[df['Source'] == 'Hue']
    
    if hue_df.empty:
        st.info("No Hue data found.")
    else:
        fix_cols = [c for c in df.columns if "_Fix" in c]
        score_map = {c.replace("_Fix", "_Score"): c for c in fix_cols}
        
        failures = []
        for idx, row in hue_df.iterrows():
            for score_col, fix_col in score_map.items():
                if row[score_col] <= 2:
                    failures.append({
                        "Industry": row['Industry'],
                        "Category": score_col.replace("_Score", ""),
                        "Score": row[score_col],
                        "Action Item": row[fix_col],
                        "Filename": row['Filename']
                    })
        
        if failures:
            fail_df = pd.DataFrame(failures)
            st.dataframe(fail_df, use_container_width=True)
            csv = fail_df.to_csv(index=False).encode('utf-8')
            st.download_button("⬇️ Download Tickets (CSV)", csv, "hue_critical_fixes.csv", "text/csv")
        else:
            st.success("🎉 No critical failures found for Hue!")

with tab2:
    st.dataframe(df)