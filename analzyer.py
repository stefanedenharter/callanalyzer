import streamlit as st
import pandas as pd
import os
import re
from pathlib import Path
import matplotlib.pyplot as plt

# Function to extract CSV from HTML
def extract_csv_from_html(file_path):
    text = Path(file_path).read_text(encoding='utf-8')
    match = re.search(r'gk_fileData\s*=\s*{.*?:(?P<q>[\'\"])(?P<data>.*?)(?P=q)};', text, re.DOTALL)
    if not match:
        return pd.DataFrame()
    csv_data = match.group("data").encode('utf-8').decode('unicode_escape')
    df = pd.read_csv(pd.compat.StringIO(csv_data))
    return df

# Streamlit UI
st.title("📞 Phone Call Report Analyzer")

# Folder selection
folder_path = st.text_input("Enter path to folder with HTML files:")

if folder_path and os.path.isdir(folder_path):
    all_data = []
    for file in os.listdir(folder_path):
        if file.lower().endswith(".html"):
            full_path = os.path.join(folder_path, file)
            df = extract_csv_from_html(full_path)
            if not df.empty:
                df['source_file'] = file  # Optional tracking
                all_data.append(df)

    if all_data:
        df_all = pd.concat(all_data, ignore_index=True)

        # Normalize columns if needed
        df_all.columns = [col.strip() for col in df_all.columns]

        # Convert datetime if available
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
        st.warning("No valid HTML reports found in the folder.")
else:
    st.info("Please enter a valid folder path to begin.")
