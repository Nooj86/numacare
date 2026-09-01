import os
from pathlib import Path
from dotenv import load_dotenv
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from sqlalchemy import create_engine
import streamlit as st

# -----------------------------------------------------------------------------
# PAGE CONFIGURATION
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="NumaCare Analytics",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded",
)

# -----------------------------------------------------------------------------
# DATABASE CONNECTION & LIVE DATA LOADING
# -----------------------------------------------------------------------------
env_path = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=env_path)


def get_db_url():
    # Works locally via .env OR on Streamlit Cloud via st.secrets
    user = os.getenv("DB_USER") or st.secrets.get("DB_USER")
    password = os.getenv("DB_PASS") or st.secrets.get("DB_PASS")
    host = os.getenv("DB_HOST") or st.secrets.get("DB_HOST")
    port = os.getenv("DB_PORT") or st.secrets.get("DB_PORT", "6543")
    dbname = os.getenv("DB_NAME") or st.secrets.get("DB_NAME", "postgres")

    if not password:
        raise ValueError("Database credentials missing!")

    return f"postgresql://{user}:{password}@{host}:{port}/{dbname}"


@st.cache_data(ttl=3600)  # Caches PostgreSQL query results for 1 hour
def load_data():
    db_url = get_db_url()
    engine = create_engine(db_url)

    query = """
        SELECT 
            "Invoice_No",
            "Trans_Date",
            "Service_Centre",
            "Patient_ID",
            "Patient_Name",
            "Medical_Aid",
            "Category",
            "Claim_Code",
            "Item_Code",
            "Description",
            "Quantity",
            "Amount_Excl",
            "Cost",
            "Is_Reversal"
        FROM billing_data
        ORDER BY "Trans_Date" ASC
    """

    df = pd.read_sql(query, engine)
    df["Trans_Date"] = pd.to_datetime(df["Trans_Date"])
    df["Year"] = df["Trans_Date"].dt.year
    df["Month_Num"] = df["Trans_Date"].dt.month
    df["Month_Name"] = df["Trans_Date"].dt.strftime("%b")

    if "Profit" not in df.columns:
        df["Profit"] = df["Amount_Excl"] - df["Cost"]

    return df


with st.spinner("Connecting securely to Supabase PostgreSQL Database..."):
    df = load_data()

# Global Month Ordering
months_order = [
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
]
# -----------------------------------------------------------------------------
# SIDEBAR FILTERS
# -----------------------------------------------------------------------------
st.sidebar.image(
    "https://img.icons8.com/color/96/000000/hospital-2.png", width=60
)
st.sidebar.title("NumaCare Executive Filter")

available_years = sorted(df["Year"].dropna().unique().astype(int).tolist())
selected_year = st.sidebar.selectbox("Select Analysis Year", available_years)

st.sidebar.markdown("---")
st.sidebar.info(
    "**Dashboard Scope:**\nThis decision-support engine models clinical volume, inventory profit margins, operational overheads, and financial leakage across all dialysis service centers."
)

with st.sidebar.expander("Data Limitation Note"):
    st.write(
        "The historical dataset utilizes a static cohort of 150 anonymized patient IDs across multi-year cycles. "
        "While chronic dialysis patient populations naturally exhibit low churn (~80–85% retention annually), real-world data "
        "would reflect slight monthly variance due to new patient intake, mortality, or kidney transplants.\n\n"
        "To model operational utilization accurately despite this static cohort, volume metrics focus on **Treatment Sessions "
        "per Active Bed** and **Procedure Categories (Chronic vs. Acute)** rather than raw patient count growth."
    )

st.sidebar.markdown("---")
st.sidebar.caption(
    "**Data Privacy & Governance Notice:**\n"
    "This decision-support engine is modeled on real-world multi-center clinical workflows, "
    "reimbursement dynamics, and operational cost structures.\n\n"
    "**Anonymization & Compliance:**\n"
    "All facility names, patient IDs, and pricing metrics have been anonymized, synthesized, "
    "or modified to protect proprietary operational data and comply with patient privacy standards."
)

# Filter dataset for main views
df_filtered = df[df["Year"] == selected_year].copy()

# -----------------------------------------------------------------------------
# MAIN HEADER & EXECUTIVE KPIs
# -----------------------------------------------------------------------------
st.title("NumaCare Executive Operations & Financial Dashboard")
st.caption(
    f"Multi-Centre Performance Analysis for **{selected_year}** | Billed Ledger Data"
)

# 1. Executive Calculations
total_gross_revenue = df_filtered["Amount_Excl"].sum()
total_cost = df_filtered["Cost"].sum()
total_net_profit = df_filtered["Profit"].sum()
overall_margin = (
    (total_net_profit / total_gross_revenue) * 100
    if total_gross_revenue != 0
    else 0
)

total_sessions = df_filtered[
    df_filtered["Category"].isin(["Chronic", "Acute"])
]["Invoice_No"].nunique()
total_patients = df_filtered["Patient_ID"].nunique()

OPEX_PERCENTAGE = 0.55
opex_est = total_gross_revenue * OPEX_PERCENTAGE
ebitda_est = total_net_profit - opex_est

# KPI Cards Display
kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
kpi1.metric("Gross Revenue", f"${total_gross_revenue:,.2f}")
kpi2.metric("Total Cost of Goods", f"${total_cost:,.2f}")
kpi3.metric("Gross Profit", f"${total_net_profit:,.2f}", f"{overall_margin:.1f}% Margin")
kpi4.metric("Dialysis Sessions", f"{total_sessions:,}")
kpi5.metric("Unique Patients", f"{total_patients:,}")

st.markdown("---")

# -----------------------------------------------------------------------------
# TAB NAVIGATION
# -----------------------------------------------------------------------------
tab1, tab2, tab3 = st.tabs(
    [
        "📈 Revenue & Volume Trends",
        "📦 Stock & Consumable Profitability",
        "🚨 Reversals & Financial Leakage",
    ]
)

# =============================================================================
# TAB 1: REVENUE & VOLUME TRENDS
# =============================================================================
with tab1:
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Monthly Treatment Session Counts")
        
        # View toggle for Clinic vs. Category Breakdown
        view_mapping = st.radio(
            "Session Grouping View",
            ["By Clinic Location", "By Treatment Category"],
            horizontal=True,
            key="session_view_radio"
        )
        
        if view_mapping == "By Clinic Location":
            session_df = (
                df_filtered[df_filtered["Category"].isin(["Chronic", "Acute"])]
                .groupby(["Month_Num", "Month_Name", "Service_Centre"])[
                    "Invoice_No"
                ]
                .nunique()
                .reset_index()
                .sort_values("Month_Num")
            )

            fig_sessions = px.line(
                session_df,
                x="Month_Name",
                y="Invoice_No",
                color="Service_Centre",
                markers=True,
                category_orders={"Month_Name": months_order},
                color_discrete_sequence=["#4C72B0", "#DD8452", "#55A868"],
                labels={
                    "Invoice_No": "Total Sessions",
                    "Month_Name": "Month",
                    "Service_Centre": "Clinic Location",
                },
            )
        else:
            # Grouping mapped by Category (Chronic, Acute, and Combined Total)
            cat_df = (
                df_filtered[df_filtered["Category"].isin(["Chronic", "Acute"])]
                .groupby(["Month_Num", "Month_Name", "Category"])[
                    "Invoice_No"
                ]
                .nunique()
                .reset_index()
            )
            
            total_cat_df = (
                df_filtered[df_filtered["Category"].isin(["Chronic", "Acute"])]
                .groupby(["Month_Num", "Month_Name"])[
                    "Invoice_No"
                ]
                .nunique()
                .reset_index()
            )
            total_cat_df["Category"] = "Total (Chronic + Acute)"
            
            session_df = pd.concat([cat_df, total_cat_df], ignore_index=True).sort_values("Month_Num")

            fig_sessions = px.line(
                session_df,
                x="Month_Name",
                y="Invoice_No",
                color="Category",
                markers=True,
                category_orders={"Month_Name": months_order},
                color_discrete_sequence=["#4C72B0", "#DD8452", "#2B5C8F"],
                labels={
                    "Invoice_No": "Total Sessions",
                    "Month_Name": "Month",
                    "Category": "Session Category",
                },
            )

        fig_sessions.update_layout(
            plot_bgcolor="white",
            height=380,
            hovermode="x unified",
            legend=dict(
                orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1
            ),
        )
        fig_sessions.update_xaxes(showgrid=True, gridcolor="#E5E5E5")
        fig_sessions.update_yaxes(showgrid=True, gridcolor="#E5E5E5")
        st.plotly_chart(fig_sessions, use_container_width=True)

    with col2:
        st.subheader("Revenue Contribution by Payor")
        # Payor Revenue
        med_rev = (
            df_filtered.groupby("Medical_Aid")["Amount_Excl"]
            .sum()
            .reset_index()
            .sort_values("Amount_Excl", ascending=True)
        )

        fig_med = px.bar(
            med_rev,
            y="Medical_Aid",
            x="Amount_Excl",
            orientation="h",
            color_discrete_sequence=["#4C72B0"],
            labels={
                "Amount_Excl": "Billed Revenue ($)",
                "Medical_Aid": "Medical Aid / Payor",
            },
        )
        fig_med.update_layout(
            plot_bgcolor="white",
            height=380,
            xaxis_tickprefix="$",
            xaxis_tickformat=",",
        )
        fig_med.update_xaxes(showgrid=True, gridcolor="#E5E5E5")
        st.plotly_chart(fig_med, use_container_width=True)

    st.info(
        "**Financial Model Estimate:** Assuming an estimated 55% fixed operating overhead rate, "
        f"estimated EBITDA for {selected_year} is **${ebitda_est:,.2f}**."
    )

# =============================================================================
# TAB 2: STOCK & CONSUMABLE PROFITABILITY
# =============================================================================
with tab2:
    st.subheader("Stock Consumables Profitability Engine")

    col_scale, col_empty = st.columns([1, 2])
    with col_scale:
        scale_type = st.radio(
            "X-Axis View Scale",
            ["Linear (Default)", "Logarithmic (Equal Visibility)"],
            horizontal=True,
        )

    # Stock aggregation
    stock_df = df_filtered[df_filtered["Category"] == "Stock"].copy()
    stock_summary = (
        stock_df.groupby("Description")
        .agg(
            Total_Qty=("Quantity", "sum"),
            Total_Revenue=("Amount_Excl", "sum"),
            Total_Cost=("Cost", "sum"),
        )
        .reset_index()
    )

    stock_summary["Gross_Profit"] = (
        stock_summary["Total_Revenue"] - stock_summary["Total_Cost"]
    )
    stock_summary["Margin_Pct"] = (
        stock_summary["Gross_Profit"] / stock_summary["Total_Revenue"]
    ) * 100
    stock_summary = stock_summary.sort_values(by="Gross_Profit", ascending=True)

    # Plot 1: Stacked Bar Chart
    fig_stock = go.Figure()

    fig_stock.add_trace(
        go.Bar(
            y=stock_summary["Description"],
            x=stock_summary["Total_Cost"],
            name="Direct Stock Cost",
            orientation="h",
            marker_color="#DD8452",
            customdata=stock_summary[["Total_Qty", "Margin_Pct"]],
            hovertemplate="<b>Item:</b> %{y}<br><b>Cost:</b> $%{x:,.2f}<br><b>Qty:</b> %{customdata[0]:,}<extra></extra>",
        )
    )

    fig_stock.add_trace(
        go.Bar(
            y=stock_summary["Description"],
            x=stock_summary["Gross_Profit"],
            name="Gross Profit",
            orientation="h",
            marker_color="#55A868",
            customdata=stock_summary[["Total_Qty", "Margin_Pct"]],
            hovertemplate="<b>Item:</b> %{y}<br><b>Gross Profit:</b> $%{x:,.2f}<br><b>Margin:</b> %{customdata[1]:.1f}%<br><b>Qty:</b> %{customdata[0]:,}<extra></extra>",
        )
    )

    is_log = scale_type == "Logarithmic (Equal Visibility)"
    fig_stock.update_layout(
        barmode="stack",
        height=420,
        plot_bgcolor="white",
        xaxis_title=(
            "Dollar Amount ($)" if not is_log else "Dollar Amount (Log Scale)"
        ),
        xaxis_type="log" if is_log else "linear",
        xaxis_tickprefix="$",
        xaxis_tickformat=",",
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1
        ),
    )
    fig_stock.update_xaxes(showgrid=True, gridcolor="#E5E5E5")
    st.plotly_chart(fig_stock, use_container_width=True)

    st.markdown("---")

    col_pie, col_line = st.columns(2)

    with col_pie:
        st.subheader("Profit Split: High-Value vs General")
        stock_df["Item_Group"] = stock_df["Description"].apply(
            lambda x: "Dialyzers (High-Value)"
            if "DIALYZER" in str(x).upper()
            else "General Sundries & Meds"
        )
        stock_df["Gross_Profit"] = stock_df["Amount_Excl"] - stock_df["Cost"]
        group_summary = (
            stock_df.groupby("Item_Group")["Gross_Profit"].sum().reset_index()
        )

        fig_pie = px.pie(
            group_summary,
            values="Gross_Profit",
            names="Item_Group",
            hole=0.5,
            color_discrete_sequence=["#55A868", "#4C72B0"],
        )
        fig_pie.update_traces(
            textinfo="percent+label",
            hovertemplate="<b>%{label}</b><br>Gross Profit: $%{value:,.2f}<extra></extra>",
        )
        fig_pie.update_layout(plot_bgcolor="white", height=350, showlegend=False)
        st.plotly_chart(fig_pie, use_container_width=True)

        st.markdown(
            "**Key Finding:** 77% of consumable stock margin is concentrated in Dialyzer units alone, making supplier contract negotiations for Dialyzers the primary lever for inventory cost reduction."
        )

    with col_line:
        st.subheader("Consumable Stock Cost per Session")
        stock_monthly = (
            df_filtered[df_filtered["Category"] == "Stock"]
            .groupby(["Month_Num", "Month_Name", "Service_Centre"])["Cost"]
            .sum()
            .reset_index()
        )
        session_monthly = (
            df_filtered[df_filtered["Category"].isin(["Chronic", "Acute"])]
            .groupby(["Month_Num", "Month_Name", "Service_Centre"])[
                "Invoice_No"
            ]
            .nunique()
            .reset_index()
        )

        merged_cost = pd.merge(
            stock_monthly,
            session_monthly,
            on=["Month_Num", "Month_Name", "Service_Centre"],
        )
        merged_cost["Cost_Per_Session"] = (
            merged_cost["Cost"] / merged_cost["Invoice_No"]
        )
        merged_cost = merged_cost.sort_values("Month_Num")

        fig_cost = px.line(
            merged_cost,
            x="Month_Name",
            y="Cost_Per_Session",
            color="Service_Centre",
            markers=True,
            category_orders={"Month_Name": months_order},
            color_discrete_sequence=["#4C72B0", "#DD8452", "#55A868"],
            labels={
                "Cost_Per_Session": "Stock Cost / Session ($)",
                "Month_Name": "Month",
                "Service_Centre": "Clinic Location",
            },
        )
        fig_cost.update_layout(
            plot_bgcolor="white",
            height=350,
            yaxis_tickprefix="$",
            hovermode="x unified",
            legend=dict(
                orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1
            ),
        )
        fig_cost.update_xaxes(showgrid=True, gridcolor="#E5E5E5")
        fig_cost.update_yaxes(showgrid=True, gridcolor="#E5E5E5")
        st.plotly_chart(fig_cost, use_container_width=True)

        st.markdown(
            "**Key Finding:** Consumable stock cost per treatment session remains highly stable at ~$195–$200/session across all three centers, showing consistent clinical inventory management without noticeable waste."
        )

# =============================================================================
# TAB 3: REVERSALS & FINANCIAL LEAKAGE
# =============================================================================
with tab3:
    st.subheader("Billing Reversals & Revenue Leakage")

    col_rev1, col_rev2 = st.columns(2)

    with col_rev1:
        st.subheader("Monthly Revenue Leakage Rate (%)")
        monthly_leakage = (
            df_filtered.groupby(["Month_Num", "Month_Name", "Service_Centre"])
            .agg(
                Total_Billed=("Amount_Excl", lambda x: x[x > 0].sum()),
                Reversed_Amount=("Amount_Excl", lambda x: abs(x[x < 0].sum())),
            )
            .reset_index()
        )

        monthly_leakage["Leakage_Pct"] = (
            monthly_leakage["Reversed_Amount"] / monthly_leakage["Total_Billed"]
        ) * 100
        monthly_leakage = monthly_leakage.sort_values("Month_Num")

        fig_leak = px.line(
            monthly_leakage,
            x="Month_Name",
            y="Leakage_Pct",
            color="Service_Centre",
            markers=True,
            category_orders={"Month_Name": months_order},
            color_discrete_sequence=["#4C72B0", "#DD8452", "#55A868"],
            labels={
                "Leakage_Pct": "Leakage Rate (%)",
                "Month_Name": "Month",
                "Service_Centre": "Clinic Location",
            },
        )
        fig_leak.update_layout(
            plot_bgcolor="white",
            height=380,
            yaxis_ticksuffix="%",
            hovermode="x unified",
            legend=dict(
                orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1
            ),
        )
        fig_leak.update_xaxes(showgrid=True, gridcolor="#E5E5E5")
        fig_leak.update_yaxes(showgrid=True, gridcolor="#E5E5E5")
        st.plotly_chart(fig_leak, use_container_width=True)

        st.markdown(
            "**Key Finding:** Reversals consume between 2.9% and 6.4% of total monthly billed revenue across clinics, representing avoidable financial leakage."
        )

    with col_rev2:
        st.subheader("Reversal Value by Payor & Category")
        reversal_df = df_filtered[df_filtered["Is_Reversal"] == True].copy()

        if len(reversal_df) > 0:
            reversal_df["Abs_Amount"] = reversal_df["Amount_Excl"].abs()
            med_reversals = (
                reversal_df.groupby(["Medical_Aid", "Category"])["Abs_Amount"]
                .sum()
                .reset_index()
            )

            fig_rev_bar = px.bar(
                med_reversals,
                x="Medical_Aid",
                y="Abs_Amount",
                color="Category",
                barmode="stack",
                color_discrete_sequence=["#DD8452", "#4C72B0", "#55A868"],
                labels={
                    "Abs_Amount": "Reversed Value ($)",
                    "Medical_Aid": "Medical Aid / Payor",
                    "Category": "Billing Category",
                },
            )
            fig_rev_bar.update_layout(
                plot_bgcolor="white",
                height=380,
                yaxis_tickprefix="$",
                yaxis_tickformat=",",
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="right",
                    x=1,
                ),
            )
            fig_rev_bar.update_xaxes(showgrid=False)
            fig_rev_bar.update_yaxes(showgrid=True, gridcolor="#E5E5E5")
            st.plotly_chart(fig_rev_bar, use_container_width=True)
        else:
            st.info("No reversals recorded for the selected year.")

        st.markdown(
            "**Key Finding:** The bulk of monetary reversals stem from Chronic Dialysis sessions under **State Health Fund** payors, suggesting potential delays or errors in pre-authorization confirmation prior to procedure entry."
        )

    st.success(
        "**Strategic Recommendation:** Implementing automated claim validation before submitting state medical aid invoices can reduce monthly administrative rework and financial leakage by up to ~6%."
    )