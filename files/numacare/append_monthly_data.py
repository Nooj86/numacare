import os
from datetime import datetime, timedelta
from pathlib import Path
import random
from dotenv import load_dotenv
import pandas as pd
from sqlalchemy import create_engine, text, types

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

# --- 2. QUERY DATABASE FOR STATE (MAX DATE & MAX INVOICE) ---
print("Fetching existing database state from Supabase...")
with engine.connect() as conn:
    state_query = text(
        f"SELECT MAX(\"Trans_Date\") as max_date, MAX(\"Invoice_No\") as max_inv FROM {TABLE_NAME}"
    )
    result = conn.execute(state_query).fetchone()
    last_date = (
        pd.to_datetime(result[0]) if result[0] else pd.to_datetime("2026-07-27")
    )
    last_invoice = int(result[1]) if result[1] else 100000

    # Fetch existing patient cohort to preserve longitudinal continuity
    patient_query = text(
        f"SELECT DISTINCT \"Patient_ID\", \"Medical_Aid\", \"Service_Centre\" FROM {TABLE_NAME}"
    )
    existing_patients_df = pd.read_sql(patient_query, conn)

print(f"Last Recorded Date in DB: {last_date.date()}")
print(f"Last Invoice Number in DB: {last_invoice}")
print(f"Existing Active Patient Pool: {len(existing_patients_df)} patients")

# --- 3. DETERMINE GENERATION WINDOW ---
start_date = last_date + timedelta(days=1)
today = pd.to_datetime(datetime.now().date())

if start_date > today:
    print(
        "✅ Database is already up to date! No new records needed at this time."
    )
    exit(0)

print(f"Generating new incremental records from {start_date.date()} to {today.date()}...")

# --- 4. GENERATE INCREMENTAL ROWS ---
# Convert existing patients to list of dicts
patient_pool = existing_patients_df.to_dict("records")

# Introduce ~5% organic growth for new patients
num_new_patients = max(1, int(len(patient_pool) * 0.05))
service_centres = ["Walvis Bay", "Ongwediva", "Rundu"]
medical_aids = [
    "PSEMAS",
    "NMH Medical Aid",
    "Bankmed Namibia",
    "Heritage Health",
    "Private / Cash",
]

for i in range(num_new_patients):
    patient_pool.append(
        {
            "Patient_ID": f"PAT-{len(patient_pool) + 101:04d}",
            "Medical_Aid": random.choice(medical_aids),
            "Service_Centre": random.choice(service_centres),
        }
    )

new_records = []
current_invoice = last_invoice + 1
date_range = pd.date_range(start=start_date, end=today)

# Catalog definitions
procedures = [
    {
        "Code": "75148",
        "Desc": "Chronic Haemodialysis Session",
        "Category": "Chronic",
        "Amount": 2850.00,
        "Cost": 0.00,
    },
    {
        "Code": "75150",
        "Desc": "Acute Emergency Dialysis",
        "Category": "Acute",
        "Amount": 4200.00,
        "Cost": 0.00,
    },
]

stock_items = [
    {
        "Code": "STK-001",
        "Desc": "High-Flux Dialyzer F80",
        "Amount": 450.00,
        "Cost": 210.00,
    },
    {
        "Code": "STK-002",
        "Desc": "AV Fistula Needle 16G",
        "Amount": 45.00,
        "Cost": 18.00,
    },
    {
        "Code": "STK-003",
        "Desc": "Blood Line Set Adult",
        "Amount": 180.00,
        "Cost": 75.00,
    },
    {
        "Code": "STK-004",
        "Desc": "Heparin Sodium 5000IU",
        "Amount": 65.00,
        "Cost": 28.00,
    },
    {
        "Code": "STK-005",
        "Desc": "Acid Concentrate 10L",
        "Amount": 220.00,
        "Cost": 95.00,
    },
]

for single_date in date_range:
    # Daily session count (~6 to 12 sessions across clinics per day)
    daily_sessions = random.randint(6, 12)

    for _ in range(daily_sessions):
        patient = random.choice(patient_pool)
        proc = random.choices(procedures, weights=[0.85, 0.15])[0]

        # Procedure Row
        new_records.append(
            {
                "Invoice_No": current_invoice,
                "Trans_Date": single_date.date(),
                "Service_Centre": patient["Service_Centre"],
                "Patient_ID": patient["Patient_ID"],
                "Patient_Name": f"Patient {patient['Patient_ID'].split('-')[-1]}",
                "Medical_Aid": patient["Medical_Aid"],
                "Category": proc["Category"],
                "Claim_Code": proc["Code"],
                "Item_Code": proc["Code"],
                "Description": proc["Desc"],
                "Quantity": 1,
                "Amount_Excl": proc["Amount"],
                "Cost": proc["Cost"],
                "Is_Reversal": False,
            }
        )

        # 3 to 5 Stock Bundle Items per Session
        session_stock = random.sample(stock_items, k=random.randint(3, 5))
        for item in session_stock:
            qty = random.randint(1, 2)
            new_records.append(
                {
                    "Invoice_No": current_invoice,
                    "Trans_Date": single_date.date(),
                    "Service_Centre": patient["Service_Centre"],
                    "Patient_ID": patient["Patient_ID"],
                    "Patient_Name": f"Patient {patient['Patient_ID'].split('-')[-1]}",
                    "Medical_Aid": patient["Medical_Aid"],
                    "Category": "Stock",
                    "Claim_Code": item["Code"],
                    "Item_Code": item["Code"],
                    "Description": item["Desc"],
                    "Quantity": qty,
                    "Amount_Excl": item["Amount"] * qty,
                    "Cost": item["Cost"] * qty,
                    "Is_Reversal": False,
                }
            )

        current_invoice += 1

# --- 5. APPEND TO SUPABASE ---
df_new = pd.DataFrame(new_records)
print(f"Generated {len(df_new):,} new line-item records to append.")

if not df_new.empty:
    df_new.to_sql(
        name=TABLE_NAME,
        con=engine,
        if_exists="append",  # Appends to existing table schema
        index=False,
        chunksize=5000,
    )
    print(
        f"✅ Successfully appended {len(df_new):,} records to Supabase table '{TABLE_NAME}'!"
    )