"""
Optional Streamlit dashboard for Part D analytics.
Reads marts from Snowflake via environment variables.
Run: streamlit run streamlit_app.py
"""

import streamlit as st
import pandas as pd
from snowflake.connector import connect
import os

@st.cache_resource
def get_snowflake_connection():
    """Create and cache Snowflake connection."""
    return connect(
        account=os.getenv('SNOWFLAKE_ACCOUNT'),
        user=os.getenv('SNOWFLAKE_USER'),
        role=os.getenv('SNOWFLAKE_ROLE'),
        warehouse=os.getenv('SNOWFLAKE_WAREHOUSE'),
        database=os.getenv('SNOWFLAKE_DATABASE'),
        private_key_path=os.getenv('SNOWFLAKE_PRIVATE_KEY_PATH'),
        private_key_passphrase=os.getenv('SNOWFLAKE_PRIVATE_KEY_PASSPHRASE'),
    )

def load_data(query):
    """Load data from Snowflake."""
    try:
        conn = get_snowflake_connection()
        cursor = conn.cursor()
        cursor.execute(query)
        return pd.DataFrame(cursor.fetchall(), columns=[d[0] for d in cursor.description])
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return pd.DataFrame()

st.set_page_config(page_title="Part D Analytics", layout="wide")
st.title("Medicare Part D Analytics Dashboard")

st.markdown("""
Analytics on 500K prescriber claims from CMS public data.
Data updates via dbt models in Snowflake.
""")

# Tab 1: Top Drugs by Cost
st.header("Top 10 Most Expensive Drugs")
top_drugs = load_data("""
    SELECT RANK, DRUG_NAME, GENERIC_NAME, TOTAL_COST_USD, PRESCRIBER_COUNT
    FROM PARTD_LAB.MARTS.FCT_TOP_DRUGS_BY_COST
    LIMIT 10
    ORDER BY RANK
""")
if not top_drugs.empty:
    st.bar_chart(top_drugs.set_index('DRUG_NAME')['TOTAL_COST_USD'])
    st.dataframe(top_drugs, use_container_width=True)

# Tab 2: Brand vs Generic
st.header("Brand vs Generic Market Share")
brand_generic = load_data("""
    SELECT SPECIALTY, DRUG_TYPE, TOTAL_COST_USD, PCT_OF_COST
    FROM PARTD_LAB.MARTS.FCT_BRAND_VS_GENERIC_SHARE
    ORDER BY SPECIALTY, DRUG_TYPE
""")
if not brand_generic.empty:
    col1, col2 = st.columns(2)
    with col1:
        st.write("Brand vs Generic by Specialty")
        st.dataframe(brand_generic, use_container_width=True)

# Tab 3: Specialty Cost Analysis
st.header("Cost by Specialty & State")
specialty_costs = load_data("""
    SELECT SPECIALTY, PROVIDER_STATE, TOTAL_COST_USD, PRESCRIBER_COUNT, COST_PER_PRESCRIBER
    FROM PARTD_LAB.MARTS.FCT_COST_BY_SPECIALTY_STATE
    ORDER BY TOTAL_COST_USD DESC
    LIMIT 20
""")
if not specialty_costs.empty:
    st.bar_chart(specialty_costs.set_index('SPECIALTY')['TOTAL_COST_USD'])
    st.dataframe(specialty_costs, use_container_width=True)

# Tab 4: Opioid Prescribing
st.header("Opioid Prescribing by Specialty")
opioid = load_data("""
    SELECT SPECIALTY, DRUG_CLASS, TOTAL_CLAIMS, PCT_OF_CLAIMS, TOTAL_COST_USD
    FROM PARTD_LAB.MARTS.FCT_OPIOID_PRESCRIBING_BY_SPECIALTY
    ORDER BY SPECIALTY, DRUG_CLASS
""")
if not opioid.empty:
    st.dataframe(opioid, use_container_width=True)

st.markdown("---")
st.caption("Data sourced from CMS Medicare Part D public data. Updated via dbt.")
