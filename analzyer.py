import streamlit as st
import pandas as pd
import re
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import io

# --- UI setup ---
st.set_page_config(page_title="Call Report Analyzer", layout="wide")
st.title("📞 Phone Call Report Analyzer")

st.markdown(
    """
    <style>
    .version-badge {
        position: absolute;
        top: 0.5rem;
        right: 1rem;
        background-color: #e0e0e0;
        color: #000;
        padding: 0.25rem 0.5rem;
        border-radius: 5px;
        font-size: 0.85rem;
        z-index: 1000;
    }
    </style>
    <div class="version-badge">🔖 Version 1.3.1</div>
    """,
    unsafe_allow_html=True
)

# --- Extension mapping ---
extension_name_map = {
    '7773': 'AD', '7789': 'PF', '7725': 'CB', '7729': 'SM',
    '7768': 'CM', '7722': 'FF', '7783': 'TM', '7769': 'PB',
    '7721': 'KS', '7787': 'DK', '7776': 'DH', '7779': 'FM'
}
valid_extensions = set(extension_name_map.keys())

# --- Extract embedded CSV from HTML ---
def extract_csv_from_html_bytes(file_bytes):
    try:
        text = file_bytes.decode('utf-8')
        match = re.search(r'gk_fileData\s*=\s*{.*?:(?P<q>["\'])(?P<data>.*?)(?P=q)};', text, re.DOTALL)
        if not match:
            return pd.DataFrame()
        csv_data = match.group("data").encode('utf-8').decode('unicode_escape')
        return pd.read_csv(io.StringIO(csv_data))
    except Exception as e:
        st.error(f"Error parsing file: {e}")
        return pd.DataFrame()

# --- Classify call type from dial pattern ---
def classify_from_dial_pattern(val):
    if pd.isna(val):
        return "Unknown"
    val = str(val).strip().lower()
    if val == "mobile":
        return "Mobile"
    if val == "international":
        return "International"
    if val == "other external":
        return "Other External"
    if val.startswith('+') or val.startswith('900448') or val.startswith('9.00'):
        return "International"
    elif re.fullmatch(r'\d{7}', val):
        return "Other External"
    elif re.match(r'^(7|8|9)\d{6,}', val):
        return "Mobile"
    elif val.startswith('9.08') or 'mobile' in val:
        return "Mobile"
    else:
        return "Other External"

# --- File uploader ---
uploaded_files = st.file_uploader(
    "Upload one or more HTML call report files:",
    type="html",
    accept_multiple_files=True
)

# --- Run analysis ---
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

            # Filter users and map names
            if 'callingPartyNumber' in df_all.columns:
                df_all['callingPartyNumber'] = (
                    df_all['callingPartyNumber']
                    .astype(str)
                    .str.strip()
                    .str.extract(r'(\d{4})')[0]
                )
                df_all = df_all[df_all['callingPartyNumber'].isin(valid_extensions)]
                df_all['callingPartyUnicodeLoginUserID'] = df_all['callingPartyNumber'].map(extension_name_map)

            # Date formatting
            if 'dateTimeOrigination' in df_all.columns:
                df_all['dateTimeOrigination'] = pd.to_datetime(
                    df_all['dateTimeOrigination'], unit='s', errors='coerce')
                df_all['Month'] = df_all['dateTimeOrigination'].dt.to_period('M')

            # Classify Call Category using Dial Pattern
            pattern_col = 'finalCalledPartyPattern' if 'finalCalledPartyPattern' in df_all.columns else 'Dial Pattern'
            if pattern_col in df_all.columns:
                df_all['Call Category'] = df_all[pattern_col].apply(classify_from_dial_pattern)
            else:
                df_all['Call Category'] = "Unknown"

            # Rename columns
            df_all = df_all.rename(columns={
                'callingPartyUnicodeLoginUserID': 'User',
                'callingPartyNumber': 'Extension',
                'finalCalledPartyPattern': 'Dial Pattern',
                'dateTimeOrigination': 'Date'
            })

            st.session_state["df_all"] = df_all
        else:
            st.warning("No valid call data found.")
    else:
        st.warning("Please upload at least one HTML file.")

# --- Display & Visuals ---
if "df_all" in st.session_state:
    df_all = st.session_state["df_all"]

    st.subheader("📋 Raw Call Records")

    user_ids = df_all['User'].dropna().unique().tolist()
    call_types = df_all['Call Category'].dropna().unique().tolist()

    selected_user = st.selectbox("Filter by User", ["All"] + sorted(user_ids))
    selected_type = st.selectbox("Filter by Call Type", ["All"] + sorted(call_types))

    df_filtered = df_all.copy()
    if selected_user != "All":
        df_filtered = df_filtered[df_filtered['User'] == selected_user]
    if selected_type != "All":
        df_filtered = df_filtered[df_filtered['Call Category'] == selected_type]

    if df_filtered.empty:
        st.info("No call records match the selected filters.")
    else:
        st.dataframe(df_filtered)

        call_order = ['International', 'Other External', 'Mobile']

        # --- Chart 1: Monthly view ---
        st.subheader("📊 Monthly Call Volume by Call Type (Filtered)")
        grouped = (
            df_filtered.groupby(['Month', 'Call Category'])
            .size()
            .unstack(fill_value=0)
            .reindex(columns=call_order, fill_value=0)
            .sort_index()
        )
        fig1, ax1 = plt.subplots()
        grouped.plot(kind='bar', stacked=True, ax=ax1)
        ax1.yaxis.set_major_locator(mticker.MaxNLocator(integer=True))
        ax1.set_ylabel("Number of Calls")
        ax1.set_xlabel("Month")
        ax1.set_title("Calls per Month by Call Type")
        ax1.legend(title="Call Type")
        st.pyplot(fig1)

        # --- Chart 2: Total by user ---
        st.subheader("📊 Total Call Volume by User (All Data)")
        all_usernames = list(extension_name_map.values())
        grouped_users = (
            df_all.groupby(['User', 'Call Category'])
            .size()
            .unstack(fill_value=0)
            .reindex(index=all_usernames, columns=call_order, fill_value=0)
        )
        grouped_users['Total'] = grouped_users.sum(axis=1)
        grouped_users = grouped_users.sort_values(by='Total', ascending=False).drop(columns='Total')

        fig2, ax2 = plt.subplots()
        grouped_users.plot(kind='bar', stacked=True, ax=ax2)
        ax2.yaxis.set_major_locator(mticker.MaxNLocator(integer=True))
        ax2.set_ylabel("Number of Calls")
        ax2.set_xlabel("User")
        ax2.set_title("Total Calls by User (All Files)")
        ax2.legend(title="Call Type")
        st.pyplot(fig2)
