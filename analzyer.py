import streamlit as st
import pandas as pd
import numpy as np
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
    <div class="version-badge">🔖 Version 1.6.0</div>
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

# --- File uploader ---
uploaded_files = st.file_uploader(
    "Upload one or more Excel call report files (Raw Data tab):",
    type=["xls", "xlsx", "xlsm"],
    accept_multiple_files=True
)

def extract_data_from_excel(file):
    try:
        df = pd.read_excel(file, sheet_name="Raw Data", engine="openpyxl")
        df.columns = [str(col).strip() for col in df.columns]
        
        # --- Fix dateTimeConnect == 0 ---
        if "dateTimeConnect" in df.columns and "dateTimeDisconnect" in df.columns:
            mask = df["dateTimeConnect"] == 0
            df.loc[mask, "dateTimeConnect"] = df.loc[mask, "dateTimeDisconnect"] - 600
        
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
        df["Weekday"] = df["Date"].dt.day_name()

        df["source_file"] = getattr(file, 'name', None)  # Track source file if possible

        # --- Calculate call duration ---
        df["Call Duration (s)"] = df["dateTimeDisconnect"] - df["dateTimeConnect"]
        df["Call Duration (hr)"] = df["Call Duration (s)"] / 3600

        keep_cols = [
            "User", "callingPartyNumber", "dateTimeConnect", "dateTimeDisconnect", "Call Category",
            "Date", "Month", "Weekday", "source_file", "Call Duration (s)", "Call Duration (hr)"
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

    # --- Multi-select Filters ---
    col1, col2, col3 = st.columns(3)
    with col1:
        selected_users = st.multiselect(
            "Filter by User", sorted(user_ids), default=sorted(user_ids)
        )
    with col2:
        selected_types = st.multiselect(
            "Filter by Call Type", call_order, default=call_order
        )
    with col3:
        selected_months = st.multiselect(
            "Filter by Month", all_months, default=all_months
        )

    df_filtered = df_all.copy()
    if selected_users:
        df_filtered = df_filtered[df_filtered['User'].isin(selected_users)]
    if selected_types:
        df_filtered = df_filtered[df_filtered['Call Category'].isin(selected_types)]
    if selected_months:
        df_filtered = df_filtered[df_filtered['Month'].astype(str).isin(selected_months)]

    if df_filtered.empty:
        st.info("No call records match the selected filters.")
    else:
        st.dataframe(df_filtered)

        ## ----------- Grouped Bar Chart Helper Function ----------- ##
        def grouped_bar_chart(groupby_col, group_order, x_label):
            grouped_calls = (
                df_filtered.groupby([groupby_col, 'Call Category'])
                .size()
                .unstack(fill_value=0)
                .reindex(index=group_order, fill_value=0)
                .reindex(columns=call_order, fill_value=0)
            )
            grouped_duration = (
                df_filtered.groupby([groupby_col, 'Call Category'])["Call Duration (hr)"]
                .sum()
                .unstack(fill_value=0)
                .reindex(index=group_order, fill_value=0)
                .reindex(columns=call_order, fill_value=0)
            )

            x = np.arange(len(group_order))
            width = 0.35  # width of a bar
            fig, ax = plt.subplots(figsize=(max(6, len(group_order)), 4))

            n_types = len(call_order)
            for i, call_type in enumerate(call_order):
                # Calls
                ax.bar(x + i*width/(2*n_types), grouped_calls[call_type], width/(2*n_types),
                       label=f"{call_type} (Calls)")
                # Duration
                ax.bar(x + width/2 + i*width/(2*n_types), grouped_duration[call_type], width/(2*n_types),
                       label=f"{call_type} (Hours)", alpha=0.7, hatch='//')

            ax.set_xticks(x + width/4)
            ax.set_xticklabels([str(g) for g in group_order], rotation=45)
            ax.set_ylabel("Count / Hours")
            ax.set_xlabel(x_label)
            handles, labels = ax.get_legend_handles_labels()
            # Remove duplicates in legend
            unique = dict(zip(labels, handles))
            ax.legend(unique.values(), unique.keys(), fontsize="small", title_fontsize="small", ncol=2)
            ax.yaxis.set_major_locator(mticker.MaxNLocator(integer=True))
            ax.set_title(f"Calls and Duration by {x_label}")
            return fig

        ## --- Chart 1: Monthly ---
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("📊 Monthly: Number of Calls & Total Duration")
            fig1 = grouped_bar_chart(
                groupby_col="Month",
                group_order=[pd.Period(m) for m in all_months] if all_months and isinstance(df_filtered['Month'].iloc[0], pd.Period) else all_months,
                x_label="Month"
            )
            st.pyplot(fig1)

        ## --- Chart 2: Weekday ---
        weekday_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        with col2:
            st.subheader("📊 Weekly: Number of Calls & Total Duration")
            fig2 = grouped_bar_chart(
                groupby_col="Weekday",
                group_order=weekday_order,
                x_label="Weekday"
            )
            st.pyplot(fig2)

        ## --- Chart 3: User ---
        st.subheader("📊 Total by User: Number of Calls & Total Duration")
        all_usernames = list(extension_name_map.values())
        fig3 = grouped_bar_chart(
            groupby_col="User",
            group_order=all_usernames,
            x_label="User"
        )
        st.pyplot(fig3)
