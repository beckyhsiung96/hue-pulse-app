import streamlit as st
import os
import random
import pandas as pd
import glob
import base64
import altair as alt
from datetime import datetime
# Using direct gspread to avoid wrapper issues
import gspread
from google.oauth2.service_account import Credentials
from st_click_detector import click_detector
from streamlit_gsheets import GSheetsConnection

# ================= CONFIGURATION =================
INPUT_ROOT = "output_slices"
# We define scopes explicitly to ensure access
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

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

# ================= GSHEETS CONNECTION (ROBUST) =================
@st.cache_resource
def get_gsheet_client():
    # Robustly load secrets
    try:
        # Check if 'connections.gsheets' exists
        if "connections" in st.secrets and "gsheets" in st.secrets["connections"]:
            secrets_dict = dict(st.secrets["connections"]["gsheets"]) # Convert to standard dict
            
            # Construct credentials explicitly from dict
            creds = Credentials.from_service_account_info(
                secrets_dict, 
                scopes=SCOPES
            )
            client = gspread.authorize(creds)
            return client, secrets_dict.get("spreadsheet")
        else:
            st.error("❌ 'connections.gsheets' section missing in secrets.toml")
            return None, None
    except Exception as e:
        st.error(f"❌ Auth Error: {str(e)}")
        return None, None

def get_data_as_df(client, sheet_url):
    try:
        sheet = client.open_by_url(sheet_url).sheet1
        data = sheet.get_all_records()
        return pd.DataFrame(data)
    except Exception as e:
        st.warning(f"Could not read GSheet: {e}")
        return pd.DataFrame()

def append_row_to_gsheet(client, sheet_url, row_data):
    try:
        sheet = client.open_by_url(sheet_url).sheet1
        # Convert row_data values to list
        row_values = list(row_data.values())
        sheet.append_row(row_values)
        return True
    except Exception as e:
        st.error(f"Save failed: {e}")
        return False

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

def save_vote(winner_source, loser_source, industry, win_file, lose_file):
    user = st.session_state.get('user_name', 'Anonymous')
    
    client, sheet_url = get_gsheet_client()
    if not client: return

    row = {
        "User": user,
        "Winner": winner_source,
        "Loser": loser_source,
        "Industry": industry,
        "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "Winner logo file name": win_file,
        "Loser logo file name": lose_file
    }
    
    if append_row_to_gsheet(client, sheet_url, row):
        st.session_state['stats'][winner_source] += 1
        st.session_state['stats']['Total'] += 1
        st.toast("Vote saved!", icon="✅")

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
user = st.session_state['user_name']
st.markdown(f"### Hi {user}, which logo is better?", unsafe_allow_html=True)

if st.session_state['pair'] is None:
    st.session_state['pair'] = get_strict_pair()

if st.session_state['pair']:
    hue_path, looka_path, industry = st.session_state['pair']
    
    # Context
    ctx = BRAND_INFO.get(industry, {"name": "Unknown", "tagline": "", "industry": industry})
    st.markdown(f"<p style='text-align:center;'><b>{ctx['industry']}</b> | {ctx['name']} | <i>{ctx['tagline']}</i></p>", unsafe_allow_html=True)

    # Layout Randomizer
    if 'layout_order' not in st.session_state:
        st.session_state['layout_order'] = [0, 1]
        random.shuffle(st.session_state['layout_order'])
        
    options = [hue_path, looka_path] # 0=Hue, 1=Looka
    idx_left = st.session_state['layout_order'][0]
    idx_right = st.session_state['layout_order'][1]
    
    col1, col2 = st.columns(2)

    # --- LEFT IMAGE ---
    with col1:
        content_left = get_image_html(options[idx_left], "btn_left").replace("width: 100%;", "width: 85%; margin: 0 auto;")
        clicked_left = click_detector(content_left)
        if clicked_left == "btn_left":
            win_src = os.path.basename(options[idx_left]).split('_')[0]
            lose_src = os.path.basename(options[idx_right]).split('_')[0]
            win_file = os.path.basename(options[idx_left])
            lose_file = os.path.basename(options[idx_right])
            
            save_vote(win_src, lose_src, industry, win_file, lose_file)
            st.session_state['pair'] = get_strict_pair()
            st.session_state['layout_order'] = [0, 1] 
            random.shuffle(st.session_state['layout_order'])
            st.rerun()

    # --- RIGHT IMAGE ---
    with col2:
        content_right = get_image_html(options[idx_right], "btn_right").replace("width: 100%;", "width: 85%; margin: 0 auto;")
        clicked_right = click_detector(content_right)
        if clicked_right == "btn_right":
            win_src = os.path.basename(options[idx_right]).split('_')[0]
            lose_src = os.path.basename(options[idx_left]).split('_')[0]
            win_file = os.path.basename(options[idx_right])
            lose_file = os.path.basename(options[idx_left])
            
            save_vote(win_src, lose_src, industry, win_file, lose_file)
            st.session_state['pair'] = get_strict_pair()
            st.session_state['layout_order'] = [0, 1]
            random.shuffle(st.session_state['layout_order'])
            st.rerun()
    
    total_images = len(glob.glob(f"{INPUT_ROOT}/*/*.png"))
    if total_images > 0:
        st.progress(len(st.session_state['seen_images']) / total_images)

else:
    st.balloons()
    st.success("🎉 All pairs voted on!")
    if st.button("Start Over"):
        reset_session()

st.write("") 

# ================= ADMIN DASHBOARD =================
# ================= ADMIN DASHBOARD =================
with st.expander("📊 Admin Controls & Results"):
    
    query_params = st.query_params
    admin_mode = query_params.get("admin") == "true"

    # Lazy Load Init
    if 'admin_df' not in st.session_state:
        st.session_state['admin_df'] = pd.DataFrame()

    # GATEKEEPER BUTTON
    if st.button("🔄 Load/Refresh Data"):
        try:
            conn = st.connection("gsheets", type=GSheetsConnection)
            # ttl=0 ensures we get FRESH data when button is clicked
            st.session_state['admin_df'] = conn.read(ttl=0) 
            st.success("Data Loaded From Google!")
        except Exception as e:
            st.error(f"Read Error: {e}")

    # Check if data exists in memory
    df = st.session_state['admin_df']

    if not df.empty:
        filtered_df = df.copy()

        # --- ADMIN ONLY: USER FILTER ---
        if admin_mode:
            st.warning("⚠️ **Admin Mode Active**")
            
            # 1. Manage Data
            st.markdown("[Open Google Sheet](https://docs.google.com/spreadsheets/u/0/) to manage rows.")
            
            st.divider()
            
            # 2. Add Filter
            if 'User' in df.columns:
                users = sorted(df['User'].astype(str).unique().tolist())
                
                # "Select All" Logic pattern
                container = st.container()
                all_selected = st.checkbox("Select All Users", value=True)
                
                if all_selected:
                    selected_users = users
                else:
                    selected_users = st.multiselect("Select Users", users, default=users)
                
                filtered_df = df[df['User'].isin(selected_users)]
                
                # Show filter stats
                st.caption(f"Showing {len(filtered_df)} votes from {len(selected_users)} users.")
                st.divider()

        # --- METRICS (Using filtered_df) ---
        hue_wins = len(filtered_df[filtered_df['Winner'] == 'Hue'])
        total = len(filtered_df)
        rate = (hue_wins/total)*100 if total > 0 else 0.0
        
        m1, m2, m3 = st.columns(3)
        m1.metric("Total Votes", total)
        m2.metric("Hue Win Rate", f"{rate:.2f}%")
        looka_wins = total - hue_wins
        m3.metric("Hue vs Looka", f"{hue_wins} - {looka_wins}")
        
        st.write("---")
        
        # --- CHART (Using filtered_df) ---
        if {'Industry', 'Winner'}.issubset(filtered_df.columns):
            # Ensure we have data to plot
            if len(filtered_df) == 0:
                st.warning("No data matches the current filters.")
            else:
                matrix = filtered_df.groupby(['Industry', 'Winner']).size().unstack(fill_value=0)
                if 'Hue' not in matrix.columns: matrix['Hue'] = 0
                if 'Looka' not in matrix.columns: matrix['Looka'] = 0
                
                src_data = matrix.reset_index().melt('Industry', var_name='Source', value_name='Votes')
                
                chart = alt.Chart(src_data).mark_bar().encode(
                    x=alt.X('Industry', axis=alt.Axis(labelAngle=0)),
                    y='Votes',
                    color=alt.Color('Source', scale=alt.Scale(domain=['Hue', 'Looka'], range=['#FF4B4B', '#333333'])),
                    xOffset='Source',
                    tooltip=['Industry', 'Source', 'Votes']
                ).properties(height=350)
                
                st.altair_chart(chart, use_container_width=True)
                

        else:
                st.warning("Data loaded, but columns 'Industry' or 'Winner' are missing.")

    else:
        st.info("Results hidden. Click 'Load Data' to fetch.")

    if not df.empty and admin_mode: # Only show if data is loaded AND admin
         # --- CHART 2: Win Rate by User (Admin Only) ---
        st.write("---")
        st.subheader("🏆 Hue Win Rate by User")
        
        if len(filtered_df) > 0:
            # 1. Group by User + Winner
            user_wins = filtered_df.groupby(['User', 'Winner']).size().unstack(fill_value=0)
            if 'Hue' not in user_wins.columns: user_wins['Hue'] = 0
            
            # 2. Calculate Total & Rate
            user_wins['Total'] = user_wins.sum(axis=1)
            user_wins['Hue Win Rate'] = (user_wins['Hue'] / user_wins['Total']).fillna(0)
            
            # Calculate Average Win Rate (Average of user win rates)
            avg_win_rate = user_wins['Hue Win Rate'].mean()

            # 3. Format for Chart
            chart_data = user_wins.reset_index()[['User', 'Hue Win Rate', 'Total', 'Hue']]
            
            # 4. Altair Chart (Layered)
            base = alt.Chart(chart_data).encode(
                x=alt.X('User', sort='-y', axis=alt.Axis(labelAngle=0)) # Horizontal labels
            )

            bars = base.mark_bar().encode(
                y=alt.Y('Hue Win Rate', axis=alt.Axis(format='%')),
                color=alt.value('#ff4b4b'), # Hue Brand Color
                tooltip=['User', alt.Tooltip('Hue Win Rate', format='.1%'), 'Total', 'Hue']
            )

            # Text 1: Win Rate (Red, Bold, higher up)
            rate_text = base.mark_text(dy=-18, color='#ff4b4b', fontWeight='bold').encode(
                y=alt.Y('Hue Win Rate'),
                text=alt.Text('Hue Win Rate', format='.0%')
            )
            
            # Text 2: Total Count (Grey, smaller, closer to bar)
            count_text = base.mark_text(dy=-6, color='gray', fontSize=10).encode(
                y=alt.Y('Hue Win Rate'),
                text=alt.Text('Total')
            )

            # Rule: Average Line
            rule = alt.Chart(pd.DataFrame({'y': [avg_win_rate]})).mark_rule(
                color='gray', 
                strokeDash=[5, 5],
                size=2
            ).encode(y='y')

            st.altair_chart((bars + rate_text + count_text + rule).properties(height=350), use_container_width=True)
            
            st.caption(f"Dashed line indicates average user win rate: {avg_win_rate:.1%}")
        else:
            st.warning("No data for current user selection.")
            
        # --- RAW DATA (Moved Below) ---
        if st.checkbox("Show Raw Data"):
            st.dataframe(filtered_df.sort_index(ascending=False))