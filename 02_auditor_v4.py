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
    API_KEY = "PLACEHOLDER_KEY_DO_NOT_COMMIT" # Fallback for local testing

MODEL_NAME = "gemini-2.5-flash-lite" 

INPUT_ROOT = "output_slices"
OUTPUT_CSV = "FINAL_AUDIT_V4_PRODUCT.csv"

TEST_LIMIT = 5  # <--- NEW: Set to 5 for testing, set to 0 or None to run full batch
# ==================================================

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

def flatten_response(source, industry, filename, json_data):
    row = {
        "Source": source,
        "Industry": industry,
        "Filename": filename
    }
    
    # The 8 "Product Quality" Categories
    categories = [
        "variety", "quality", "industry_relevance", "layout", 
        "font", "color", "icon", "container"
    ]
    
    for cat in categories:
        data = json_data.get(cat, {})
        # Format Column Names: "industry_relevance" -> "IndustryRelevance_Score"
        prefix = cat.replace("_", " ").title().replace(" ", "")
        
        row[f"{prefix}_Score"] = data.get("score", 0)
        row[f"{prefix}_Fix"] = data.get("suggested_fix", "None")
        row[f"{prefix}_Reason"] = data.get("reason", "")
        
    return row

def audit_logo_v4(image_path):
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

    # --- THE 8-CATEGORY PRODUCT PROMPT ---
    prompt = f"""
    You are a Senior Product Designer auditing logo quality for the '{industry}' industry.
    
    Evaluate this logo on these 8 PRODUCT DIMENSIONS (Score 1-5):
    
    1. VARIETY (Distinctiveness):
       - Is this logo unique or does it look like a template? 
       - 5 = Unique/Custom feel. 1 = Generic/Overused trope.
       
    2. QUALITY (Aesthetic Fidelity):
       - Are the assets premium? 
       - 5 = Sharp, professional vector feel. 1 = Glitchy, clip-art style, amateur.
       
    3. INDUSTRY RELEVANCE (Semantic Fit):
       - Does it fit '{industry}'? 
       - 5 = Perfect fit. 1 = Confusing/Wrong industry (e.g. Hammer for Spa).
       
    4. LAYOUT (Composition):
       - Is the balance correct? 
       - 5 = Balanced, professional spacing. 1 = Elements touching, off-center, messy.
       
    5. FONT (Typography):
       - Is the text readable and styled correctly? 
       - 5 = Legible, good pairing. 1 = Unreadable, tiny tagline, clashing styles.
       
    6. COLOR (Palette):
       - Is the contrast and harmony good? 
       - 5 = Good contrast (WCAG), nice harmony. 1 = Low contrast, vibrating colors.
       
    7. ICON (Symbolism):
       - Is the icon itself good? 
       - 5 = Strong symbol. 1 = Weak/Unclear symbol or no symbol where needed.
       
    8. CONTAINER (Shape/Badge integration):
       - How well is the logo contained or bounded? 
       - NOTE: If no visible container exists, judge the *implied* shape/balance.
       - 5 = Well integrated shape. 1 = Awkward bounding box or floating elements.

    OUTPUT JSON FORMAT:
    {{
      "variety": {{ "score": 1-5, "reason": "...", "suggested_fix": "SHORT actionable instruction" }},
      "quality": {{ "score": 1-5, "reason": "...", "suggested_fix": "..." }},
      "industry_relevance": {{ "score": 1-5, "reason": "...", "suggested_fix": "..." }},
      "layout": {{ "score": 1-5, "reason": "...", "suggested_fix": "..." }},
      "font": {{ "score": 1-5, "reason": "...", "suggested_fix": "..." }},
      "color": {{ "score": 1-5, "reason": "...", "suggested_fix": "..." }},
      "icon": {{ "score": 1-5, "reason": "...", "suggested_fix": "..." }},
      "container": {{ "score": 1-5, "reason": "...", "suggested_fix": "..." }}
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

if __name__ == "__main__":
    import random
    print(f"🚀 Starting V4 PRODUCT AUDIT using {MODEL_NAME}...")
    
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

    print(f"📦 Total images to audit: {len(all_images)} (Stratified V4 Sample)")
    
    if not all_images:
        print(f"❌ No sliced images found in '{INPUT_ROOT}'.")
        exit()
    
    # Check for existing CSV to warn about overwrite
    if os.path.exists(OUTPUT_CSV):
             print(f"⚠️ Overwriting existing {OUTPUT_CSV}...")

    all_data = []
    for i, image_path in enumerate(all_images):
        print(f"[{i+1}/{len(all_images)}] Auditing {os.path.basename(image_path)}...")
        result = audit_logo_v4(image_path)
        if result: all_data.append(result)
        time.sleep(4) 

    if all_data:
        df = pd.DataFrame(all_data)
        df.to_csv(OUTPUT_CSV, index=False)
        print(f"✅ V4 Audit Complete: {OUTPUT_CSV}")