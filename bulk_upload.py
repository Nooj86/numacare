import os
from pathlib import Path
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, types

# Force load .env from the script's directory
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)

DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT", "6543")
DB_NAME = os.getenv("DB_NAME", "postgres")

if not DB_PASS:
    raise ValueError(
        f"DB_PASS is missing! Check your .env file at {env_path.resolve()}"
    )

DATABASE_URL = (
    f"postgresql://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)
CSV_FILE_PATH = "dialysis_billing_data.csv"
TABLE_NAME = "billing_data"

# --- READ CSV DATA ---
print(f"Reading historical CSV: '{CSV_FILE_PATH}'...")
df = pd.read_csv(CSV_FILE_PATH)
df["Trans_Date"] = pd.to_datetime(df["Trans_Date"])

print(f"Loaded {len(df):,} rows.")

# --- DEFINE POSTGRES SCHEMA ---
dtype_mapping = {
    "Invoice_No": types.INTEGER(),
    "Trans_Date": types.DATE(),
    "Service_Centre": types.VARCHAR(length=50),
    "Patient_ID": types.VARCHAR(length=50),
    "Patient_Name": types.VARCHAR(length=100),
    "Medical_Aid": types.VARCHAR(length=50),
    "Category": types.VARCHAR(length=50),
    "Claim_Code": types.VARCHAR(length=50),
    "Item_Code": types.VARCHAR(length=50),
    "Description": types.VARCHAR(length=255),
    "Quantity": types.INTEGER(),
    "Amount_Excl": types.NUMERIC(precision=10, scale=2),
    "Cost": types.NUMERIC(precision=10, scale=2),
    "Is_Reversal": types.BOOLEAN(),
}

# --- UPLOAD TO SUPABASE VIA POOLER ---
print("Connecting securely via Supabase Pooler...")
engine = create_engine(DATABASE_URL)

print(f"Uploading batch records to '{TABLE_NAME}'...")
df.to_sql(
    name=TABLE_NAME,
    con=engine,
    if_exists="replace",
    index=False,
    chunksize=5000,
    dtype=dtype_mapping,
)

print(
    f"✅ Success! Uploaded {len(df):,} historical records into '{TABLE_NAME}'."
)