import os
from datetime import datetime, timedelta
from pathlib import Path
import random
from dotenv import load_dotenv
import pandas as pd
from sqlalchemy import create_engine, text

# --- 1. CONFIGURATION & DATABASE CONNECTION ---
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT", "6543")
DB_NAME = os.getenv("DB_NAME", "postgres")

if not DB_PASS:
    raise ValueError("DB_PASS is missing! Check environment settings.")

DATABASE_URL = (
    f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)
engine = create_engine(DATABASE_URL)
TABLE_NAME = "billing_data"

# --- 2. QUERY DATABASE FOR STATE & HISTORICAL CATALOGS ---
print("Fetching database state and historical catalogs from Supabase...")
with engine.connect() as conn:
    # State Query
    state_query = text(
        f'SELECT MAX("Trans_Date") as max_date, MAX("Invoice_No") as max_inv FROM {TABLE_NAME}'
    )
    result = conn.execute(state_query).fetchone()
    last_date = (
        pd.to_datetime(result[0]) if result[0] else pd.to_datetime("2026-07-31")
    )
    last_invoice = int(result[1]) if result[1] else 100000

    # Active Patient Pool
    patient_query = text(
        f'SELECT DISTINCT "Patient_ID", "Medical_Aid", "Service_Centre" FROM {TABLE_NAME}'
    )
    existing_patients_df = pd.read_sql(patient_query, conn)

    # Dynamic Catalog Extraction from Historical Stock Data
    stock_catalog_query = text(
        f"""
        SELECT DISTINCT "Claim_Code", "Item_Code", "Description", 
               AVG("Amount_Excl" / NULLIF("Quantity", 0)) as unit_amount,
               AVG("Cost" / NULLIF("Quantity", 0)) as unit_cost
        FROM {TABLE_NAME}
        WHERE "Category" = 'Stock' AND "Amount_Excl" > 0
        GROUP BY "Claim_Code", "Item_Code", "Description"
        """
    )
    stock_catalog_df = pd.read_sql(stock_catalog_query, conn)

    # Dynamic Catalog Extraction for Procedures
    proc_catalog_query = text(
        f"""
        SELECT DISTINCT "Claim_Code", "Item_Code", "Description", "Category",
               AVG("Amount_Excl" / NULLIF("Quantity", 0)) as unit_amount,
               AVG("Cost" / NULLIF("Quantity", 0)) as unit_cost
        FROM {TABLE_NAME}
        WHERE "Category" IN ('Chronic', 'Acute') AND "Amount_Excl" > 0
        GROUP BY "Claim_Code", "Item_Code", "Description", "Category"
        """
    )
    proc_catalog_df = pd.read_sql(proc_catalog_query, conn)

print(f"Last Recorded Date in DB: {last_date.date()}")
print(f"Last Invoice Number in DB: {last_invoice}")
print(f"Active Patient Pool: {len(existing_patients_df)} static patients")
print(f"Extracted Stock Items from History: {len(stock_catalog_df)} items")

# --- 3. DETERMINE GENERATION WINDOW ---
start_date = last_date + timedelta(days=1)
today = pd.to_datetime(datetime.now().date())

# Stop at last day of August if running in September
target_end = min(today, pd.to_datetime("2026-08-31"))

if start_date > target_end:
    print("✅ Database is already up to date! No new records needed.")
    exit(0)

print(f"Generating aligned records from {start_date.date()} to {target_end.date()}...")

# --- 4. GENERATE INCREMENTAL ROWS ---
patient_pool = existing_patients_df.to_dict("records")
stock_items = stock_catalog_df.to_dict("records")
procedures = proc_catalog_df.to_dict("records")

new_records = []
current_invoice = last_invoice + 1
date_range = pd.date_range(start=start_date, end=target_end)

for single_date in date_range:
    # Dialysis centers usually operate Monday - Saturday
    if single_date.dayofweek == 6:  # Sunday
        daily_sessions = random.randint(1, 3)
    else:
        daily_sessions = random.randint(8, 14)

    for _ in range(daily_sessions):
        patient = random.choice(patient_pool)
        
        # Pick procedure (mostly Chronic)
        proc = random.choices(procedures, weights=[0.90, 0.10])[0] if len(procedures) > 1 else procedures[0]

        # Reversal modeling (~4% overall)
        reversal_probability = 0.07 if patient["Medical_Aid"] == "PSEMAS" else 0.02
        is_reversal = random.random() < reversal_probability
        amount_sign = -1.0 if is_reversal else 1.0

        pat_num = patient["Patient_ID"].replace("PAT-", "")

        # Procedure Line Item
        proc_amount = float(proc["unit_amount"]) * amount_sign
        proc_cost = float(proc["unit_cost"])
        
        new_records.append(
            {
                "Invoice_No": current_invoice,
                "Trans_Date": single_date.date(),
                "Service_Centre": patient["Service_Centre"],
                "Patient_ID": patient["Patient_ID"],
                "Patient_Name": f"Patient {pat_num}",
                "Medical_Aid": patient["Medical_Aid"],
                "Category": proc["Category"],
                "Claim_Code": proc["Claim_Code"],
                "Item_Code": proc["Item_Code"],
                "Description": proc["Description"],
                "Quantity": 1,
                "Amount_Excl": proc_amount,
                "Cost": proc_cost,
                "Is_Reversal": is_reversal,
            }
        )

        # 2 to 4 Stock Items per session from exact historical catalog
        session_stock_count = random.randint(2, 4)
        session_stock = random.sample(stock_items, k=min(session_stock_count, len(stock_items)))
        
        for item in session_stock:
            qty = random.randint(1, 2)
            item_amount = float(item["unit_amount"]) * qty * amount_sign
            item_cost = float(item["unit_cost"]) * qty

            new_records.append(
                {
                    "Invoice_No": current_invoice,
                    "Trans_Date": single_date.date(),
                    "Service_Centre": patient["Service_Centre"],
                    "Patient_ID": patient["Patient_ID"],
                    "Patient_Name": f"Patient {pat_num}",
                    "Medical_Aid": patient["Medical_Aid"],
                    "Category": "Stock",
                    "Claim_Code": item["Claim_Code"],
                    "Item_Code": item["Item_Code"],
                    "Description": item["Description"],
                    "Quantity": qty,
                    "Amount_Excl": item_amount,
                    "Cost": item_cost,
                    "Is_Reversal": is_reversal,
                }
            )

        current_invoice += 1

# --- 5. APPEND TO SUPABASE ---
df_new = pd.DataFrame(new_records)
print(f"Generated {len(df_new):,} aligned line-item records.")

if not df_new.empty:
    df_new.to_sql(
        name=TABLE_NAME,
        con=engine,
        if_exists="append",
        index=False,
        chunksize=5000,
    )
    print(
        f"✅ Successfully appended {len(df_new):,} aligned records to '{TABLE_NAME}'!"
    )
