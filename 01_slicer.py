# FILE: 01_slicer.py
import os
import glob
from PIL import Image

# ================= CONFIGURATION =================
# INPUT: Where your big grid screenshots are
INPUT_SCREENSHOTS_FOLDER = "input_screenshots"

# OUTPUT: Where the individual files will go
OUTPUT_SLICES_FOLDER = "ready_for_audit"

# GRID SETTINGS (Must match your screenshots)
COLS = 3
ROWS = 10
# =================================================

def slice_grid(image_path):
    filename = os.path.basename(image_path)
    # Parse filename: expects "source_industry.png" (e.g., looka_coffee.png)
    name_parts = os.path.splitext(filename)[0].split('_')
    
    if len(name_parts) < 2:
        print(f"⚠️ SKIPPING {filename}: Format must be 'Source_Industry.png'")
        return

    source = name_parts[0]   # "looka"
    industry = name_parts[1] # "coffee"

    print(f"🔪 Slicing {source.upper()} batch for {industry}...")
    
    try:
        img = Image.open(image_path)
    except Exception as e:
        print(f"   ❌ Could not open image: {e}")
        return

    img_width, img_height = img.size
    cell_width = img_width / COLS
    cell_height = img_height / ROWS
    
    # Create a subfolder for this batch (e.g., ready_for_audit/looka_coffee)
    # This keeps things organized for the next script
    batch_folder = os.path.join(OUTPUT_SLICES_FOLDER, f"{source}_{industry}")
    if not os.path.exists(batch_folder):
        os.makedirs(batch_folder)
    
    count = 0
    for r in range(ROWS):
        for c in range(COLS):
            left = c * cell_width
            upper = r * cell_height
            right = left + cell_width
            lower = upper + cell_height
            
            # Crop
            logo_slice = img.crop((left, upper, right, lower))
            count += 1
            
            # Save file: looka_coffee_01.png
            slice_name = f"{source}_{industry}_{count:02d}.png"
            logo_slice.save(os.path.join(batch_folder, slice_name))
            
    print(f"   ✅ Created {count} slices in /{source}_{industry}")

# === MAIN EXECUTION ===
if __name__ == "__main__":
    print("🚀 STARTING SLICER...")
    
    # Ensure input folder exists
    if not os.path.exists(INPUT_SCREENSHOTS_FOLDER):
        os.makedirs(INPUT_SCREENSHOTS_FOLDER)
        print(f"📁 Created folder '{INPUT_SCREENSHOTS_FOLDER}'. Drop your screenshots there!")
        exit()

    # Find images
    screenshots = glob.glob(os.path.join(INPUT_SCREENSHOTS_FOLDER, "*.png"))
    screenshots += glob.glob(os.path.join(INPUT_SCREENSHOTS_FOLDER, "*.jpg"))
    
    if not screenshots:
        print("❌ No images found. Add 'looka_coffee.png' etc. to input folder.")
    else:
        for screenshot in screenshots:
            slice_grid(screenshot)
        print("\n✨ SLICING COMPLETE. You can now run the Audit script.")