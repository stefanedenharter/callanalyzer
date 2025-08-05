import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import pytz

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
    <div class="version-badge">🔖 Version 2.1.0</div>
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

        # Fix dateTimeConnect == 0
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

        df["source_file"] = getattr(file, 'name', None)

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

def plotly_stacked_side_by_side(df, group_col, group_order, call_order, title, xaxis_title):
    counts = (
        df.groupby([group_col, 'Call Category'])
        .size()
        .unstack(fill_value=0)
        .reindex(index=group_order, fill_value=0)
        .reindex(columns=call_order, fill_value=0)
    )
    durations = (
        df.groupby([group_col, 'Call Category'])["Call Duration (min)"]
        .sum()
        .unstack(fill_value=0)
        .reindex(index=group_order, fill_value=0)
        .reindex(columns=call_order, fill_value=0)
    )

    fig = go.Figure()
    px_colors = px.colors.qualitative.Plotly

    # Add calls bars (left group) on primary y-axis (y)
    for i, call_cat in enumerate(call_order):
        fig.add_trace(go.Bar(
            name=f"{call_cat}",
            x=[str(x) for x in group_order],
            y=counts[call_cat],
            offsetgroup=0,
            marker_color=px_colors[i % len(px_colors)],
            hovertemplate=f"Call Category: {call_cat}<br>Count: "+"%{y}<extra></extra>",
            showlegend=True
        ))

    # Add durations bars (right group) on secondary y-axis (y2)
    for i, call_cat in enumerate(call_order):
        fig.add_trace(go.Bar(
            name=f"{call_cat} (Duration min)",
            x=[str(x) for x in group_order],
            y=durations[call_cat],
            offsetgroup=1,
            marker_color=px_colors[i % len(px_colors)],
            opacity=0.6,
            hovertemplate=f"Call Category: {call_cat}<br>Duration (min): "+"%{y:.1f}<extra></extra>",
            yaxis='y2',           # <-- assign to second y-axis here
            showlegend=False
        ))

    fig.update_layout(
        barmode='stack',
        title=title,
        xaxis_title=xaxis_title,
        yaxis=dict(
            title="Call Count",
            side='left',
            showgrid=True,
            zeroline=True
        ),
        yaxis2=dict(
            title="Duration (min)",
            overlaying='y',
            side='right',
            showgrid=False,
            zeroline=False
        ),
        legend=dict(
            title_text="",
            traceorder="grouped",
            yanchor="top",
            y=0.99,
            xanchor="left",
            x=0.01
        ),
        margin=dict(l=40, r=80, t=60, b=40),  # add extra right margin for second y-axis
        height=450,
        width=900
    )
    return fig


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

if "df_all" in st.session_state:
    df_all = st.session_state["df_all"]

    call_order = sorted(df_all['Call Category'].dropna().unique())
    user_ids = df_all['User'].dropna().unique().tolist()
    all_usernames = list(extension_name_map.values())
    weekday_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

    now = pd.Timestamp.now()
    last_12_months = pd.period_range(end=now.to_period('M'), periods=12).tolist()
    last_12_months_str = [str(m) for m in last_12_months]

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
        all_months = sorted(set(last_12_months_str + [str(m) for m in df_all['Month'].unique()]))
        selected_months = st.multiselect(
            "Filter by Month", all_months, default=last_12_months_str
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
        # Monthly chart limited to last 12 months
        df_monthly = df_filtered[df_filtered['Month'].astype(str).isin(last_12_months_str)]

        st.subheader("📊 Monthly: Call Count & Duration — Last 12 Months")
        fig_monthly = plotly_stacked_side_by_side(df_monthly, "Month", last_12_months_str, call_order,
                                                    xaxis_title="Month")
        st.plotly_chart(fig_monthly, use_container_width=True)

        st.subheader("📊 Weekday: Call Count & Duration")
        fig_weekly = plotly_stacked_side_by_side(df_filtered, "Weekday", weekday_order, call_order,
                                                 xaxis_title="Weekday")
        st.plotly_chart(fig_weekly, use_container_width=True)

        st.subheader("📊 By User: Call Count & Duratio")
        fig_user = plotly_stacked_side_by_side(df_filtered, "User", all_usernames, call_order,
                                               xaxis_title="User")
        st.plotly_chart(fig_user, use_container_width=True)

        # Prepare CET timezone columns for display
        cet = pytz.timezone("Europe/Berlin")

        df_display = df_filtered.copy()

        if "Connect Time (Unix)" in df_display.columns:
            df_display["Connect Time CET"] = pd.to_datetime(df_display["Connect Time (Unix)"], unit='s', errors='coerce')\
                .dt.tz_localize('UTC').dt.tz_convert(cet).dt.strftime('%Y-%m-%d %H:%M:%S')

        if "Disconnect Time (Unix)" in df_display.columns:
            df_display["Disconnect Time CET"] = pd.to_datetime(df_display["Disconnect Time (Unix)"], unit='s', errors='coerce')\
                .dt.tz_localize('UTC').dt.tz_convert(cet).dt.strftime('%Y-%m-%d %H:%M:%S')

        cols_to_show = [
            "User",
            "Extension",
            "Connect Time CET",
            "Disconnect Time CET",
            "Call Category",
            "Date",
            "Month",
            "Weekday",
            "Call Duration (s)",
            "Call Duration (min)"
        ]
        df_display = df_display[[col for col in cols_to_show if col in df_display.columns]]

        st.subheader("📋 Raw Call Records (Filtered)")
        st.dataframe(df_display)
