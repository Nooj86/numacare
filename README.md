# NumaCare — Renal Dialysis Billing & Operations Dashboard

An end-to-end healthcare analytics dashboard for monitoring dialysis billing efficiency, tracking consumable stock consumption, analyzing revenue leakage/reversals, and managing static patient cohorts across multiple regional service centres.

Powered by **Streamlit**, **Supabase PostgreSQL**, **SQLAlchemy**, and **GitHub Actions**.

---

## Project Overview

NumaCare bridges clinical operations and billing analytics. Designed around a static cohort model of 150 anonymized renal patients, the platform models realistic longitudinal treatment patterns, procedure-to-consumable bundling, and regional claim reversal dynamics (e.g., PSEMAS / State Health Fund leakage).

### **Key Features**
* **Live Supabase PostgreSQL Backend:** Replaced static CSV mocks with a high-performance relational database with Row Level Security (RLS) enabled.
* **Automated Monthly Ingestion:** A state-aware pipeline automatically generates and appends incremental, historically aligned data at the end of every calendar month.
* **Consumable & Stock Cost Tracking:** Dynamically pulls stock catalog items, unit amounts, and unit costs directly from database history to maintain accurate per-session cost metrics (~$180–$220/session).
* **Revenue Leakage Analytics:** Models ~4% financial leakage (billing reversals), identifying claim rejection patterns across private and state medical aids.
* **Automated Caching & Sync:** Dynamic max-date filtering prevents UI display gaps across Streamlit Cloud deployments.

---

## Tech Stack

* **Frontend / Dashboard:** Streamlit, Plotly Express & Graph Objects, Pandas
* **Database / Backend:** Supabase (PostgreSQL)
* **ORM & Database Client:** SQLAlchemy, `psycopg2-binary`
* **Automation & CI/CD:** GitHub Actions (Cron Scheduler)
* **Environment Management:** `python-dotenv`

---

## Repository Structure

``text
numacare/
├── .github/
│   └── workflows/
│       └── monthly_ingestion.yml   # Scheduled GitHub Action (runs on 1st of month)
├── app.py / numacare.py            # Streamlit dashboard entry point
├── append_monthly_data.py          # State-aware incremental data ingestion engine
├── requirements.txt                # Production dependencies for Streamlit Cloud
├── .env.example                    # Template for database credentials
└── README.md                       # Project documentation
⚙️ Local Development Setup
1. Clone the Repository
Bash
git clone [https://github.com/Nooj86/numacare.git](https://github.com/Nooj86/numacare.git)
cd numacare
2. Set Up Virtual Environment & Dependencies
Bash
python -m venv venv
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

pip install -r requirements.txt
3. Configure Database Secrets (.env)
Create a .env file in the project root:

Code snippet
DB_USER=postgres.[YOUR_SUPABASE_PROJECT_REF]
DB_PASS=YOUR_SUPABASE_DATABASE_PASSWORD
DB_HOST=aws-1-eu-west-1.pooler.supabase.com
DB_PORT=6543
DB_NAME=postgres
4. Run the Dashboard Locally
Bash
streamlit run app.py
🚀 Data Pipeline & Automation
Incremental monthly data is generated using append_monthly_data.py.

Key Ingestion Rules:
State Preservation: Queries MAX("Trans_Date") and MAX("Invoice_No") to seamlessly resume billing sequence numbers without duplication.

Catalog Consistency: Dynamically extracts existing Service_Centre locations, procedure codes, and stock consumable descriptions from historical records to avoid phantom metrics.

Cohort Integrity: Preserves the 150 static patient IDs (PAT-001 through PAT-150) to maintain true longitudinal retention statistics.

Running Data Appender Manually:
Bash
python append_monthly_data.py
GitHub Actions Workflow:
The ingestion workflow is defined in .github/workflows/monthly_ingestion.yml. It runs automatically at 00:00 UTC on the 1st of every month to capture the full prior month's data, and can also be triggered manually via the GitHub Actions UI using workflow_dispatch.

🔒 Security & Database Best Practices
Row Level Security (RLS): Enabled on public.billing_data in Supabase to restrict unauthenticated PostgREST API access while allowing direct SQLAlchemy backend access over SSL.

Secret Isolation: API keys and connection strings are excluded from source control using .gitignore and injected via Streamlit Secrets (st.secrets) in production and GitHub Repository Secrets in CI/CD.
