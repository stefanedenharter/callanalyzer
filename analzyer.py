import streamlit as st
import pandas as pd
import re
import matplotlib.pyplot as plt
import io

# Extension-to-Name mapping
extension_name_map = {
    '7773': 'AD', '7789': 'PF', '7725': 'CB', '7729': 'SM',
    '7768': 'CM', '7722': 'FF', '7783': 'TM', '7769': 'PB',
    '7721': 'KS', '7787': 'DK', '7776': 'DH', '7779': 'FM'
}
valid_extensions = set(extension_name_map.keys())

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

# UI
st.title("📞 Phone Call Report Analyzer")

uploaded_files = st.file_uploader(
    "Upload one or more HTML call report files:",
    type="html",
    accept_multiple_files=True
)

# Analyze button and store result in session state
if st.button("Analyze"):
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

            # Ensure callingPartyNumber is string
            df_all['callingPartyNumber'] = df_all['callingPartyNumber'].astype(str)

            # Filter only valid extensions
            df_all = df_all[df_all['callingPartyNumber'].isin(valid_extensions)]

            # Replace User ID with mapped name
            df_all['callingPartyUnicodeLoginUserID'] = df_all['callingPartyNumber'].map(extension_name_map)

            # Convert date column
            if 'dateTimeOrigination' in df_all.columns:
                df_all['dateTimeOrigination'] = pd.to_datetime(df_all['dateTimeOrigination'], unit='s', errors='coerce')
                df_all['Month'] = df_all['dateTimeOrigination'].dt.to_period('M')

            # Rename columns for clarity
            column_renames = {
                'callingPartyUnicodeLoginUserID': 'User',
                'callingPartyNumber': 'Extension',
                'finalCalledPartyPattern': 'Call Type',
                'dateTimeOrigination': 'Date',
                'duration': 'Duration (s)'
            }
            df_all = df_all.rename(columns=column_renames)

            st.session_state["df_all"] = df_all
        else:
            st.warning("No valid call data found in uploaded files.")
    else:
        st.warning("Please upload at least one HTML file to proceed.")

# Use session state to persist data and enable interactivity
if "df_all" in st.session_state:
    df_all = st.session_state["df_all"]

    st.subheader("📋 Raw Call Records")

    # Filters
    user_ids = df_all['User'].dropna().unique().tolist()
    call_types = df_all['Call Type'].dropna().unique().tolist()

    selected_user = st.selectbox("Filter by User", ["All"] + sorted(user_ids))
    selected_type = st.selectbox("Filter by Call Type", ["All"] + sorted(call_types))

    df_filtered = df_all.copy()
    if selected_user != "All":
        df_filtered = df_filtered[df_filtered['User'] == selected_user]
    if selected_type != "All":
        df_filtered = df_filtered[df_filtered['Call Type'] == selected_type]

    if df_filtered.empty:
        st.info("No call records match the selected filters.")
    else:
        st.dataframe(df_filtered)

        # Bar chart
        st.subheader("📊 Monthly Call Volume")
        if 'Month' in df_filtered.columns:
            call_counts = df_filtered['Month'].value_counts().sort_index()
            fig, ax = plt.subplots()
            if not call_counts.empty:
                call_counts.plot(kind='bar', ax=ax)
                ax.set_ylabel("Number of Calls")
                ax.set_xlabel("Month")
                ax.set_title("Calls per Month")
                st.pyplot(fig)
            else:
                st.info("No data available for chart.")
