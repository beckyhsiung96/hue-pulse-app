import os
import glob
import json
import time
import pandas as pd
from PIL import Image
import google.generativeai as genai
from google.api_core import exceptions

# ================= CONFIGURATION =================
def get_api_key():
    try:
        paths = [".streamlit/secrets.toml", "../.streamlit/secrets.toml"]
        for p in paths:
            if os.path.exists(p):
                with open(p, "r") as f:
                    for line in f:
                        if "GEMINI_API_KEY" in line:
                            parts = line.split("=")
                            if len(parts) == 2:
                                return parts[1].strip().strip('"').strip("'")
    except: pass
    return os.environ.get("GEMINI_API_KEY")

API_KEY = get_api_key()
# API_KEY = "YOUR_API_KEY_HERE" # Or st.secrets if running in Streamlit
MODEL_NAME = "gemini-2.5-flash" 

INPUT_ROOT = "output_slices"
OUTPUT_CSV = "workspace_dev/FINAL_AUDIT_V7_BUGS.csv"
TEST_LIMIT = 5 
# =================================================

if not API_KEY:
    print("❌ API_KEY not found.")
    exit(1)

genai.configure(api_key=API_KEY)
model = genai.GenerativeModel(model_name=MODEL_NAME, generation_config={"response_mime_type": "application/json"})

def normalize_keys(data):
    if isinstance(data, dict):
        return {k.lower().replace(" ", "_"): normalize_keys(v) for k, v in data.items()}
    return data

def flatten_response(source, industry, filename, json_data):
    row = {"Source": source, "Industry": industry, "Filename": filename}
    
    # The 6 QA Categories
    categories = ["layout", "text", "color", "icon", "container", "cohesiveness"]
    
    for cat in categories:
        data = json_data.get(cat, {})
        prefix = cat.title()
        
        # Extract data
        bugs = data.get("bugs", [])
        score = data.get("score", 0)
        
        # DATA ENFORCEMENT: If bugs exist, Score MUST be 1.
        if bugs and len(bugs) > 0:
            score = 1
            
        row[f"{prefix}_Score"] = score
        # Join bugs with a pipe | for easy parsing later
        row[f"{prefix}_Bugs"] = "|".join(bugs) if bugs else "None"
        row[f"{prefix}_Reason"] = data.get("reason", "")
        
    return row

def audit_logo_v7(image_path):
    print(f"   🐞 Bug Hunt: {os.path.basename(image_path)}...")
    
    filename = os.path.basename(image_path)
    clean_name = os.path.splitext(filename)[0]
    parts = clean_name.split('_')
    source = parts[0] if len(parts) >= 1 else "Unknown"
    industry = parts[1] if len(parts) >= 2 else "Unknown"

    img = Image.open(image_path)

    # --- THE V7 "BUG HUNTER" PROMPT ---
    prompt = f"""
    You are a QA Engineer for a Logo Design System. Your job is to FLAG BUGS.
    Analyze this logo for the '{industry}' industry.

    PROTOCOL:
    1. Scan for the specific "Critical Bugs" listed below.
    2. If ANY bug is found in a category, that Category Score is automatically 1.
    3. If NO bugs are found, rate the design quality 2-5 (2=Boring, 5=Excellent).

    === BUG CHECKLIST (Use these exact tags) ===

    1. LAYOUT
       - "Disproportionate_Sizing": Elements are comically large/small relative to each other.
       - "Off_Center": Visibly unaligned.

    2. TEXT
       - "Text_Cutoff": Text exceeds the container or canvas edge (overflow).
       - "Text_Unreadable": Text is too small (<6px equivalent) or illegible font.
       - "Bad_Ratio": Tagline is larger than Brand Name, or Ratio is awkward.

    3. COLOR
       - "Low_Contrast": Text blends into background (hard to read).
       - "Theme_Mismatch": Colors clearly wrong for '{industry}' (e.g. Neon Pink for Law Firm).

    4. ICON
       - "Bad_Asset_Quality": Icon looks like a glitch, ugly clip-art, or pixelated.
       - "Icon_Too_Small": Icon is lost in the layout.
       - IF NO ICON: Return bugs: [] (Empty), do not penalize.

    5. CONTAINER
       - "Container_Cutoff": Shape exceeds the logo card.
       - "Container_Mismatch": Shape style clashes with industry.
       - IF NO CONTAINER: Return bugs: [] (Empty).

    6. COHESIVENESS (Style Matching)
       - "Style_Clash_Text": Font A and Font B clash (e.g. Round vs Sharp).
       - "Style_Clash_Icon": Icon style (e.g. Line Art) does not match Font (e.g. Blocky).
       - "Style_Clash_Container": Container style does not match Content.

    OUTPUT JSON FORMAT:
    {{
      "layout": {{ "score": 1-5, "bugs": ["Tag1", "Tag2"], "reason": "..." }},
      "text": {{ "score": 1-5, "bugs": ["Tag1"], "reason": "..." }},
      "color": {{ "score": 1-5, "bugs": [], "reason": "..." }},
      "icon": {{ "score": 1-5, "bugs": [], "reason": "..." }},
      "container": {{ "score": 1-5, "bugs": [], "reason": "..." }},
      "cohesiveness": {{ "score": 1-5, "bugs": [], "reason": "..." }}
    }}
    """

    for attempt in range(3):
        try:
            response = model.generate_content([prompt, img])
            raw_text = response.text.replace("```json", "").replace("```", "").strip()
            data = json.loads(raw_text)
            clean_data = normalize_keys(data)
            return flatten_response(source, industry, filename, clean_data)
        except Exception as e:
            print(f"      ❌ Error: {e}")
            time.sleep(2)
            break 
    return None

if __name__ == "__main__":
    print(f"🚀 Starting V7 BUG HUNT...")
    all_images = glob.glob(os.path.join(INPUT_ROOT, "*", "*.png"))
    if TEST_LIMIT > 0: all_images = all_images[:TEST_LIMIT]
    
    all_data = []
    for i, image_path in enumerate(all_images):
        result = audit_logo_v7(image_path)
        if result: all_data.append(result)
        time.sleep(4) 

    if all_data:
        df = pd.DataFrame(all_data)
        df.to_csv(OUTPUT_CSV, index=False)
        print(f"✅ V7 Audit Complete: {OUTPUT_CSV}")
