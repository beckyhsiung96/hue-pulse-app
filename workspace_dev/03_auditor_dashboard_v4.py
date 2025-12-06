import streamlit as st
import pandas as pd
import altair as alt
import os

# ================= CONFIGURATION =================
CSV_FILE = "FINAL_AUDIT_V4_PRODUCT.csv"
# =================================================

st.set_page_config(layout="wide", page_title="Hue Product Quality Dashboard")

# Custom CSS for "Executive" Feel
st.markdown("""
<style>
    .big-metric { font-size: 32px; font-weight: 800; color: #333; }
    .sub-metric { font-size: 16px; color: #666; }
    .stDataFrame { border-radius: 10px; }
    h1, h2, h3 { color: #111; }
</style>
""", unsafe_allow_html=True)

@st.cache_data
def load_data():
    if not os.path.exists(CSV_FILE): return None
    return pd.read_csv(CSV_FILE)

df = load_data()

# ================= SIDEBAR =================
st.sidebar.header("🔍 Filters")
if df is not None:
    industries = ["All"] + sorted(df['Industry'].unique().tolist())
    sel_ind = st.sidebar.selectbox("Industry", industries)
    if sel_ind != "All": df = df[df['Industry'] == sel_ind]
else:
    st.error(f"Please run '02_auditor_v4.py' to generate {CSV_FILE}")
    st.stop()

# ================= HEADER =================
st.title("🎨 Hue Product Quality Dashboard")
st.markdown("High-level comparison of Hue vs. Looka across 8 Product Dimensions.")
st.divider()

# ================= 1. THE 8-CATEGORY BATTLEFIELD =================
st.subheader("1. The 8-Category Comparison")

# Helper to prepare chart data
score_cols = [c for c in df.columns if "_Score" in c]
avg_scores = df.groupby('Source')[score_cols].mean().round(2).T.reset_index()
avg_scores.columns = ['Category', 'Hue', 'Looka']
if 'Hue' not in avg_scores.columns: avg_scores['Hue'] = 0
if 'Looka' not in avg_scores.columns: avg_scores['Looka'] = 0
avg_scores['Gap'] = avg_scores['Hue'] - avg_scores['Looka']

# Clean Names (Remove _Score)
avg_scores['Category_Clean'] = avg_scores['Category'].str.replace('_Score', '')

# Chart
chart_data = avg_scores.melt(id_vars=['Category_Clean'], value_vars=['Hue', 'Looka'], var_name='Source', value_name='Score')

# Grouped Bar Chart
bars = alt.Chart(chart_data).mark_bar().encode(
    x=alt.X('Category_Clean', title=None, axis=alt.Axis(labelAngle=0)),
    y=alt.Y('Score', title='Avg Score (1-5)', scale=alt.Scale(domain=[0, 5])),
    color=alt.Color('Source', scale=alt.Scale(domain=['Hue', 'Looka'], range=['#FF4B4B', '#333333'])),
    xOffset='Source',
    tooltip=['Category_Clean', 'Source', 'Score']
).properties(height=350)

st.altair_chart(bars, use_container_width=True)

# Win/Loss Text Summary
c1, c2 = st.columns(2)
with c1:
    wins = avg_scores[avg_scores['Gap'] > 0]
    if not wins.empty:
        st.success(f"**✅ Hue Wins In:** {', '.join(wins['Category_Clean'].tolist())}")
    else:
        st.info("Hue is currently trailing in all categories.")
with c2:
    losses = avg_scores[avg_scores['Gap'] < -0.5] # Only show significant losses
    if not losses.empty:
        st.error(f"**⚠️ Critical Gaps (>0.5):** {', '.join(losses['Category_Clean'].tolist())}")

st.divider()

# ================= 2. ACTION ITEM AGGREGATION =================
st.subheader("2. Priority Fixes (Aggregated)")
st.markdown("We analyzed the text of every 'Fix Ticket' to find the most common recurring issues.")

# Function to get top keywords/phrases from fix columns for Hue
def get_top_issues(category_col):
    fix_col = category_col.replace("_Score", "_Fix")
    hue_fixes = df[df['Source'] == 'Hue'][fix_col]
    # Simple aggregation: Filter out "None" and count exact strings
    # In a real NLP app we would tokenize, but exact string matching is safer for "Tickets"
    counts = hue_fixes[hue_fixes != "None"].value_counts().head(3)
    return counts

# Create a Grid of Top Issues
cats = [c for c in df.columns if "_Score" in c]
cols = st.columns(4) 
# Row 1
for i in range(4):
    cat = cats[i]
    with cols[i]:
        clean_name = cat.replace("_Score", "")
        st.markdown(f"**{clean_name}**")
        issues = get_top_issues(cat)
        if not issues.empty:
            for issue, count in issues.items():
                st.caption(f"• {issue} ({count})")
        else:
            st.caption("No major issues.")

st.write("") # Spacer

cols_2 = st.columns(4)
# Row 2
for i in range(4, 8):
    cat = cats[i]
    with cols_2[i-4]:
        clean_name = cat.replace("_Score", "")
        st.markdown(f"**{clean_name}**")
        issues = get_top_issues(cat)
        if not issues.empty:
            for issue, count in issues.items():
                st.caption(f"• {issue} ({count})")
        else:
            st.caption("No major issues.")

st.divider()

# ================= 3. DETAILED FIX LIST =================
st.subheader("3. 🛠️ The Fix List (Actionable Tickets)")

tab1, tab2 = st.tabs(["🔴 Critical (Score 1-2)", "📄 All Data"])

with tab1:
    st.markdown("Filter: **Hue** logos with Score **<= 2**.")
    hue_df = df[df['Source'] == 'Hue']
    
    failures = []
    # Identify fix columns
    fix_map = {c: c.replace("_Score", "_Fix") for c in score_cols}
    
    for idx, row in hue_df.iterrows():
        for score_col, fix_col in fix_map.items():
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
        st.download_button("Download Critical Fixes", csv, "hue_critical_fixes.csv", "text/csv")
    else:
        st.success("No critical failures found for Hue!")

with tab2:
    st.dataframe(df)