import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

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
    <div class="version-badge">🔖 Version 1.5.2</div>
    """,
    unsafe_allow_html=True
)

# --- Extension mapping ---
extension_name_map = {
    '7773': 'AD', '7789': 'PF', '7725': 'CB', '7729': 'SM',
    '7768': 'CM', '7722': 'FF', '7783': 'TM', '7769': 'PB',
    '7721': 'KS', '7787': 'DK', '7776': 'DH', '7779': 'FM',
    "7784": "MV"
}
valid_extensions = set(extension_name_map.keys())

uploaded_files = st.file_uploader(
    "Upload one or more Excel call report files (Raw Data tab):",
    type=["xls", "xlsx", "xlsm"],
    accept_multiple_files=True
)

def extract_data_from_excel(file):
    try:
        df = pd.read_excel(file, sheet_name="Raw Data", engine="openpyxl")
        df.columns = [str(col).strip() for col in df.columns]

        part_cols = [
            "finalCalledPartyNumberPartition",
            "originalCalledPartyNumberPartition",
            "callingPartyNumberPartition"
        ]
        df["Call Category"] = df[part_cols].bfill(axis=1).iloc[:, 0]
        df = df.dropna(subset=["Call Category"])

        df["callingPartyNumber"] = df["callingPartyNumber"].astype(str).str.extract(r'(\d{4})')[0]
        df = df[df["callingPartyNumber"].isin(valid_extensions)]
        df["User"] = df["callingPartyNumber"].map(extension_name_map)

        df["Date"] = pd.to_datetime(df["dateTimeConnect"], unit='s', errors='coerce')
        df["Month"] = df["Date"].dt.to_period('M')

        df["source_file"] = getattr(file, 'name', None)  # Track source file if possible

        keep_cols = [
            "User", "callingPartyNumber", "dateTimeConnect", "dateTimeDisconnect", "Call Category", "Date", "Month", "source_file"
        ]
        df = df[keep_cols].rename(columns={
            "callingPartyNumber": "Extension",
            "dateTimeConnect": "Connect Time (Unix)",
            "dateTimeDisconnect": "Disconnect Time (Unix)"
        })

        return df
    except Exception as e:
        st.error(f"Error reading Excel: {e}")
        return pd.DataFrame()

if st.button("Analyze"):
    if uploaded_files:
        all_data = []
        for file in uploaded_files:
            df = extract_data_from_excel(file)
            if not df.empty:
                all_data.append(df)
        if all_data:
            df_all = pd.concat(all_data, ignore_index=True)
            st.session_state["df_all"] = df_all
        else:
            st.warning("No valid call data found in uploaded files.")
    else:
        st.warning("Please upload at least one Excel file.")

# --- Display & Visuals ---
if "df_all" in st.session_state:
    df_all = st.session_state["df_all"]

    st.subheader("📋 Raw Call Records")

    call_order = sorted(df_all['Call Category'].dropna().unique())
    user_ids = df_all['User'].dropna().unique().tolist()
    all_months = sorted(df_all['Month'].dropna().astype(str).unique().tolist())

    # --- Filters in one row ---
    col1, col2, col3 = st.columns(3)
    with col1:
        selected_user = st.selectbox("Filter by User", ["All"] + sorted(user_ids))
    with col2:
        selected_type = st.selectbox("Filter by Call Type", ["All"] + call_order)
    with col3:
        selected_month = st.selectbox("Filter by Month", ["All"] + all_months)

    df_filtered = df_all.copy()
    if selected_user != "All":
        df_filtered = df_filtered[df_filtered['User'] == selected_user]
    if selected_type != "All":
        df_filtered = df_filtered[df_filtered['Call Category'] == selected_type]
    if selected_month != "All":
        df_filtered = df_filtered[df_filtered['Month'].astype(str) == selected_month]

    if df_filtered.empty:
        st.info("No call records match the selected filters.")
    else:
        st.dataframe(df_filtered)

        # --- Chart 1: Monthly call distribution ---
        grouped = (
            df_filtered.groupby(['Month', 'Call Category'])
            .size()
            .unstack(fill_value=0)
            .sort_index()
        )
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("📊 Monthly Call Volume (Filtered)")
            fig1, ax1 = plt.subplots(figsize=(5, 3))
            grouped.plot(kind='bar', stacked=True, ax=ax1)
            ax1.yaxis.set_major_locator(mticker.MaxNLocator(integer=True))
            ax1.set_ylabel("Calls")
            ax1.set_xlabel("Month")
            ax1.set_title("Calls by Month")
            ax1.legend(title="Call Type", fontsize="small", title_fontsize="small")
            st.pyplot(fig1)

        # --- Chart 1.5: Weekly call distribution ---
        with col2:
            st.subheader("📊 Weekly Call Volume (Filtered)")
            df_filtered['Weekday'] = df_filtered['Date'].dt.day_name()
            weekday_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
            weekly_grouped = (
                df_filtered.groupby(['Weekday', 'Call Category'])
                .size()
                .unstack(fill_value=0)
                .reindex(index=weekday_order)
            )
            fig3, ax3 = plt.subplots(figsize=(5, 3))
            weekly_grouped.plot(kind='bar', stacked=True, ax=ax3)
            ax3.yaxis.set_major_locator(mticker.MaxNLocator(integer=True))
            ax3.set_ylabel("Calls")
            ax3.set_xlabel("Weekday")
            ax3.set_title("Calls by Weekday")
            ax3.legend(title="Call Type", fontsize="small", title_fontsize="small")
            st.pyplot(fig3)

        # --- Chart 2: Total by user ---
        st.subheader("📊 Total Call Volume by User (All Data)")
        all_usernames = list(extension_name_map.values())
        grouped_users = (
            df_all.groupby(['User', 'Call Category'])
            .size()
            .unstack(fill_value=0)
            .reindex(index=all_usernames, fill_value=0)
        )
        grouped_users['Total'] = grouped_users.sum(axis=1)
        grouped_users = grouped_users.sort_values(by='Total', ascending=False).drop(columns='Total')

        fig2, ax2 = plt.subplots(figsize=(10, 4))
        grouped_users.plot(kind='bar', stacked=True, ax=ax2)
        ax2.yaxis.set_major_locator(mticker.MaxNLocator(integer=True))
        ax2.set_ylabel("Calls")
        ax2.set_xlabel("User")
        ax2.set_title("Total Calls by User")
        ax2.legend(title="Call Type", fontsize="small", title_fontsize="small")
        st.pyplot(fig2)
