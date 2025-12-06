import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
import os
import glob

# ================= CONFIGURATION =================
CSV_FILE = "FINAL_AUDIT_V5_PRODUCT.csv"
IMAGE_ROOT = "output_slices"
# =================================================

st.set_page_config(layout="wide", page_title="Hue Product Audit V5")

# Custom CSS
st.markdown("""
<style>
    .metric-container {
        background-color: #FFFFFF;
        border: 1px solid #E0E0E0;
        padding: 15px;
        border-radius: 10px;
        text-align: center;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
        height: 100%;
    }
    .metric-label {
        font-size: 13px; font-weight: 700; color: #888;
        text-transform: uppercase; margin-bottom: 5px;
    }
    .metric-value { font-size: 28px; font-weight: 800; color: #222; }
    .metric-delta { font-size: 13px; font-weight: 500; }
    .positive { color: #28a745; }
    .negative { color: #dc3545; }
    .neutral { color: #6c757d; }
    .issue-box {
        background-color: #FFF5F5; border-left: 3px solid #dc3545;
        padding: 8px; margin-top: 10px; text-align: left;
        font-size: 12px; color: #555;
    }
    h2 {
        font-size: 20px; color: #111;
        border-bottom: 2px solid #ff4b4b; padding-bottom: 8px;
        margin-top: 30px; margin-bottom: 20px;
    }
</style>
""", unsafe_allow_html=True)

@st.cache_data
def load_data():
    if not os.path.exists(CSV_FILE): return None
    df = pd.read_csv(CSV_FILE)
    return df

@st.cache_resource
def get_image_map():
    image_map = {}
    for path in glob.glob(f"{IMAGE_ROOT}/**/*.png", recursive=True):
        filename = os.path.basename(path)
        image_map[filename] = path
    return image_map

df = load_data()
img_map = get_image_map()

# ================= SIDEBAR =================
st.sidebar.header("🔍 Filters")
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
    if "Name_Length" in df.columns:
        sel_len = checkbox_filter("Name Length", "Name_Length", "📏")
        if sel_len is not None: df = df[df["Name_Length"].isin(sel_len)]

    # 4. Tagline
    if "Has_Tagline" in df.columns:
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

# ================= HELPERS =================
# Calculate Averages (Pandas automatically skips NaNs, which is what we want)
score_cols = [c for c in df.columns if "_Score" in c]
avg = df.groupby('Source')[score_cols].mean().round(2).T.reset_index()
# Flexibly rename columns
avg = avg.rename(columns={'index': 'Category'})
if 'Category' not in avg.columns:
    # Fallback if index name was different
    avg.columns.values[0] = 'Category'

# Handle missing columns if data is partial
if 'Hue' not in avg.columns: avg['Hue'] = np.nan
if 'Looka' not in avg.columns: avg['Looka'] = np.nan

avg['Gap'] = avg['Hue'] - avg['Looka']

def get_top_issues(col_name):
    fix_col = col_name.replace("_Score", "_Fix")
    if fix_col not in df.columns: return []
    
    hue_issues = df[(df['Source'] == 'Hue') & (df[fix_col].notna()) & (df[fix_col] != "None")]
    if hue_issues.empty: return []
    return hue_issues[fix_col].value_counts().head(2).index.tolist()

def render_card(col_obj, title, csv_col_name):
    row = avg[avg['Category'] == csv_col_name]
    
    hue_val = "N/A"
    gap_display = ""
    issue_html = ""
    
    if not row.empty:
        h_score = row['Hue'].values[0]
        l_score = row['Looka'].values[0]
        gap = row['Gap'].values[0]
        
        # Check for NaN (which means no data for this category, e.g. no containers)
        if not pd.isna(h_score):
            hue_val = f"{h_score:.2f}"
            
            # Logic for coloring the gap
            if not pd.isna(gap):
                color_class = "positive" if gap > 0 else "negative" if gap < 0 else "neutral"
                sign = "+" if gap > 0 else ""
                gap_display = f"<div class='metric-delta {color_class}'>{sign}{gap:.2f} vs Looka</div>"
            
            # Issues
            top_issues = get_top_issues(csv_col_name)
            if top_issues and h_score < 4.0:
                issue_items = "".join([f"<li>{i}</li>" for i in top_issues])
                issue_html = f"<div class='issue-box'><b>Top Fixes:</b><ul style='margin:0; padding-left:15px;'>{issue_items}</ul></div>"
        else:
            gap_display = "<div class='metric-delta neutral'>No Data</div>"

    col_obj.markdown(f"""
    <div class="metric-container">
        <div class="metric-label">{title}</div>
        <div class="metric-value">{hue_val}</div>
        {gap_display}
        {issue_html}
    </div>
    """, unsafe_allow_html=True)

# ================= MAIN UI =================
st.title("🎨 Hue Product Quality Dashboard")

# 1. INSIGHTS
with st.container():
    avg['CleanCat'] = avg['Category'].str.replace('_Score', '').str.replace('IndustryRelevance', 'Relevance').str.title()
    sorted_gaps = avg.sort_values('Gap')
    worst = sorted_gaps.iloc[0]
    best = sorted_gaps.iloc[-1]
    
    st.markdown("#### 💡 Audit Insights")
    c_insight1, c_insight2 = st.columns(2)
    with c_insight1:
        if worst['Gap'] < 0:
            st.error(f"📉 **Establish Parity:** Hue is struggling most with **{worst['CleanCat']}** ({worst['Gap']:.2f} vs Looka). Focusing here will yield the biggest quality lift.")
        else:
            st.success("✅ **No Gaps:** Hue is leading or tied in every category!")
    with c_insight2:
        if best['Gap'] > 0:
            st.success(f"🏆 **Winning Edge:** Hue's standout strength is **{best['CleanCat']}** (+{best['Gap']:.2f}). Leverage this in marketing!")
        elif best['Gap'] == 0:
            st.warning(f"⚖️ **Tough Market:** Hue is at best tied with Looka in **{best['CleanCat']}**.")
        else:
            st.warning(f"⚠️ **Trailing:** Even in its best category (**{best['CleanCat']}**), Hue is behind by {best['Gap']:.2f}.")

# 2. HIGH LEVEL
st.markdown("## 🧠 High Level Aggregation")
c1, c2, c3 = st.columns(3)
render_card(c1, "Quality (Aesthetic)", "Quality_Score")
render_card(c2, "Variety (Distinctness)", "Variety_Score")
render_card(c3, "Industry Relevance", "IndustryRelevance_Score")

# 2. COMPONENT SCAN
st.markdown("## 🔬 Deep Component Scan")
d1, d2, d3, d4, d5 = st.columns(5)
render_card(d1, "Layout", "Layout_Score")
render_card(d2, "Font", "Font_Score")
render_card(d3, "Color", "Color_Score")
render_card(d4, "Icon", "Icon_Score")
render_card(d5, "Container", "Container_Score")

st.write("") 

# 3. WIN/LOSS CHART
with st.expander("📊 View Head-to-Head Chart", expanded=True):
    # Melt and drop NaNs for the chart
    chart_data = avg.melt(id_vars=['Category', 'Gap'], value_vars=['Hue', 'Looka'], var_name='Source', value_name='Score')
    chart_data = chart_data.dropna(subset=['Score'])
    
    chart_data['Category'] = chart_data['Category'].str.replace('_Score', '')
    
    bars = alt.Chart(chart_data).mark_bar().encode(
        x=alt.X('Category', axis=alt.Axis(labelAngle=0)),
        y=alt.Y('Score', scale=alt.Scale(domain=[0, 5])),
        color=alt.Color('Source', scale=alt.Scale(domain=['Hue', 'Looka'], range=['#FF4B4B', '#333333'])),
        xOffset='Source',
        tooltip=['Category', 'Source', 'Score']
    ).properties(height=320)
    st.altair_chart(bars, use_container_width=True)

# 4. STRATEGIC HEATMAP
st.markdown("## 🗺️ Strategic Industry Heatmap")
with st.expander("Explore Scores by Industry", expanded=True):
    # Prepare data: Group by Industry & Category (Hue only by default)
    if 'Industry' in df.columns:
        # User toggle
        h_source = st.radio("Show Scores For:", ["Hue", "Looka"], horizontal=True)
        
        heat_df = df[df['Source'] == h_source]
        if not heat_df.empty:
            # Group measure cols
            heat_avg = heat_df.groupby('Industry')[score_cols].mean().round(2).reset_index()
            # Melt
            heat_melt = heat_avg.melt(id_vars='Industry', var_name='Category', value_name='Score')
            heat_melt['Category'] = heat_melt['Category'].str.replace('_Score', '')
            
            heatmap = alt.Chart(heat_melt).mark_rect().encode(
                x=alt.X('Category', title=None),
                y=alt.Y('Industry', title=None),
                color=alt.Color('Score', scale=alt.Scale(domain=[1, 5], scheme='redyellowgreen')),
                tooltip=['Industry', 'Category', 'Score']
            ).properties(height=300)
            
            # Text overlay
            text = heatmap.mark_text(baseline='middle').encode(
                text='Score',
                color=alt.value('black')
            )
            
            st.altair_chart(heatmap + text, use_container_width=True)
        else:
            st.info(f"No data available for {h_source} to generate heatmap.")
    else:
        st.warning("Industry data missing.")

# 5. VISUAL REPAIR STATION
st.markdown("## 🛠️ Visual Repair Station")

tab1, tab2, tab3 = st.tabs(["🔥 Critical Visuals (Score 1-2)", "📈 The Pareto Chart", "📄 Raw Data"])

with tab1:
    st.markdown("**Focus:** Hue logos with Score <= 2.")
    hue_df = df[df['Source'] == 'Hue']
    if hue_df.empty:
        st.info("No Hue data found.")
    else:
        fix_cols = [c for c in df.columns if "_Fix" in c]
        failures = []
        for idx, row in hue_df.iterrows():
            for fix_col in fix_cols:
                score_col = fix_col.replace("_Fix", "_Score")
                # Check for nan and threshold
                if pd.notna(row[score_col]) and row[score_col] <= 2:
                    failures.append({
                        "Filename": row['Filename'],
                        "Category": score_col.replace("_Score", ""),
                        "Score": row[score_col],
                        "Fix": row[fix_col]
                    })
        
        if failures:
            failures = sorted(failures, key=lambda x: x['Score'])
            for i in range(0, len(failures), 3):
                cols = st.columns(3)
                for j in range(3):
                    if i + j < len(failures):
                        item = failures[i+j]
                        with cols[j]:
                            img_path = img_map.get(item['Filename'])
                            if img_path: st.image(img_path, use_container_width=True)
                            else: st.warning(f"Missing: {item['Filename']}")
                            st.error(f"**{item['Category']} (Score {int(item['Score'])})**")
                            st.caption(f"🔧 {item['Fix']}")
                            st.divider()
        else:
            st.success("🎉 Clean Sheet! No critical failures found.")

with tab2:
    st.markdown("**Most frequent issues:**")
    all_fixes = []
    fix_cols = [c for c in df.columns if "_Fix" in c]
    for col in fix_cols:
        # Filter out None and NaN
        fixes = df[(df['Source'] == 'Hue') & (df[col].notna()) & (df[col] != "None")][col].tolist()
        all_fixes.extend(fixes)
    
    if all_fixes:
        fix_counts = pd.Series(all_fixes).value_counts().reset_index()
        fix_counts.columns = ['Fix Description', 'Count']
        chart = alt.Chart(fix_counts.head(10)).mark_bar().encode(
            x='Count', y=alt.Y('Fix Description', sort='-x'), color=alt.value('#ff4b4b')
        )
        st.altair_chart(chart, use_container_width=True)
    else:
        st.info("No fixes recorded.")

with tab3:
    st.dataframe(df)