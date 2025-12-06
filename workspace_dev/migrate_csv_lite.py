import csv
import json
import datetime
import os

CSV_FILE = "workspace_dev/FINAL_AUDIT_V4_PRODUCT.csv"
BRAND_FILE = "workspace_dev/brand_data.json"

def get_meta(brands, ind):
    info = brands.get(ind, {})
    name = info.get("name", "")
    tagline = info.get("tagline", "")
    L = len(name)
    n_len = "Short" if L < 10 else "Medium" if L <= 20 else "Long"
    return datetime.datetime.now().strftime("%Y-%m-%d"), n_len, "Yes" if tagline else "No"

try:
    with open(BRAND_FILE) as f:
        brands = json.load(f)

    with open(CSV_FILE, 'r') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    # Check if migration needed
    if "Audit_Date" in fieldnames:
        print("✅ Columns already exist.")
        exit()

    # Add new columns
    new_fields = fieldnames + ["Audit_Date", "Name_Length", "Has_Tagline"]
    
    with open(CSV_FILE, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=new_fields)
        writer.writeheader()
        
        for row in rows:
            date, n_len, has_tag = get_meta(brands, row['Industry'])
            row['Audit_Date'] = date
            row['Name_Length'] = n_len
            row['Has_Tagline'] = has_tag
            writer.writerow(row)
            
    print(f"✅ Migration Complete! Updated {len(rows)} rows.")

except Exception as e:
    print(f"❌ Error: {e}")
