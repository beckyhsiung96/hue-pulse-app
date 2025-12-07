import streamlit as st
import pandas as pd
import altair as alt
import os
import glob

# ================= CONFIGURATION =================
CSV_FILE = "workspace_dev/FINAL_AUDIT_V7_BUGS.csv"
IMAGE_ROOT = "output_slices"
# =================================================

st.set_page_config(layout="wide", page_title="Hue QA Dashboard")

# CSS
st.markdown("""
<style>
    .bug-card {
        background-color: #FFF5F5;
        border: 1px solid #ffcccc;
        padding: 15px; border-radius: 8px;
        text-align: center;
    }
    .bug-count { font-size: 28px; font-weight: 800; color: #dc3545; }
    .bug-label { font-size: 14px; font-weight: 600; color: #888; text-transform: uppercase; }
    h2 { border-bottom: 2px solid #dc3545; padding-bottom: 10px; margin-top: 30px; }
</style>
""", unsafe_allow_html=True)

@st.cache_data
def load_data():
    if not os.path.exists(CSV_FILE): return None
    return pd.read_csv(CSV_FILE)

@st.cache_resource
def get_image_map():
    image_map = {}
    for path in glob.glob(f"{IMAGE_ROOT}/**/*.png", recursive=True):
        image_map[os.path.basename(path)] = path
    return image_map

df = load_data()
img_map = get_image_map()

# ================= SIDEBAR =================
st.sidebar.header("🔍 Filters")
if df is not None:
    # Industry Filter
    industries = ["All"] + sorted(df['Industry'].unique().tolist())
    sel_ind = st.sidebar.selectbox("Industry", industries)
    if sel_ind != "All": df = df[df['Industry'] == sel_ind]
    
    # Source Filter
    sources = ["All"] + sorted(df['Source'].unique().tolist())
    sel_src = st.sidebar.selectbox("Source", sources)
    if sel_src != "All": df = df[df['Source'] == sel_src]
else:
    st.error(f"Waiting for {CSV_FILE}...")
    st.stop()

# ================= DATA PREP =================
# Identify Bug Columns (columns ending in _Bugs)
bug_cols = [c for c in df.columns if "_Bugs" in c]

# Calculate "Defect Rate" (Percentage of logos with Score 1 in that category)
defect_rates = {}
total_logos = len(df)

all_bugs_list = []

for col in bug_cols:
    score_col = col.replace("_Bugs", "_Score")
    # Count how many have Score == 1
    fail_count = len(df[df[score_col] == 1])
    defect_rates[col.replace("_Bugs", "")] = (fail_count / total_logos) * 100
    
    # Collect individual bug tags for the Pareto chart
    # We look at rows where the string is not "None" and is not NaN
    bugs_series = df[col].dropna()
    bugs_series = bugs_series[bugs_series != "None"]
    
    for bug_str in bugs_series:
        if not isinstance(bug_str, str): continue
        # Split "Bug1|Bug2" into list
        tags = bug_str.split("|")
        for tag in tags:
            all_bugs_list.append({"Category": col.replace("_Bugs",""), "Bug": tag})

# ================= DASHBOARD UI =================
st.title("🐞 Hue QA Dashboard (V7)")
st.markdown("**Goal:** Eliminate Critical Bugs (Score 1). Focus on Engineering Fixes.")

# --- 1. THE "KILL ZONE" (Defect Rates) ---
st.markdown("## 🚨 Defect Rate by Category")
st.caption(f"% of {total_logos} logos containing at least one critical bug.")

cols = st.columns(6)
cats = ["Layout", "Text", "Color", "Icon", "Container", "Cohesiveness"]

for i, cat in enumerate(cats):
    rate = defect_rates.get(cat, 0)
    with cols[i]:
        st.markdown(f"""
        <div class="bug-card">
            <div class="bug-label">{cat}</div>
            <div class="bug-count">{rate:.1f}%</div>
            <div>Failure Rate</div>
        </div>
        """, unsafe_allow_html=True)

st.divider()

# --- 2. THE PARETO CHART (Specific Bugs) ---
st.markdown("## 📉 Top Bugs (Prioritization)")
c1, c2 = st.columns([2, 1])

if all_bugs_list:
    bug_df = pd.DataFrame(all_bugs_list)
    bug_counts = bug_df['Bug'].value_counts().reset_index()
    bug_counts.columns = ['Bug Name', 'Count']
    bug_counts['Percentage'] = (bug_counts['Count'] / total_logos) * 100
    
    with c1:
        st.markdown("### Most Frequent Bug Types")
        chart = alt.Chart(bug_counts.head(10)).mark_bar().encode(
            x=alt.X('Count'),
            y=alt.Y('Bug Name', sort='-x'),
            color=alt.value('#dc3545'),
            tooltip=['Bug Name', 'Count', alt.Tooltip('Percentage', format='.1f')]
        ).properties(height=400)
        st.altair_chart(chart, use_container_width=True)
        
    with c2:
        st.markdown("### Action Plan")
        top_bug = bug_counts.iloc[0]
        st.error(f"🔥 **Top Priority:** {top_bug['Bug Name']}")
        st.write(f"Occurs in **{top_bug['Count']}** logos ({top_bug['Percentage']:.1f}% of total).")
        st.write("Fixing this one bug yields the highest ROI.")

else:
    st.success("No bugs found! Perfect run.")

st.divider()

# --- 3. VISUAL EVIDENCE ---
st.markdown("## 🔬 Evidence Locker")

# Filter controls
filter_bug_type = st.selectbox("Filter by Bug Type", ["All"] + sorted(bug_df['Bug'].unique().tolist()) if all_bugs_list else [])

failures = []
# Re-scan to find filenames matching the filter
for idx, row in df.iterrows():
    row_bugs = []
    for col in bug_cols:
        val = row[col]
        if val != "None" and isinstance(val, str):
            tags = val.split("|")
            # If filter is applied, check if tag matches
            if filter_bug_type == "All" or filter_bug_type in tags:
                row_bugs.extend(tags)
    
    if row_bugs:
        failures.append({
            "Filename": row['Filename'],
            "Bugs": list(set(row_bugs)), # Dedup
            "Source": row['Source']
        })

if failures:
    st.caption(f"Showing {len(failures)} examples.")
    # Grid Layout
    for i in range(0, len(failures), 3):
        cols = st.columns(3)
        for j in range(3):
            if i + j < len(failures):
                item = failures[i+j]
                with cols[j]:
                    img_path = img_map.get(item['Filename'])
                    if img_path: 
                        st.image(img_path, use_container_width=True)
                    else: 
                        st.warning("Image missing")
                    
                    st.markdown(f"**{item['Source']}**")
                    # Display tags as red badges
                    for bug in item['Bugs']:
                        st.markdown(f"<span style='background:#ffe6e6; color:#b30000; padding:2px 6px; border-radius:4px; font-size:12px; margin-right:4px;'>{bug}</span>", unsafe_allow_html=True)
                    st.divider()
else:
    st.info("No logos match this bug filter.")
