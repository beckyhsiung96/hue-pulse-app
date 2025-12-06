import streamlit as st
import pandas as pd
import altair as alt
import os

# ================= CONFIGURATION =================
CSV_FILE = "SYSTEM_AUDIT_REPORT.csv"
# =================================================

st.set_page_config(layout="wide", page_title="Hue vs Looka: Audit Dashboard")

# CSS for "Scorecards"
st.markdown("""
<style>
    .metric-card {
        background-color: #f9f9f9;
        border: 1px solid #ddd;
        padding: 15px;
        border-radius: 8px;
        text-align: center;
    }
    .metric-value { font-size: 24px; font-weight: bold; color: #333; }
    .metric-label { font-size: 14px; color: #666; }
    .win { color: #28a745; }
    .loss { color: #dc3545; }
</style>
""", unsafe_allow_html=True)

# @st.cache_data  <-- REMOVED to force reload on refresh
def load_data():
    if not os.path.exists(CSV_FILE):
        return None
    return pd.read_csv(CSV_FILE)

df = load_data()

# ================= SIDEBAR CONTROLS =================
st.sidebar.title("🎛️ Audit Controls")

if st.sidebar.button("🔄 Reload Data"):
    st.cache_data.clear()
    st.rerun()

if df is not None:
    # Debug Info
    st.sidebar.markdown("---")
    st.sidebar.metric("Total Rows", len(df))
    st.sidebar.metric("Hue Rows", len(df[df['Source'] == 'Hue']))
    st.sidebar.metric("Looka Rows", len(df[df['Source'] == 'Looka']))
    st.sidebar.markdown("---")

if df is not None:
    # Industry Filter
    all_industries = ["All"] + sorted(df['Industry'].unique().tolist())
    selected_industry = st.sidebar.selectbox("Filter by Industry", all_industries)
    
    # Filter Data
    if selected_industry != "All":
        df_filtered = df[df['Industry'] == selected_industry]
    else:
        df_filtered = df
else:
    st.error(f"Waiting for {CSV_FILE}... Run 02_auditor_v3.py first!")
    st.stop()

# ================= MAIN DASHBOARD =================
st.title("🚀 Launch Readiness: Hue vs. Looka")
st.markdown("### The 'Gap Analysis' Report")

# 1. HIGH LEVEL SCORECARD
st.subheader("1. The Scoreboard (Average 1-5)")

# Calculate Means by Source
score_cols = [c for c in df.columns if "_Score" in c]
avg_scores = df_filtered.groupby('Source')[score_cols].mean().round(2).T.reset_index()

# Dynamic Column Renaming (Fixes crash if only one source exists)
avg_scores.rename(columns={'index': 'Category'}, inplace=True)

# Ensure both Hue and Looka columns exist
for source in ['Hue', 'Looka']:
    if source not in avg_scores.columns:
        avg_scores[source] = 0

avg_scores['Gap'] = avg_scores['Hue'] - avg_scores['Looka']

# Display Metrics
cols = st.columns(4)
categories = avg_scores['Category'].tolist()

# Highlight top 4 most critical categories
key_cats = ['VisualAppeal_Score', 'SemanticRelevance_Score', 'Composition_Score', 'Iconography_Score']

for i, cat in enumerate(key_cats):
    row = avg_scores[avg_scores['Category'] == cat]
    if not row.empty:
        hue_score = row['Hue'].values[0]
        gap = row['Gap'].values[0]
        label = cat.replace("_Score", "").replace("VisualAppeal", "✨ Visual Appeal").replace("SemanticRelevance", "🧠 Logic")
        
        with cols[i]:
            st.metric(label, f"{hue_score}/5", delta=f"{gap:+.2f} vs Looka")

st.divider()

# 2. DETAILED COMPARISON CHART
c1, c2 = st.columns([2, 1])

with c1:
    st.markdown("#### 📊 Head-to-Head Performance")
    # Reshape for Altair
    chart_data = avg_scores.melt(id_vars=['Category', 'Gap'], value_vars=['Hue', 'Looka'], var_name='Source', value_name='Score')
    
    chart = alt.Chart(chart_data).mark_bar().encode(
        y=alt.Y('Category', sort='-x'),
        x='Score',
        color=alt.Color('Source', scale=alt.Scale(domain=['Hue', 'Looka'], range=['#FF4B4B', '#333333'])),
        yOffset='Source'
    ).properties(height=400)
    
    st.altair_chart(chart, use_container_width=True)

with c2:
    st.markdown("#### 🏆 Where We Win vs. Lose")
    wins = avg_scores[avg_scores['Gap'] > 0]
    losses = avg_scores[avg_scores['Gap'] < 0]
    
    if not wins.empty:
        st.success(f"**Winning in:** {', '.join([c.replace('_Score','') for c in wins['Category'].tolist()])}")
    else:
        st.warning("No clear wins yet.")
        
    if not losses.empty:
        st.error(f"**Losing in:** {', '.join([c.replace('_Score','') for c in losses['Category'].tolist()])}")

st.divider()

# 3. ENGINEERING BACKLOG (The Action Items)
st.subheader("🛠️ The Fix List (Actionable Tickets)")

# Tabs for different Views
tab1, tab2 = st.tabs(["🔥 Critical Failures (Score 1-2)", "📦 All Tickets"])

with tab1:
    st.markdown("These are **Launch Blockers**. Filters for Hue logos with Score < 3.")
    
    # Filter for Hue Low Scores
    bad_hue = df_filtered[df_filtered['Source'] == 'Hue']
    
    # Unpivot to find specific failures
    fix_cols = [c for c in df.columns if "_Fix" in c]
    score_map = {c.replace("_Fix", "_Score"): c for c in fix_cols}
    
    failures = []
    for idx, row in bad_hue.iterrows():
        for score_col, fix_col in score_map.items():
            if row[score_col] <= 2: # THRESHOLD FOR FAILURE
                failures.append({
                    "Industry": row['Industry'],
                    "Category": score_col.replace("_Score", ""),
                    "Score": row[score_col],
                    "The Fix": row[fix_col],
                    "Filename": row['Filename']
                })
    
    if failures:
        fail_df = pd.DataFrame(failures)
        st.dataframe(fail_df, use_container_width=True)
        
        # Download Button
        csv = fail_df.to_csv(index=False).encode('utf-8')
        st.download_button("Download Tickets CSV", csv, "hue_fix_tickets.csv", "text/csv")
    else:
        st.info("No critical failures found! (Or Hue data missing)")

with tab2:
    st.markdown("Full raw data for deep diving.")
    st.dataframe(df_filtered)