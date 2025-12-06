import pandas as pd
import json
import datetime

CSV_FILE = "FINAL_AUDIT_V4_PRODUCT.csv"
BRAND_FILE = "brand_data.json"

try:
    df = pd.read_csv(CSV_FILE)
    print(f"Loaded {len(df)} rows.")
    
    with open(BRAND_FILE) as f:
        brands = json.load(f)

    def get_meta(ind):
        info = brands.get(ind, {})
        name = info.get("name", "")
        tagline = info.get("tagline", "")
        L = len(name)
        n_len = "Short" if L < 10 else "Medium" if L <= 20 else "Long"
        return n_len, "Yes" if tagline else "No"

    # Add columns if missing
    if "Audit_Date" not in df.columns:
        df["Audit_Date"] = datetime.datetime.now().strftime("%Y-%m-%d")
        print("Added Audit_Date")
    
    if "Name_Length" not in df.columns or "Has_Tagline" not in df.columns:
        # Apply row-wise
        meta = df["Industry"].apply(lambda x: get_meta(x))
        df["Name_Length"] = meta.apply(lambda x: x[0])
        df["Has_Tagline"] = meta.apply(lambda x: x[1])
        print("Added Name_Length & Has_Tagline")

    df.to_csv(CSV_FILE, index=False)
    print("✅ Migration Complete!")
    
except Exception as e:
    print(f"Migration failed or unnecessary: {e}")
