import os
import glob
import json
import time
import csv
from PIL import Image
import google.generativeai as genai
from google.api_core import exceptions


# ================= CONFIGURATION =================
def get_api_key():
    try:
        # Try finding secrets in common locations
        paths = [".streamlit/secrets.toml", "../.streamlit/secrets.toml"]
        for p in paths:
            if os.path.exists(p):
                with open(p, "r") as f:
                    for line in f:
                        if "GEMINI_API_KEY" in line:
                            # Simple parse: key = "value"
                            parts = line.split("=")
                            if len(parts) == 2:
                                return parts[1].strip().strip('"').strip("'")
    except Exception as e:
        print(f"⚠️ Error reading secrets: {e}")
    return os.environ.get("GEMINI_API_KEY")

API_KEY = get_api_key()
if not API_KEY:
    print("❌ API_KEY not found in secrets.toml or environment.")
    exit(1)

MODEL_NAME = "gemini-2.5-flash-lite" 

INPUT_ROOT = "output_slices"
OUTPUT_CSV = "FINAL_AUDIT_V5_PRODUCT.csv" # Updated filename

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
    if isinstance(data, dict):
        return {k.lower().replace(" ", "_"): normalize_keys(v) for k, v in data.items()}
    return data

from datetime import datetime

# Load Brand Data
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
BRAND_DATA_PATH = os.path.join(BASE_DIR, "brand_data.json")
BRAND_METADATA = {}
if os.path.exists(BRAND_DATA_PATH):
    try:
        with open(BRAND_DATA_PATH, "r") as f:
            BRAND_METADATA = json.load(f)
    except: pass

def get_metadata(filename):
    # Try exact match first
    meta = BRAND_METADATA.get(filename)
    if not meta:
        # Try finding by brand name in filename
        for brand_key, data in BRAND_METADATA.items():
            if brand_key in filename:
                return data
    return meta

def flatten_response(source, industry, filename, json_data):
    # Metadata Injection
    meta = get_metadata(filename)
    name_len = meta.get("Name_Length", "Unknown") if meta else "Unknown"
    has_tag = meta.get("Has_Tagline", "No") if meta else "No"
    
    row = {
        "Source": source,
        "Industry": industry,
        "Filename": filename,
        "Audit_Date": datetime.now().strftime("%Y-%m-%d"),
        "Name_Length": name_len,
        "Has_Tagline": has_tag
    }
    
    categories = [
        "variety", "quality", "industry_relevance", "layout", 
        "font", "color", "icon", "container"
    ]
    
    for cat in categories:
        data = json_data.get(cat, {})
        prefix = cat.replace("_", " ").title().replace(" ", "")
        
        # CRITICAL UPDATE: 
        # We defaults to None (NaN) instead of 0. 
        # This allows Pandas to exclude it from averages later.
        row[f"{prefix}_Score"] = data.get("score", None) 
        row[f"{prefix}_Fix"] = data.get("suggested_fix", "None")
        row[f"{prefix}_Reason"] = data.get("reason", "")
        
    return row

def audit_logo_v5(image_path):
    print(f"   🎨 Product Audit: {os.path.basename(image_path)}...")
    
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

    # --- THE V5 "SMART N/A" PROMPT ---
    prompt = f"""
    You are a Senior Product Designer auditing logo quality for the '{industry}' industry.
    
    Evaluate on these 8 PRODUCT DIMENSIONS.
    
    IMPORTANT: For 'Icon' and 'Container', check if they exist first. 
    If they do not exist, return "score": null. DO NOT rate them as low quality.

    1. VARIETY (Distinctiveness):
       - Is this logo unique or a template? (5=Unique, 1=Generic).
       
    2. QUALITY (Aesthetic Fidelity):
       - Are the assets premium? (5=Sharp/Pro, 1=Glitchy/Clip-art).
       
    3. INDUSTRY RELEVANCE (Semantic Fit):
       - Does it fit '{industry}'? (5=Perfect fit, 1=Wrong industry).
       
    4. LAYOUT (Composition):
       - Is the balance correct? (5=Balanced, 1=Messy/Touching elements).
       
    5. FONT (Typography):
       - Readable and styled/paired correctly for both name and tagline? (5=Great, 1=Unreadable/Tiny).
       
    6. COLOR (Palette):
       - Contrast and harmony? (5=Great, 1=Low contrast/Vibrating).
       
    7. ICON (Symbolism):
       - CHECK EXISTENCE: Is there a distinct icon symbol (graphic)?
       - IF NO ICON (Wordmark only): Return "score": null.
       - IF ICON EXISTS: Rate it 1-5 (5=Strong symbol, 1=Weak/Unclear).
       
    8. CONTAINER (Shape/Badge):
       - CHECK EXISTENCE: Is there a visible container shape (circle, badge, shield, box) enclosing the logo?
       - IF NO CONTAINER (Floating elements): Return "score": null.
       - IF CONTAINER EXISTS: Rate integration 1-5.

    OUTPUT JSON FORMAT:
    {{
      "variety": {{ "score": 1-5, "reason": "...", "suggested_fix": "..." }},
      "quality": {{ "score": 1-5, "reason": "...", "suggested_fix": "..." }},
      "industry_relevance": {{ "score": 1-5, "reason": "...", "suggested_fix": "..." }},
      "layout": {{ "score": 1-5, "reason": "...", "suggested_fix": "..." }},
      "font": {{ "score": 1-5, "reason": "...", "suggested_fix": "..." }},
      "color": {{ "score": 1-5, "reason": "...", "suggested_fix": "..." }},
      "icon": {{ "score": 1-5 OR null, "reason": "...", "suggested_fix": "..." }},
      "container": {{ "score": 1-5 OR null, "reason": "...", "suggested_fix": "..." }}
    }}
    """

    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = model.generate_content([prompt, img])
            raw_text = response.text.replace("```json", "").replace("```", "").strip()
            data = json.loads(raw_text)
            clean_data = normalize_keys(data)
            return flatten_response(source, industry, filename, clean_data)
        except exceptions.ResourceExhausted:
            print(f"      ⏳ Rate Limit. Sleeping 20s...")
            time.sleep(20)
        except Exception as e:
            print(f"      ❌ Error: {e}")
            break 
    return None

import random

if __name__ == "__main__":
    print(f"🚀 Starting V5 PRODUCT AUDIT...")

    # Stratified Sampling Logic
    all_images = []
    subfolders = glob.glob(os.path.join(INPUT_ROOT, "*"))
    
    for folder in subfolders:
        folder_images = glob.glob(os.path.join(folder, "*.png"))
        if TEST_LIMIT and TEST_LIMIT > 0:
            if len(folder_images) > TEST_LIMIT:
                random.shuffle(folder_images)
                folder_images = folder_images[:TEST_LIMIT]
        all_images.extend(folder_images)

    print(f"📦 Total images to audit: {len(all_images)} (Stratified V5 Sample)")
    
    if not all_images:
        print(f"❌ No sliced images found in '{INPUT_ROOT}'.")
        exit()
    
    all_data = []
    for i, image_path in enumerate(all_images):
        result = audit_logo_v5(image_path)
        if result: all_data.append(result)
        time.sleep(4) 

    if all_data:
        keys = all_data[0].keys()
        with open(OUTPUT_CSV, 'w', newline='') as output_file:
            dict_writer = csv.DictWriter(output_file, fieldnames=keys)
            dict_writer.writeheader()
            dict_writer.writerows(all_data)
        print(f"✅ V5 Audit Complete: {OUTPUT_CSV}")