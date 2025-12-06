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
    """Recursively lowers keys to handle API capitalization quirks"""
    if isinstance(data, dict):
        return {k.lower().replace(" ", "_"): normalize_keys(v) for k, v in data.items()}
    return data

def flatten_response(source, industry, filename, json_data):
    """
    Flattens the nested JSON into a single CSV row.
    Maps: category -> {score, reason, fix} to columns like "Typography_Score", "Typography_Fix"
    """
    row = {
        "Source": source,
        "Industry": industry,
        "Filename": filename
    }
    
    # List of expected categories from the prompt
    categories = [
        "semantic_relevance", "brand_applicability", "visual_appeal", # High Level
        "typography", "color_palette", "iconography", "composition", "scalability" # Component Level
    ]
    
    for cat in categories:
        # Extract data safely (handle missing keys if AI glitches)
        data = json_data.get(cat, {})
        prefix = cat.replace("_", " ").title().replace(" ", "") # e.g. "visual_appeal" -> "VisualAppeal"
        
        row[f"{prefix}_Score"] = data.get("score", 0)
        row[f"{prefix}_Fix"] = data.get("suggested_fix", "None")
        row[f"{prefix}_Reason"] = data.get("reason", "")
        
    return row

def audit_logo_v3(image_path):
    print(f"   ⚖️  Auditing: {os.path.basename(image_path)}...")
    
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

    # --- THE V3 "COMPLIANCE OFFICER" PROMPT ---
    prompt = f"""
    You are the Senior Design Compliance Officer. 
    Conduct a rigorous audit of this logo for the '{industry}' industry.
    
    Scoring Rubric (1-5):
    5 = Exceptional. Unique, perfectly executed, strategic.
    3 = Passable. Safe, generic, standard execution. (The "Looka" baseline).
    1 = Broken. Glitched, illegible, semantic mismatch.

    EVALUATE ON THESE 8 CATEGORIES:

    === PART A: STRATEGIC FIT (High Level) ===
    1. Semantic Relevance: Does the imagery literally match '{industry}'? (e.g., Coffee cup for Cafe = 5. Hammer for Cafe = 1).
    2. Brand Applicability: Does the mood/vibe match the industry? (e.g., Corporate font for Bank = 5. Horror font for Spa = 1).
    3. Visual Appeal (Aesthetic Fidelity): Is it unique/premium? *CRITICAL: If it looks like generic clip-art or a default template, Max Score is 3.*

    === PART B: TECHNICAL EXECUTION (Component Level) ===
    4. Typography: Check legibility, pairing, and kerning. 
    5. Color Palette: Check contrast (WCAG) and harmony. 
    6. Iconography: Check asset quality. Is it a clean vector or jagged/ugly? 
    7. Composition (Layout): Check balance and padding. *CRITICAL: If text touches icon, Score = 1.*
    8. Scalability: Will this work at 50px (Favicon)? Check for thin lines or clutter.

    OUTPUT JSON FORMAT (Strictly enforce this structure):
    {{
      "semantic_relevance": {{ "score": 1-5, "reason": "...", "suggested_fix": "..." }},
      "brand_applicability": {{ "score": 1-5, "reason": "...", "suggested_fix": "..." }},
      "visual_appeal": {{ "score": 1-5, "reason": "...", "suggested_fix": "..." }},
      "typography": {{ "score": 1-5, "reason": "...", "suggested_fix": "..." }},
      "color_palette": {{ "score": 1-5, "reason": "...", "suggested_fix": "..." }},
      "iconography": {{ "score": 1-5, "reason": "...", "suggested_fix": "..." }},
      "composition": {{ "score": 1-5, "reason": "...", "suggested_fix": "..." }},
      "scalability": {{ "score": 1-5, "reason": "...", "suggested_fix": "..." }}
    }}
    
    *Important*: "suggested_fix" must be a technical instruction (e.g., "Increase icon margin", "Swap font to Sans-Serif"). If Score is 5, fix can be "None".
    """

    # RETRY LOGIC
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = model.generate_content([prompt, img])
            raw_text = response.text.replace("```json", "").replace("```", "").strip()
            data = json.loads(raw_text)
            clean_data = normalize_keys(data)

            # Flatten to CSV Row
            return flatten_response(source, industry, filename, clean_data)
            
        except exceptions.ResourceExhausted:
            print(f"      ⏳ Rate Limit. Sleeping 20s...")
            time.sleep(20)
        except Exception as e:
            print(f"      ❌ Error: {e}")
            break 
            
    return None

# === MAIN EXECUTION ===
if __name__ == "__main__":
    import random # Late import to ensure it's available
    print(f"🚀 Starting V3 DESIGN AUDIT using {MODEL_NAME}...")
    
    # Stratified Sampling Logic
    all_images = []
    
    # Get all subfolders (e.g., Hue_Coffee Shop, Looka_Real Estate)
    subfolders = glob.glob(os.path.join(INPUT_ROOT, "*"))
    
    for folder in subfolders:
        # Get images in this specific folder
        folder_images = glob.glob(os.path.join(folder, "*.png"))
        
        if TEST_LIMIT and TEST_LIMIT > 0:
            if len(folder_images) > TEST_LIMIT:
                random.shuffle(folder_images)
                folder_images = folder_images[:TEST_LIMIT]
                
        all_images.extend(folder_images)

    print(f"📦 Total images to audit: {len(all_images)} (Stratified Sample)")
    
    if not all_images:
        print(f"❌ No sliced images found in '{INPUT_ROOT}'.")
        exit()

    all_data = []

    for i, image_path in enumerate(all_images):
        # Progress Log
        print(f"[{i+1}/{len(all_images)}] Auditing {os.path.basename(image_path)}...")
        
        result = audit_logo_v3(image_path)
        if result:
            all_data.append(result)
        
        # Rate Limit Safety
        time.sleep(4) 

    if all_data:
        df = pd.DataFrame(all_data)
        # Reorder columns to put Scores first, then Fixes
        cols = sorted(df.columns.tolist()) 
        # Optional: Force Source/Industry to front if needed, but pandas usually handles ok
        
        if os.path.exists(OUTPUT_CSV):
             print(f"⚠️ Overwriting existing {OUTPUT_CSV}...")
             
        df.to_csv(OUTPUT_CSV, index=False)
        print(f"\n✅ SUCCESS! Processed {len(df)} logos.")
        print(f"📊 Results saved to: {OUTPUT_CSV}")