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

# UPDATE: Matches your screenshot folder name exactly
INPUT_ROOT = "output_slices"  
OUTPUT_CSV = "FINAL_GAP_ANALYSIS_FULL.csv"
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
    # Fixes capitalization issues in JSON keys
    return {k.lower().replace(" ", "_"): v for k, v in data.items()}

def audit_logo_safe(image_path):
    print(f"   ✨ Auditing {os.path.basename(image_path)}...")
    
    # 1. Parse Metadata from filename
    # Logic: Filename is likely "Source_Industry Name_01.png"
    filename = os.path.basename(image_path)
    clean_name = os.path.splitext(filename)[0] # remove .png
    parts = clean_name.split('_')
    
    # Robust Parsing: Handles "Hue_Beauty Spa_01" (spaces in industry)
    if len(parts) >= 3:
        source = parts[0]                  # "Hue"
        industry = parts[1]                # "Beauty Spa"
        # parts[2] is the number "01", which we ignore
    elif len(parts) == 2:
        # Fallback if numbering is missing: "Hue_Construction"
        source = parts[0]
        industry = parts[1]
    else:
        source = "Unknown"
        industry = "Unknown"

    img = Image.open(image_path)

    # --- THE BLIND SENIOR DESIGNER PROMPT ---
    prompt = f"""
    You are a Senior Brand Identity Designer (Pentagram level).
    Conduct a BLIND AUDIT of this logo for the '{industry}' industry.
    
    Evaluate strictly on these 2 dimensions using the Rubric below:

    1. TECHNICAL HYGIENE (Score 1-10) - The Engineering Score
       - 10: Optical alignment is perfect. Contrast passes WCAG standards.
       - 5: Minor spacing awkwardness (e.g., text too close to icon).
       - 1: BROKEN. Elements overlap, text is illegible, or pixelated.
       *CRITICAL:* If text touches the icon or touches the canvas edge, Score must be < 4.

    2. CREATIVE SOUL (Score 1-10) - The Art Director Score
       - 10: Clever semantic link (e.g., a "coffee bean" that looks like a "brain" for a tech cafe). Custom typography.
       - 5: Safe but boring. Standard generic icon (e.g., a plain roof for real estate). Standard Sans-Serif.
       - 1: Clip-art level. Looks like a default template. Zero personality.

    3. DIAGNOSIS (The Fix)
       - primary_flaw: Categorize the WORST issue. Choose ONE: 
         ["Kerning_Issue", "Layout_Crash", "Low_Contrast", "Generic_Cliché", "Font_Mismatch", "None"].
       - critique: A ruthless but constructive 10-word critique for the junior designer.

    Return valid JSON: hygiene_score, soul_score, primary_flaw, critique.
    """

    # RETRY LOGIC (Aggressive for Pro / Exp Models)
    max_retries = 5
    for attempt in range(max_retries):
        try:
            response = model.generate_content([prompt, img])
            raw_text = response.text.replace("```json", "").replace("```", "").strip()
            data = json.loads(raw_text)
            clean_data = normalize_keys(data)

            return {
                "Source": source,
                "Industry": industry,
                "Hygiene_Score": clean_data.get("hygiene_score", clean_data.get("technical_hygiene", 0)),
                "Soul_Score": clean_data.get("soul_score", clean_data.get("creative_soul", 0)),
                "Primary_Flaw": clean_data.get("primary_flaw", "Unknown"),
                "Critique": clean_data.get("critique", ""),
                "Filename": filename
            }
            
        except exceptions.ResourceExhausted:
            wait_time = (attempt + 1) * 30 + 10 # 40s, 70s, 100s...
            print(f"      ⏳ Rate Limit hit. Sleeping {wait_time}s... (Attempt {attempt+1}/{max_retries})")
            time.sleep(wait_time)
        except Exception as e:
            print(f"      ❌ Error: {e}")
            break 
            
    return None

# === MAIN EXECUTION ===
if __name__ == "__main__":
    print(f"🚀 Starting AUDIT using {MODEL_NAME}...")
    
    # Find all png/jpg files recursively inside the folders created by Step 1
    # Structure: output_slices/looka_coffee/*.png
    all_images = glob.glob(os.path.join(INPUT_ROOT, "*", "*.png"))
    
    if not all_images:
        print(f"❌ No sliced images found in '{INPUT_ROOT}'. Did you run Script 01?")
        exit()

    print(f"📄 Found {len(all_images)} logos to audit.")
    all_data = []

    for image_path in all_images:
        result = audit_logo_safe(image_path)
        if result:
            all_data.append(result)
        
        # Rate Limit Safety: Flash-Lite has higher quotas.
        time.sleep(4) 

    if all_data:
        df = pd.DataFrame(all_data)
        df.to_csv(OUTPUT_CSV, index=False)
        print(f"\n✅ SUCCESS! Processed {len(df)} logos.")
        print(f"📊 Results saved to: {OUTPUT_CSV}")