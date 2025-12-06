import streamlit as st
import os
import random
import pandas as pd
import glob
import base64
import altair as alt
# ⚠️ ENSURE YOU HAVE INSTALLED: pip install st-click-detector
from st_click_detector import click_detector

# ================= CONFIGURATION =================
INPUT_ROOT = "output_slices"
RESULTS_FILE = "human_pulse_results.csv"

BRAND_INFO = {
    "Coffee Shop": {"name": "River Roasters", "tagline": "", "industry": "Coffee Shop"},
    "Real Estate": {"name": "Oakwood Heritage Properties", "tagline": "Est. 1985", "industry": "Real Estate"},
    "Software": {"name": "Nexalis", "tagline": "", "industry": "Software Technology"},
    "Construction": {"name": "Ironclad Construction", "tagline": "", "industry": "Construction"},
    "Beauty Spa": {"name": "Luna & Sol", "tagline": "Holistic Wellness", "industry": "Beauty & Spa"}
}

# ================= HELPER: IMAGE ENCODING =================
def get_image_html(file_path, unique_id):
    """
    Converts a local image to a Base64 string so it can be clicked in HTML.
    """
    with open(file_path, "rb") as f:
        data = f.read()
    b64_data = base64.b64encode(data).decode()
    
    style = """
        width: 100%; 
        border-radius: 8px; 
        transition: transform 0.2s, box-shadow 0.2s;
        cursor: pointer;
        border: 2px solid #eee;
        display: block;
    """
    
    html = f"""
        <a href='#' id='{unique_id}'>
            <img src='data:image/png;base64,{b64_data}' style='{style}' 
            onmouseover="this.style.transform='scale(1.02)'; this.style.boxShadow='0 4px 15px rgba(0,0,0,0.1)'; this.style.borderColor='#ff4b4b';" 
            onmouseout="this.style.transform='scale(1.0)'; this.style.boxShadow='none'; this.style.borderColor='#eee';">
        </a>
    """
    return html

# ================= SETUP =================
st.set_page_config(layout="centered", page_title="Logo Pulse")

st.markdown("""
<style>
    .block-container { padding-top: 2rem !important; max-width: 900px; }
    h1 { font-size: 1.8rem !important; margin-bottom: 0.5rem !important; }
    .stDeployButton {display:none;}
    .zoom-hint { text-align: center; color: #888; font-size: 0.8rem; margin-top: 5px; }
</style>
""", unsafe_allow_html=True)

# State Init
if 'pair' not in st.session_state: st.session_state['pair'] = None
if 'stats' not in st.session_state: st.session_state['stats'] = {"Hue": 0, "Looka": 0, "Total": 0}
if 'seen_images' not in st.session_state: st.session_state['seen_images'] = set()
if 'user_name' not in st.session_state: st.session_state['user_name'] = None

# ================= CSS TWEAKS (MOBILE FRIENDLY) =================
st.markdown("""
<style>
    /* Aggressive mobile spacing reset */
    .block-container { 
        padding-top: 0.5rem !important; 
        padding-bottom: 2rem !important; 
        padding-left: 0.5rem !important;
        padding-right: 0.5rem !important;
        max-width: 100%; 
    }
    
    /* Hide the huge default header decoration */
    header { visibility: hidden; }
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
    
    /* Compact Text */
    h3 { 
        margin: 0 !important; 
        padding: 0 !important; 
        font-size: 1.1rem !important; 
        text-align: center;
    }
    p { margin-bottom: 0.2rem !important; font-size: 0.9rem !important; }
    
    /* Remove gaps between elements */
    .element-container { margin-bottom: 0.2rem !important; }
    
    /* TIGHTEN VERTICAL GAP (Mobile Stack) */
    div[data-testid="column"] { 
        padding: 0 !important;
        margin-bottom: -5rem !important; /* Force overlap/tightness */
        z-index: 1; /* Ensure distinct stacking context */
    }
    
    /* Remove gap between columns in the flex container */
    div[data-testid="column"] > div {
        height: auto !important;
    }
    
    /* Target the Horizontal Block that holds the columns */
    div[class*="stHorizontalBlock"] {
        gap: 0 !important;
    }
    
    /* Remove padding from the components inside columns */
    div.element-container {
        margin-bottom: 0rem !important;
        padding-bottom: 0rem !important;
    }

    /* Specifically target the click detector iframe/container if possible (it's usually an iframe in a div) */
    iframe {
        margin-bottom: 0 !important;
        display: block !important;
    }

    /* Ensure images take full width but minimal height overhead */
    img { 
        margin-bottom: 0 !important; 
        padding-bottom: 0 !important;
    }
    
    /* Reduce top padding further */
    .block-container { 
        padding-top: 0 !important; 
        padding-bottom: 1rem !important; 
    }
</style>
""", unsafe_allow_html=True)

# ================= LOGIC =================
def get_strict_pair():
    inventory = {}
    all_files = glob.glob(os.path.join(INPUT_ROOT, "*", "*.png"))
    
    for f in all_files:
        if f in st.session_state['seen_images']: continue
        parts = os.path.splitext(os.path.basename(f))[0].split('_')
        if len(parts) < 2: continue
        
        source, industry = parts[0], parts[1]
        if industry not in inventory: inventory[industry] = {"Hue": [], "Looka": []}
        if source in inventory[industry]: inventory[industry][source].append(f)

    playable = [ind for ind, srcs in inventory.items() if srcs["Hue"] and srcs["Looka"]]
    
    if not playable: return None

    sel_ind = random.choice(playable)
    hue_img = random.choice(inventory[sel_ind]["Hue"])
    looka_img = random.choice(inventory[sel_ind]["Looka"])
    
    st.session_state['seen_images'].add(hue_img)
    st.session_state['seen_images'].add(looka_img)
    
    return [hue_img, looka_img, sel_ind]

def save_vote(winner_source, loser_source, industry):
    user = st.session_state.get('user_name', 'Anonymous')
    data = {
        "User": [user],
        "Winner": [winner_source], 
        "Loser": [loser_source], 
        "Industry": [industry]
    }
    df = pd.DataFrame(data)
    
    if not os.path.exists(RESULTS_FILE):
        df.to_csv(RESULTS_FILE, index=False)
    else:
        df.to_csv(RESULTS_FILE, mode='a', header=False, index=False)
    
    st.session_state['stats'][winner_source] += 1
    st.session_state['stats']['Total'] += 1

def reset_session():
    st.session_state['seen_images'] = set()
    st.session_state['pair'] = None
    st.session_state['stats'] = {"Hue": 0, "Looka": 0, "Total": 0}
    st.rerun()

# ================= MAIN UI =================

# 1. LOGIN GATE
if not st.session_state['user_name']:
    st.markdown("### 👋 Welcome!", unsafe_allow_html=True)
    with st.form("login_form"):
        name_input = st.text_input("Please enter your name:", placeholder="Name")
        if st.form_submit_button("Start Voting"):
            if name_input.strip():
                st.session_state['user_name'] = name_input.strip()
                st.rerun()
    st.stop()

# 2. VOTING APP
# Header info - Condensed
user = st.session_state['user_name']
st.markdown(f"### Hi {user}, which logo is better?", unsafe_allow_html=True)

if st.session_state['pair'] is None:
    st.session_state['pair'] = get_strict_pair()

if st.session_state['pair']:
    hue_path, looka_path, industry = st.session_state['pair']
    
    # Context - Single Line
    ctx = BRAND_INFO.get(industry, {"name": "Unknown", "tagline": "", "industry": industry})
    st.markdown(f"<p style='text-align:center;'><b>{ctx['industry']}</b> | {ctx['name']} | <i>{ctx['tagline']}</i></p>", unsafe_allow_html=True)

    # Layout Randomizer
    if 'layout_order' not in st.session_state:
        st.session_state['layout_order'] = [0, 1]
        random.shuffle(st.session_state['layout_order'])
        
    options = [hue_path, looka_path] # 0=Hue, 1=Looka
    idx_left = st.session_state['layout_order'][0]
    idx_right = st.session_state['layout_order'][1]
    
    # Using columns (stacked on mobile)
    col1, col2 = st.columns(2)

    # --- LEFT IMAGE ---
    with col1:
        # Reduced width to 85% to fit better
        content_left = get_image_html(options[idx_left], "btn_left").replace("width: 100%;", "width: 85%; margin: 0 auto;")
        clicked_left = click_detector(content_left)
        if clicked_left == "btn_left":
            win = os.path.basename(options[idx_left]).split('_')[0]
            lose = os.path.basename(options[idx_right]).split('_')[0]
            save_vote(win, lose, industry)
            st.session_state['pair'] = get_strict_pair()
            st.session_state['layout_order'] = [0, 1] 
            random.shuffle(st.session_state['layout_order'])
            st.rerun()

    # --- RIGHT IMAGE ---
    with col2:
        content_right = get_image_html(options[idx_right], "btn_right").replace("width: 100%;", "width: 85%; margin: 0 auto;")
        clicked_right = click_detector(content_right)
        if clicked_right == "btn_right":
            win = os.path.basename(options[idx_right]).split('_')[0]
            lose = os.path.basename(options[idx_left]).split('_')[0]
            save_vote(win, lose, industry)
            st.session_state['pair'] = get_strict_pair()
            st.session_state['layout_order'] = [0, 1]
            random.shuffle(st.session_state['layout_order'])
            st.rerun()
    
    # Minimal Progress
    total_images = len(glob.glob(f"{INPUT_ROOT}/*/*.png"))
    if total_images > 0:
        st.progress(len(st.session_state['seen_images']) / total_images)

else:
    st.balloons()
    st.success("🎉 All pairs voted on!")
    if st.button("Start Over"):
        reset_session()

st.write("") # Minimal spacer

# ================= ADMIN DASHBOARD (RESTORED) =================
with st.expander("📊 Admin Controls & Results"):
    
    # 1. DELETE BUTTON (Secret Admin Mode)
    # Access via URL: ?admin=true  (e.g., localhost:8501/?admin=true)
    query_params = st.query_params
    admin_mode = query_params.get("admin") == "true"

    if admin_mode:
        c1, c2 = st.columns([3, 1])
        with c1:
            st.warning("⚠️ **Danger Zone:** This clears all voting history.")
        with c2:
            if st.button("🗑️ Clear CSV Data", type="primary"):
                if os.path.exists(RESULTS_FILE):
                    os.remove(RESULTS_FILE)
                    st.toast("History deleted!", icon="🗑️")
                    # Reset in-memory stats to match file
                    st.session_state['stats'] = {"Hue": 0, "Looka": 0, "Total": 0}
                    st.rerun()
                else:
                    st.toast("No file to delete.", icon="🤷")
        st.divider()

    # 2. METRICS & CHART
    if os.path.exists(RESULTS_FILE):
        df = pd.read_csv(RESULTS_FILE)
        
        if len(df) > 0:
            # --- RESTORED METRICS SECTION ---
            total_votes = len(df)
            hue_wins = len(df[df['Winner'] == 'Hue'])
            looka_wins = len(df[df['Winner'] == 'Looka'])
            hue_rate = int((hue_wins / total_votes) * 100) if total_votes > 0 else 0
            
            # The 3-Column Layout
            m1, m2, m3 = st.columns(3)
            m1.metric("Total Votes", total_votes)
            m2.metric("Hue Win Rate", f"{hue_rate}%", delta=f"{hue_rate - 50}% vs Parity")
            m3.metric("Hue vs Looka", f"{hue_wins} - {looka_wins}")
            # --------------------------------
            
            st.write("---")
            
            # Altair Chart
            matrix = df.groupby(['Industry', 'Winner']).size().unstack(fill_value=0)
            if 'Hue' not in matrix.columns: matrix['Hue'] = 0
            if 'Looka' not in matrix.columns: matrix['Looka'] = 0
            
            src_data = matrix.reset_index().melt('Industry', var_name='Source', value_name='Votes')
            
            chart = alt.Chart(src_data).mark_bar().encode(
                x=alt.X('Industry', axis=alt.Axis(labelAngle=0)),
                y='Votes',
                color=alt.Color('Source', scale=alt.Scale(domain=['Hue', 'Looka'], range=['#FF4B4B', '#333333'])),
                xOffset='Source'
            ).properties(height=350)
            
            st.altair_chart(chart, use_container_width=True)
            
            # Show Raw Data with User column
            if st.checkbox("Show Raw Data"):
                st.dataframe(df)

        else:
            st.info("Waiting for votes...")
    else:
        st.info("No database found yet. Cast the first vote!")