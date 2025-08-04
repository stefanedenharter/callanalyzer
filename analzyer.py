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
    <div class="version-badge">🔖 Version 1.9.0</div>
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

        # --- Calculate call duration in minutes ---
        df["Call Duration (s)"] = df["dateTimeDisconnect"] - df["dateTimeConnect"]
        df["Call Duration (min)"] = df["Call Duration (s)"] / 60

        keep_cols = [
            "User", "callingPartyNumber", "dateTimeConnect", "dateTimeDisconnect", "Call Category",
            "Date", "Month", "Weekday", "source_file", "Call Duration (s)", "Call Duration (min)"
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
    all_usernames = list(extension_name_map.values())
    weekday_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

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

        ## ----------- Stacked Side-by-Side Dual Axis Chart Function ----------- ##
        def stacked_side_by_side_chart_dual_axis(groupby_col, group_order, x_label, show_legend=False):
            grouped_calls = (
                df_filtered.groupby([groupby_col, 'Call Category'])
                .size()
                .unstack(fill_value=0)
                .reindex(index=group_order, fill_value=0)
                .reindex(columns=call_order, fill_value=0)
            )
            grouped_duration = (
                df_filtered.groupby([groupby_col, 'Call Category'])["Call Duration (min)"]
                .sum()
                .unstack(fill_value=0)
                .reindex(index=group_order, fill_value=0)
                .reindex(columns=call_order, fill_value=0)
            )

            x = np.arange(len(group_order))
            width = 0.35
            fig, ax1 = plt.subplots(figsize=(8, 4))
            ax2 = ax1.twinx()
            colors = plt.cm.tab10.colors

            # Stacked bar for Calls (ax1, left)
            bottom_calls = np.zeros(len(group_order))
            bars_calls = []
            for i, call_type in enumerate(call_order):
                bar = ax1.bar(x - width/2, grouped_calls[call_type], width,
                            bottom=bottom_calls, color=colors[i % 10], alpha=0.85)
                bars_calls.append(bar)
                bottom_calls += grouped_calls[call_type]

            # Stacked bar for Duration (ax2, right)
            bottom_dur = np.zeros(len(group_order))
            bars_dur = []
            for i, call_type in enumerate(call_order):
                bar = ax2.bar(x + width/2, grouped_duration[call_type], width,
                            bottom=bottom_dur, color=colors[i % 10], alpha=0.55,
                            hatch='//', edgecolor='gray', linewidth=0.5)
                bars_dur.append(bar)
                bottom_dur += grouped_duration[call_type]

            ax1.set_ylabel("Number of Calls")
            ax2.set_ylabel("Duration in Minutes")
            ax1.set_xlabel(x_label)
            ax1.set_xticks(x)
            ax1.set_xticklabels([str(g) for g in group_order], rotation=45, ha='right')
            ax1.set_title(f"Number of Calls & Duration by {x_label}")

            # Set y-limits for both axes to max of stacks + 10% margin
            ax1.set_ylim(0, max(bottom_calls.max(), 1) * 1.1)
            ax2.set_ylim(0, max(bottom_dur.max(), 1) * 1.1)

            # Legend placement and layout
            if show_legend:
                # Legend from the call bars (solid colors)
                handles = [bars_calls[i][0] for i in range(len(call_order))]
                labels = call_order
                leg = ax1.legend(handles, labels, title="Call Category", loc='upper left',
                                bbox_to_anchor=(1.02, 1), fontsize='small', frameon=True)
                fig.subplots_adjust(right=0.75)
            else:
                fig.subplots_adjust(right=0.95)  # Leave room on right side

            fig.tight_layout()
            return fig



        ## --- Chart 1: Monthly ---


        st.subheader("📊 Monthly: Calls & Duration (min)")
        fig1 = stacked_side_by_side_chart_dual_axis(
            groupby_col="Month",
            group_order=[pd.Period(m) for m in all_months] if all_months and isinstance(df_filtered['Month'].iloc[0], pd.Period) else all_months,
            x_label="Month",
            show_legend=True
        )
        st.pyplot(fig1)


        st.subheader("📊 Weekly: Calls & Duration (min)")
        fig2 = stacked_side_by_side_chart_dual_axis(
            groupby_col="Weekday",
            group_order=weekday_order,
            x_label="Weekday",
            show_legend=False
        )
        st.pyplot(fig2)

        st.subheader("📊 By User: Calls & Duration (min)")
        fig3 = stacked_side_by_side_chart_dual_axis(
            groupby_col="User",
            group_order=all_usernames,
            x_label="User",
            show_legend=False
        )
        st.pyplot(fig3)

