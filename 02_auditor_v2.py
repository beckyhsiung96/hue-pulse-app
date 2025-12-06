import os
import glob
import json
import time
import pandas as pd
from PIL import Image
import streamlit as st
import google.generativeai as genai
from google.api_core import exceptions

# ================= CONFIGURATION =================
try:
    API_KEY = st.secrets["GEMINI_API_KEY"]
except:
    API_KEY = "PLACEHOLDER_KEY_DO_NOT_COMMIT"
MODEL_NAME = "gemini-2.5-flash-lite" 

INPUT_ROOT = "output_slices"
OUTPUT_CSV = "SYSTEM_AUDIT_REPORT.csv"

TEST_LIMIT = 5  # <--- NEW: Set to 5 for testing, set to 0 or None to run full batch
# =================================================

genai.configure(api_key=API_KEY)

model = genai.GenerativeModel(
    model_name=MODEL_NAME,
    generation_config={
        "response_mime_type": "application/json",
        "temperature": 0.0,
    }
)

def normalize_keys(data):
    return {k.lower().replace(" ", "_"): v for k, v in data.items()}

def audit_logo_system(image_path):
    print(f"   ⚙️ System Check: {os.path.basename(image_path)}...")
    
    # Parse Metadata
    filename = os.path.basename(image_path)
    clean_name = os.path.splitext(filename)[0]
    parts = clean_name.split('_')
    
    if len(parts) >= 2:
        source = parts[0]
        industry = parts[1]
    else:
        source = "Unknown"
        industry = "Unknown"

    img = Image.open(image_path)

    # --- THE 6-POINT SYSTEM PROMPT ---
    prompt = f"""
    You are a QA Engineer for a Logo Generation System. 
    Analyze this logo for the '{industry}' industry.
    
    Ignore "Beauty". Evaluate strictly on these 6 TECHNICAL COMPONENT VECTORS:

    1. TYPOGRAPHY & READABILITY (Font size, readability)
       - Fail: Tagline too small (< 6px equivalent). Text unreadable.
    
    2. PAIRING LOGIC (Font/Icon Coherence)
       - Fail: Font mood does not match Icon style (e.g., Geometric Icon + Handwritten Font).
       - Fail: Weight Mismatch (Thin Icon + Ultra-Bold Font).

    3. LAYOUT TEMPLATES (Spacing, Balance)
       - Fail: Text touches icon (Padding Bug). Visual center is off.
    
    4. COLOR & CONTRAST
       - Fail: Low contrast (WCAG violation). Vibrating colors (Red/Green).

    5. ICON MAPPING (Semantic Logic)
       - Fail: Icon is unrelated to '{industry}' (e.g., Burger for a Gym).

    6. ASSET QUALITY (Vector Hygiene)
       - Fail: Icon looks like a glitch, bad clip-art, or "foul/ugly".

    OUTPUT JSON ONLY:
    {{
        "typo_score": (1-10),
        "typo_issue": (One of: "Tagline_Microscopic", "Unreadable", "None"),
        
        "pairing_score": (1-10),
        "pairing_issue": (One of: "Weight_Mismatch", "Style_Clash", "None"),
        
        "layout_score": (1-10),
        "layout_issue": (One of: "Touching_Elements", "Off_Balance", "Uneven_Padding", "None"),
        
        "color_score": (1-10),
        "color_issue": (One of: "Low_Contrast", "Vibrating_Colors", "None"),
        
        "icon_logic_score": (1-10),
        "icon_issue": (One of: "Semantic_Mismatch", "Asset_Quality_Fail", "None"),
        
        "primary_fix_ticket": (Specific instruction: "Increase tagline min-size", "Add padding", "Retag icon #123")
    }}
    """

    # RETRY LOGIC
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = model.generate_content([prompt, img])
            raw_text = response.text.replace("```json", "").replace("```", "").strip()
            data = json.loads(raw_text)
            clean_data = normalize_keys(data)

            # Flatten for CSV - NOW INCLUDES ALL 6 VECTORS
            return {
                "Source": source,
                "Industry": industry,
                "Typo_Score": clean_data.get("typo_score", 0),
                "Typo_Issue": clean_data.get("typo_issue", "Unknown"),
                
                "Pairing_Score": clean_data.get("pairing_score", 0),
                "Pairing_Issue": clean_data.get("pairing_issue", "Unknown"),
                
                "Layout_Score": clean_data.get("layout_score", 0),
                "Layout_Issue": clean_data.get("layout_issue", "Unknown"),
                
                "Color_Score": clean_data.get("color_score", 0),
                "Color_Issue": clean_data.get("color_issue", "Unknown"), # <--- ADDED THIS
                
                "Icon_Score": clean_data.get("icon_logic_score", 0),
                "Icon_Issue": clean_data.get("icon_issue", "Unknown"),
                
                "Fix_Ticket": clean_data.get("primary_fix_ticket", ""),
                "Filename": filename
            }
            
        except exceptions.ResourceExhausted:
            print(f"      ⏳ Rate Limit. Sleeping 20s...")
            time.sleep(20)
        except Exception as e:
            print(f"      ❌ Error: {e}")
            break 
            
    return None


# === MAIN EXECUTION ===
if __name__ == "__main__":
    print(f"🚀 Starting 6-POINT SYSTEM AUDIT using {MODEL_NAME}...")
    
    all_images = glob.glob(os.path.join(INPUT_ROOT, "*", "*.png"))
    
    # --- NEW: LIMIT LOGIC ---
    if TEST_LIMIT and TEST_LIMIT > 0:
        print(f"⚠️ TEST MODE ENABLED: Running on first {TEST_LIMIT} images only.")
        all_images = all_images[:TEST_LIMIT] 
    # ------------------------

    if not all_images:
        print(f"❌ No sliced images found in '{INPUT_ROOT}'.")
        exit()

    all_data = []

    for image_path in all_images:
        result = audit_logo_system(image_path)
        if result:
            all_data.append(result)
        
        # Rate Limit Safety
        time.sleep(4) 

    if all_data:
        df = pd.DataFrame(all_data)
        df.to_csv(OUTPUT_CSV, index=False)
        print(f"\n✅ SUCCESS! Processed {len(df)} logos.")
        print(f"📊 Results saved to: {OUTPUT_CSV}")