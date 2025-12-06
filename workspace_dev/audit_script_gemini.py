import os
import glob
import json
import time
import pandas as pd
from PIL import Image
import streamlit as st
import google.generativeai as genai
from google.api_core import exceptions

# ======================= CONFIGURATION =======================
try:
    API_KEY = st.secrets["GEMINI_API_KEY"]
except:
    API_KEY = "PLACEHOLDER_KEY_DO_NOT_COMMIT"

# MODEL: Using 1.5 Pro for better design critique reasoning
MODEL_NAME = "gemini-1.5-pro" 

# GRID SETTINGS (Must match your screenshots exactly)
COLS = 3   
ROWS = 10  

# PATHS
INPUT_FOLDER = "input_screenshots"
OUTPUT_CSV = "FINAL_GAP_ANALYSIS_FULL.csv"
SLICE_FOLDER = "temp_slices"
# =============================================================

genai.configure(api_key=API_KEY)

model = genai.GenerativeModel(
    model_name=MODEL_NAME,
    generation_config={
        "response_mime_type": "application/json",
        "temperature": 0.0,
    }
)

def slice_grid(image_path):
    filename = os.path.basename(image_path)
    # Parse filename: expects "source_industry.png" (e.g., looka_coffee.png)
    name_parts = os.path.splitext(filename)[0].split('_')
    
    if len(name_parts) < 2:
        source = "Unknown"
        industry = filename
    else:
        source = name_parts[0]
        industry = name_parts[1]

    if filename.startswith('.'): return []

    print(f"🔪 Slicing {source.upper()} batch for {industry}...")
    img = Image.open(image_path)
    img_width, img_height = img.size
    cell_width = img_width / COLS
    cell_height = img_height / ROWS
    
    batch_folder = os.path.join(SLICE_FOLDER, f"{source}_{industry}")
    if not os.path.exists(batch_folder):
        os.makedirs(batch_folder)
    
    sliced_paths = []
    count = 0
    for r in range(ROWS):
        for c in range(COLS):
            left = c * cell_width
            upper = r * cell_height
            right = left + cell_width
            lower = upper + cell_height
            
            logo_slice = img.crop((left, upper, right, lower))
            count += 1
            slice_name = f"{source}_{industry}_{count:02d}.png"
            full_path = os.path.join(batch_folder, slice_name)
            logo_slice.save(full_path)
            
            sliced_paths.append({
                "path": full_path,
                "source": source,
                "industry": industry
            })
    return sliced_paths

def normalize_keys(data):
    """
    Standardizes keys to lowercase to prevent 'Unknown' errors.
    e.g. 'Primary_Flaw' -> 'primary_flaw'
    """
    return {k.lower().replace(" ", "_"): v for k, v in data.items()}

def audit_logo_safe(file_info):
    """
    Analyzes logo with retry logic for rate limits.
    """
    image_path = file_info["path"]
    source = file_info["source"]
    industry = file_info["industry"]
    
    print(f"   🤖 Auditing {os.path.basename(image_path)}...")
    
    img = Image.open(image_path)

    prompt = f"""
    You are a Senior Design QA. Analyze this logo for the '{industry}' industry (Source: {source}).
    
    Evaluate on 2 Dimensions:
    1. TECHNICAL HYGIENE (Score 1-10): 
       - 10 = Perfect alignment, clear spacing, legible contrast. 
       - 1 = Elements touching, text overlapping icon, unreadable.
       - Look specifically for "crashing" elements where text touches the icon.
       (Note: Looka usually scores high here. Check for bugs).

    2. CREATIVE SOUL (Score 1-10):
       - 10 = Unique font pairing, custom-feeling icon, distinct vibe.
       - 1 = Generic "Clip Art", overused standard fonts, boring layout.
       (Note: Generic/Boring = Low Score).

    3. DIAGNOSIS:
       - primary_flaw: Choose ONE from ["Alignment_Bug", "Spacing_Bug", "Bad_Contrast", "Generic_Icon", "Generic_Font", "None"].
       - critique: A 10-word actionable fix or observation.

    Return JSON format only.
    """

    max_retries = 5
    base_delay = 10 # 1.5 Pro limit is different but safe to keep delay?
                    # 1.5 Pro is 2 RPM for free, but paid is higher.
                    # Assuming free tier for now or robust handling.
                    # User switched to 1.5 Pro.
    
    for attempt in range(max_retries):
        try:
            response = model.generate_content(
                [prompt, img],
                generation_config={"response_mime_type": "application/json"}
            )
            result = json.loads(response.text)
            clean_result = normalize_keys(result)
            
            # Respect Rate Limit on success
            time.sleep(base_delay)

            return {
                "source": source,
                "industry": industry,
                "filename": os.path.basename(image_path),
                "hygiene_score": clean_result.get("technical_hygiene", clean_result.get("technical_hygiene_score", 0)),
                "soul_score": clean_result.get("creative_soul", clean_result.get("creative_soul_score", 0)),
                "primary_flaw": clean_result.get("primary_flaw", "Unknown"),
                "critique": clean_result.get("critique", "")
            }
        except Exception as e:
            error_str = str(e)
            if "429" in error_str:
                wait_time = (attempt + 1) * 20
                print(f"   ⏳ Rate limit bucket hit. Sleeping {wait_time}s (Attempt {attempt+1}/{max_retries})...")
                time.sleep(wait_time)
            else:
                print(f"   ❌ Error analyzing {os.path.basename(image_path)}: {e}")
                return None
    
    print(f"   ❌ Failed after {max_retries} retries due to rate limits.")
    return None

# ======================= MAIN EXECUTION =======================
if __name__ == "__main__":
    print(f"🚀 Starting Gemini Logo Gap Analysis ({MODEL_NAME})...")
    
    screenshots = glob.glob(os.path.join(INPUT_FOLDER, "*.png"))
    if not screenshots:
        print(f"❌ No .png files found in {INPUT_FOLDER}!")
        exit()

    all_data = []

    for screenshot in screenshots:
        slices = slice_grid(screenshot)
        
        for item in slices:
            audit_data = audit_logo_safe(item)
            
            if audit_data:
                clean_data = {
                    "Source": item["source"],
                    "Industry": item["industry"],
                    "Hygiene_Score": audit_data["hygiene_score"],
                    "Soul_Score": audit_data["soul_score"],
                    "Primary_Flaw": audit_data["primary_flaw"],
                    "Critique": audit_data["critique"],
                    "Filename": item["path"]
                }
                all_data.append(clean_data)

    if all_data:
        df = pd.DataFrame(all_data)
        df.to_csv(OUTPUT_CSV, index=False)
        print(f"\n✅ SUCCESS! Processed {len(df)} logos.")
        print(f"📊 Results saved to: {OUTPUT_CSV}")
    else:
        print("\n⚠️ No data collected.")