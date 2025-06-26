import streamlit as st
import pandas as pd
import re
from pathlib import Path
import matplotlib.pyplot as plt
import io

# Function to extract CSV data from HTML content
def extract_csv_from_html_bytes(file_bytes):
    try:
        text = file_bytes.decode('utf-8')
        match = re.search(r'gk_fileData\s*=\s*{.*?:(?P<q>["\'])(?P<data>.*?)(?P=q)};', text, re.DOTALL)
        if not match:
            return pd.DataFrame()
        csv_data = match.group("data").encode('utf-8').decode('unicode_escape')
        df = pd.read_csv(io.StringIO(csv_data))
        return df
    except Exception as e:
        st.error(f"Error parsing file: {e}")
        return pd.DataFrame()

# Streamlit UI
st.title("📞 Phone Call Report Analyzer")

uploaded_files = st.file_uploader(
    "Upload one or more HTML call report files:",
    type="html",
    accept_multiple_files=True
)

analyze_clicked = st.button("Analyze")

if analyze_clicked:
    if uploaded_files:
        all_data = []
        for uploaded_file in uploaded_files:
            file_bytes = uploaded_file.read()
            df = extract_csv_from_html_bytes(file_bytes)
            if not df.empty:
                df['source_file'] = uploaded_file.name
                all_data.append(df)

        if all_data:
            df_all = pd.concat(all_data, ignore_index=True)
            df_all.columns = [col.strip() for col in df_all.columns]

            if 'dateTimeOrigination' in df_all.columns:
                df_all['dateTimeOrigination'] = pd.to_datetime(df_all['dateTimeOrigination'], unit='s', errors='coerce')
                df_all['Month'] = df_all['dateTimeOrigination'].dt.to_period('M')

            st.subheader("📋 Raw Call Records")

            # Filters
            user_ids = df_all['callingPartyUnicodeLoginUserID'].dropna().unique().tolist()
            call_types = df_all['finalCalledPartyPattern'].dropna().unique().tolist()

            selected_user = st.selectbox("Filter by User ID", ["All"] + sorted(user_ids))
            selected_type = st.selectbox("Filter by Call Type", ["All"] + sorted(call_types))

            df_filtered = df_all.copy()
            if selected_user != "All":
                df_filtered = df_filtered[df_filtered['callingPartyUnicodeLoginUserID'] == selected_user]
            if selected_type != "All":
                df_filtered = df_filtered[df_filtered['finalCalledPartyPattern'] == selected_type]

            st.dataframe(df_filtered)

            # Bar chart
            st.subheader("📊 Monthly Call Volume")
            if 'Month' in df_filtered.columns:
                call_counts = df_filtered['Month'].value_counts().sort_index()
                fig, ax = plt.subplots()
                call_counts.plot(kind='bar', ax=ax)
                ax.set_ylabel("Number of Calls")
                ax.set_xlabel("Month")
                ax.set_title("Calls per Month")
                st.pyplot(fig)
        else:
            st.warning("No valid call data found in uploaded files.")
    else:
        st.warning("Please upload at least one HTML file to proceed.")
