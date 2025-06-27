# Call Analyzer v1.6.4
# This Streamlit app processes internal-to-external call reports
# Classification logic is based on 'finalCalledPartyPattern' since 'Call Type' column does not exist

import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import os
import re
from datetime import datetime
from io import StringIO

st.set_page_config(layout="wide")
st.markdown("<div style='text-align: right;'>🔹 <b>Call Report Analyzer v1.6.4</b></div>", unsafe_allow_html=True)

# --- Function to classify call category from dial pattern ---
def classify_call_category(pattern):
    if pd.isna(pattern):
        return "Other External"
    pattern = str(pattern)
    if "9.00!" in pattern:
        return "International"
    elif "9.08[365789]XXXXXXX" in pattern or re.match(r"9\\.0[1-9]\\d{7}$", pattern):
        return "Mobile"
    else:
        return "Other External"

# --- Mapping of Extensions to User IDs ---
ext_mapping = {
    "7773": "AD", "7789": "PF", "7725": "CB", "7729": "SM",
    "7768": "CM", "7722": "FF", "7783": "TM", "7769": "PB",
    "7721": "KS", "7787": "DK", "7776": "DH", "7779": "FM"
}

# --- File uploader section ---
st.title("📞 Internal to External Call Report Analyzer")
st.write("Upload one or more HTML files containing embedded call record tables.")

uploaded_files = st.file_uploader("Upload HTML files", accept_multiple_files=True, type="html")

# --- Analyze button ---
analyze = st.button("Analyze")

if analyze and uploaded_files:
    df_all = pd.DataFrame()

    for uploaded_file in uploaded_files:
        text = uploaded_file.read().decode("utf-8")

        # Updated flexible regex to extract gk_fileData
        match = re.search(r'gk_fileData\s*=\s*{[^}]*?["\'](?P<filename>[^"\']+)["\']\s*:\s*["\'](?P<data>.*)["\']\s*}', text, re.DOTALL)
        if match:
            csv_text = match.group("data").replace('\\r\\n', '\n').replace('\\"', '"')
            try:
                df = pd.read_csv(StringIO(csv_text))
                df['source_file'] = uploaded_file.name
                df_all = pd.concat([df_all, df], ignore_index=True)
            except Exception as e:
                st.warning(f"Failed to parse CSV from {uploaded_file.name}: {e}")
        else:
            st.warning(f"No embedded CSV data found in {uploaded_file.name}.")

    # --- Standardize column names ---
    df_all.columns = [col.strip() for col in df_all.columns]

    # --- Normalize and rename columns robustly ---
    col_rename = {
        "datetimeorigination": "Timestamp",
        "callingpartynumber": "Extension",
        "callingpartyunicodeloginuserid": "UserID",
        "finalcalledpartynumber": "CalledNumber",
        "finalcalledpartypattern": "DialPattern"
    }
    rename_map = {col: col_rename[col.lower()] for col in df_all.columns if col.lower() in col_rename}
    df_all.rename(columns=rename_map, inplace=True)

    # --- Filter only known extensions ---
    df_all = df_all[df_all['Extension'].astype(str).isin(ext_mapping.keys())].copy()

    # --- Add mapped user IDs ---
    df_all['User'] = df_all['Extension'].astype(str).map(ext_mapping)

    # --- Add Call Category ---
    df_all['Call Category'] = df_all['DialPattern'].apply(classify_call_category)

    # --- Convert Timestamp ---
    df_all['Date'] = pd.to_datetime(df_all['Timestamp'], unit='s')
    df_all['Month'] = df_all['Date'].dt.to_period("M").astype(str)
    df_all['Weekday'] = df_all['Date'].dt.day_name()

    # --- Filter controls ---
    col1, col2, col3 = st.columns(3)
    with col1:
        selected_user = st.selectbox("Select User", options=["All"] + sorted(df_all['User'].dropna().unique().tolist()))
    with col2:
        selected_call_type = st.selectbox("Select Call Type", options=["All"] + ['International', 'Other External', 'Mobile'])
    with col3:
        selected_month = st.selectbox("Select Month", options=["All"] + sorted(df_all['Month'].unique().tolist()))

    # --- Apply filters ---
    df_filtered = df_all.copy()
    if selected_user != "All":
        df_filtered = df_filtered[df_filtered['User'] == selected_user]
    if selected_call_type != "All":
        df_filtered = df_filtered[df_filtered['Call Category'] == selected_call_type]
    if selected_month != "All":
        df_filtered = df_filtered[df_filtered['Month'] == selected_month]

    # --- Call counts by month ---
    call_order = ['International', 'Other External', 'Mobile']
    call_counts = (
        df_filtered.groupby(['Month', 'Call Category'])
        .size()
        .unstack(fill_value=0)
        .reindex(columns=call_order, fill_value=0)
    )

    st.subheader("📊 Monthly Call Volume by Call Type (Filtered)")
    if not call_counts.empty:
        fig, ax = plt.subplots(figsize=(8, 4))
        call_counts.plot(kind='bar', stacked=True, ax=ax, legend=True)
        ax.set_ylabel("Number of Calls")
        ax.set_xlabel("Month")
        ax.yaxis.set_major_locator(mticker.MaxNLocator(integer=True))
        ax.legend(title="Call Type", fontsize="small", title_fontsize="small")
        st.pyplot(fig)
    else:
        st.warning("No call data available for the selected filters.")

    # --- Weekly chart ---
    weekday_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    weekly_grouped = (
        df_filtered.groupby(['Weekday', 'Call Category'])
        .size()
        .unstack(fill_value=0)
        .reindex(index=weekday_order)
        .reindex(columns=call_order, fill_value=0) 
    )

    st.subheader("📊 Weekly Call Volume by Call Type (Filtered)")
    if not weekly_grouped.empty:
        fig3, ax3 = plt.subplots(figsize=(8, 4))
        weekly_grouped.plot(kind='bar', stacked=True, ax=ax3)
        ax3.yaxis.set_major_locator(mticker.MaxNLocator(integer=True))
        ax3.set_ylabel("Number of Calls")
        ax3.set_xlabel("Weekday")
        ax3.set_title("Calls per Weekday by Call Type")
        ax3.legend(title="Call Type", fontsize="small", title_fontsize="small")
        st.pyplot(fig3)
    else:
        st.warning("No weekly call data available for the selected filters.")

    # --- All-user chart ---
    st.subheader("📊 Total Calls by User (All Months)")
    all_users = pd.DataFrame(index=ext_mapping.values())
    total_counts = (
        df_all.groupby(['User', 'Call Category'])
        .size()
        .unstack(fill_value=0)
        .reindex(columns=call_order, fill_value=0)
    )
    total_counts = all_users.join(total_counts, how='left').fillna(0).astype(int)
    total_counts['Total'] = total_counts.sum(axis=1)
    total_counts = total_counts.sort_values(by='Total', ascending=False)

    if not total_counts.empty:
        fig2, ax2 = plt.subplots(figsize=(8, 4))
        total_counts[call_order].plot(kind='bar', stacked=True, ax=ax2)
        ax2.yaxis.set_major_locator(mticker.MaxNLocator(integer=True))
        ax2.set_ylabel("Number of Calls")
        ax2.set_xlabel("User")
        ax2.set_title("Total Calls per User by Call Type")
        ax2.legend(title="Call Type", fontsize="small", title_fontsize="small")
        st.pyplot(fig2)
    else:
        st.warning("No overall call data available for known users.")

else:
    st.info("Please upload at least one HTML file and click 'Analyze'.")
