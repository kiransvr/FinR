from __future__ import annotations

import html
from io import BytesIO
from pathlib import Path

import pandas as pd
import streamlit as st

from src.collection_ops import append_feedback_record, generate_officer_kpis, generate_visit_plan, load_feedback_log
from src.api.auth import authenticate_user
from src.config import ProjectConfig, REQUIRED_COLUMNS
from src.pipeline import run as run_pipeline


st.set_page_config(
    page_title="Loan Default Risk",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

BASE_DIR = Path(__file__).resolve().parent
OUTPUTS_DIR = BASE_DIR / "outputs"
CONFIG = ProjectConfig(base_dir=BASE_DIR)

APP_CSS = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&family=Space+Grotesk:wght@600;700&display=swap');

    :root {
        --bg: #f4f7fb;
        --paper: #ffffff;
        --ink: #13233b;
        --muted: #60708a;
        --line: #dbe4f0;
        --brand: #0b5f80;
        --brand-soft: #e4f1f8;
        --brand-deep: #083f58;
        --accent: #b76828;
    }

    .stApp {
        font-family: 'Manrope', 'Segoe UI', sans-serif;
        background:
            radial-gradient(circle at 0% -5%, rgba(11, 95, 128, 0.11), transparent 30%),
            radial-gradient(circle at 100% 0%, rgba(183, 104, 40, 0.08), transparent 32%),
            linear-gradient(180deg, #f9fcff 0%, var(--bg) 100%);
        color: var(--ink);
    }

    .stApp p,
    .stApp label,
    .stApp div,
    .stApp span,
    .stApp li {
        font-family: 'Manrope', 'Segoe UI', sans-serif;
    }

    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1b2c46 0%, #203554 100%);
        border-right: 1px solid rgba(255, 255, 255, 0.08);
    }

    [data-testid="stSidebar"] * {
        color: #eef4ff;
    }

    [data-testid="stSidebar"] .stCaption {
        color: rgba(238, 244, 255, 0.72);
    }

    .hero {
        background:
            linear-gradient(125deg, rgba(8, 63, 88, 0.97), rgba(11, 95, 128, 0.94));
        border-radius: 18px;
        padding: 1.1rem 1.2rem;
        margin-bottom: 1rem;
        border: 1px solid rgba(255, 255, 255, 0.16);
        box-shadow: 0 12px 26px rgba(12, 29, 48, 0.2);
    }

    .hero h1,
    .hero p {
        color: #ffffff !important;
        margin: 0;
    }

    .hero h1 {
        font-family: 'Space Grotesk', 'Manrope', sans-serif;
        font-weight: 700;
        letter-spacing: 0.01em;
    }

    .hero p {
        margin-top: 0.45rem;
        font-size: 0.95rem;
        opacity: 0.9;
    }

    .panel,
    [data-testid="stMetric"],
    [data-testid="stDataFrame"],
    [data-testid="stExpander"] {
        background: var(--paper);
        border: 1px solid var(--line);
        border-radius: 14px;
        box-shadow: 0 8px 16px rgba(39, 57, 84, 0.06);
    }

    [data-testid="stMetric"] {
        padding: 0.65rem 0.75rem;
        border-left: 4px solid var(--brand);
        border-radius: 12px;
    }

    [data-testid="stMetricLabel"] {
        color: var(--muted);
        font-weight: 700;
        letter-spacing: 0.03em;
        text-transform: uppercase;
        font-size: 0.73rem;
    }

    [data-testid="stMetricValue"] {
        color: var(--ink);
        font-size: 1.85rem;
        font-weight: 800;
    }

    h1, h2, h3 {
        font-family: 'Space Grotesk', 'Manrope', sans-serif;
    }

    h3 {
        color: #253047;
        border-bottom: 2px solid #d9e8f3;
        padding-bottom: 0.22rem;
        margin-top: 0.25rem;
    }

    [data-testid="stTextInput"] input,
    [data-testid="stSelectbox"] div[data-baseweb="select"] > div,
    [data-testid="stNumberInput"] input,
    [data-testid="stDateInput"] input,
    [data-testid="stTextArea"] textarea {
        border: 1px solid #cfdceb !important;
        border-radius: 10px !important;
        background: #ffffff !important;
        color: #1f2f49 !important;
        font-size: 0.9rem !important;
    }

    [data-testid="stTextInput"] input:focus,
    [data-testid="stNumberInput"] input:focus,
    [data-testid="stDateInput"] input:focus,
    [data-testid="stTextArea"] textarea:focus {
        border-color: #0b5f80 !important;
        box-shadow: 0 0 0 1px #0b5f80 !important;
    }

    [data-testid="stSidebar"] button {
        background: linear-gradient(120deg, #236e8a, #144f6e) !important;
        color: #ffffff !important;
        border: 1px solid rgba(255, 255, 255, 0.2) !important;
        font-weight: 700 !important;
    }

    [data-testid="stSidebar"] button:hover {
        filter: brightness(1.08);
    }

    [data-testid="stFileUploaderDropzone"] {
        min-height: 88px !important;
        padding: 0.55rem 0.75rem !important;
        background: linear-gradient(140deg, rgba(196, 108, 47, 0.14), rgba(15, 92, 122, 0.18)) !important;
        border: 1px dashed rgba(255, 255, 255, 0.45) !important;
    }

    [data-testid="stFileUploaderDropzone"] [data-testid="stMarkdownContainer"] p,
    [data-testid="stFileUploaderDropzone"] small,
    [data-testid="stFileUploaderDropzone"] span,
    [data-testid="stFileUploaderDropzone"] label {
        color: #f7fbff !important;
        font-size: 0.82rem !important;
        margin: 0.1rem 0 !important;
    }

    [data-testid="stProgressBar"] > div > div {
        background: linear-gradient(90deg, #15719a, #be6f35) !important;
    }

    [data-baseweb="tab-list"] [data-baseweb="tab"] {
        font-weight: 700 !important;
        color: #33415c;
    }

    [data-testid="stDataFrame"] div[role="grid"] {
        font-size: 0.87rem;
    }

    [data-testid="stDataFrame"] [role="columnheader"] {
        background: #eaf2f8 !important;
        color: #1f3a55 !important;
        font-weight: 800 !important;
        border-bottom: 1px solid #d7e1ec !important;
    }

    [data-testid="stDataFrame"] [role="gridcell"] {
        border-bottom: 1px solid #edf2f7 !important;
    }

    [data-baseweb="tab-list"] {
        gap: 0.35rem !important;
        margin-bottom: 0.5rem;
    }

    [data-baseweb="tab-list"] [data-baseweb="tab"] {
        background: #edf3f9;
        border: 1px solid #d6e0eb;
        border-radius: 999px;
        padding: 0.36rem 0.95rem;
        font-size: 0.82rem;
    }

    [data-baseweb="tab-list"] [data-baseweb="tab"][aria-selected="true"] {
        background: linear-gradient(120deg, #236e8a, #124d6b);
        color: #ffffff !important;
        border-color: transparent;
    }

    [data-baseweb="tab-panel"] {
        background: #ffffff;
        border: 1px solid #d8e3ef;
        border-radius: 12px;
        padding: 0.8rem;
        margin-top: 0.4rem;
    }

    .table-card {
        background: #ffffff;
        border: 1px solid #d8e3ef;
        border-radius: 14px;
        padding: 0.75rem 0.9rem;
        margin-bottom: 0.4rem;
        box-shadow: 0 6px 14px rgba(21, 39, 63, 0.06);
    }

    .table-title {
        font-size: 1rem;
        font-weight: 800;
        color: #243654;
        margin: 0;
    }

    .table-subtitle {
        margin: 0.2rem 0 0;
        color: #65748b;
        font-size: 0.82rem;
    }

    .section-head {
        background: linear-gradient(180deg, #f8fbff, #eef6fc);
        border: 1px solid #d6e6f2;
        border-radius: 14px;
        padding: 0.65rem 0.85rem;
        margin: 0.6rem 0 0.55rem;
    }

    .section-head h3 {
        border: 0 !important;
        margin: 0;
        padding: 0;
        color: #1a3556;
    }

    .section-head p {
        margin: 0.2rem 0 0;
        color: #516685;
        font-size: 0.84rem;
    }

    [data-testid="baseButton-primary"],
    [data-testid="stFormSubmitButton"] button,
    [data-testid="stButton"] button {
        border-radius: 10px !important;
        font-weight: 700 !important;
    }

    @media (max-width: 900px) {
        [data-testid="stMetricValue"] {
            font-size: 1.5rem;
        }
    }
</style>
"""

st.markdown(APP_CSS, unsafe_allow_html=True)


def ensure_session_state() -> None:
    st.session_state.setdefault("authenticated", False)
    st.session_state.setdefault("username", "")
    st.session_state.setdefault("role", "")
    st.session_state.setdefault("last_upload_name", CONFIG.raw_data_path.name)


def load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def load_table_from_upload(uploaded_file) -> pd.DataFrame:
    if uploaded_file is None:
        return pd.DataFrame()

    suffix = Path(uploaded_file.name).suffix.lower()
    buffer = BytesIO(uploaded_file.getvalue())
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(buffer)
    if suffix == ".csv":
        return pd.read_csv(buffer)
    raise ValueError("Unsupported file format. Upload a .csv, .xlsx, or .xls file.")


def format_required_status(df: pd.DataFrame) -> tuple[list[str], list[str]]:
    if df.empty:
        return [], REQUIRED_COLUMNS
    missing = [column for column in REQUIRED_COLUMNS if column not in df.columns]
    present = [column for column in REQUIRED_COLUMNS if column in df.columns]
    return present, missing


def dataframe_download(df: pd.DataFrame, filename: str, label: str) -> None:
    if df.empty:
        st.button(label, disabled=True, use_container_width=True)
        return
    st.download_button(
        label=label,
        data=df.to_csv(index=False).encode("utf-8"),
        file_name=filename,
        mime="text/csv",
        use_container_width=True,
    )


def choose_columns(df: pd.DataFrame, preferred: list[str], fallback: int = 6) -> list[str]:
    selected = [column for column in preferred if column in df.columns]
    if selected:
        return selected
    return list(df.columns[:fallback])


def prepare_table(
    df: pd.DataFrame,
    preferred_cols: list[str],
    sort_candidates: list[str] | None = None,
    ascending: bool = False,
    limit: int = 100,
) -> pd.DataFrame:
    if df.empty:
        return df
    view = df.copy()
    if sort_candidates:
        view = sort_by_first_existing(view, sort_candidates, ascending=ascending)
    cols = choose_columns(view, preferred_cols, fallback=min(8, len(view.columns)))
    return view[cols].head(limit)


def render_professional_table(
    title: str,
    subtitle: str,
    df: pd.DataFrame,
    label_map: dict[str, str],
    percent_cols: list[str] | None = None,
    number_cols: list[str] | None = None,
) -> None:
    st.markdown(
        f'''
        <div class="table-card">
          <p class="table-title">{html.escape(title)}</p>
          <p class="table-subtitle">{html.escape(subtitle)}</p>
        </div>
        ''',
        unsafe_allow_html=True,
    )

    if df.empty:
        st.info("No data available for this table.")
        return

    percent_cols = percent_cols or []
    number_cols = number_cols or []
    column_config = {}
    for column in df.columns:
        label = label_map.get(column, column)
        if column in percent_cols:
            column_config[column] = st.column_config.NumberColumn(label=label, format="%.2f")
        elif column in number_cols:
            column_config[column] = st.column_config.NumberColumn(label=label, format="%.2f")
        else:
            column_config[column] = label

    st.dataframe(
        df,
        use_container_width=True,
        height=460,
        hide_index=True,
        column_config=column_config,
    )


def sort_by_first_existing(df: pd.DataFrame, candidates: list[str], ascending: bool = False) -> pd.DataFrame:
    for column in candidates:
        if column in df.columns:
            return df.sort_values(by=column, ascending=ascending)
    return df


def first_existing_column(df: pd.DataFrame, candidates: list[str]) -> str | None:
    for column in candidates:
        if column in df.columns:
            return column
    return None


def unique_values(df: pd.DataFrame, candidates: list[str]) -> list[str]:
    column = first_existing_column(df, candidates)
    if not column or df.empty:
        return []
    values = df[column].dropna().astype(str).str.strip()
    values = values[values != ""]
    return sorted(values.unique().tolist())


def apply_exact_filter(df: pd.DataFrame, candidates: list[str], selected_value: str) -> pd.DataFrame:
    if selected_value == "All" or df.empty:
        return df
    column = first_existing_column(df, candidates)
    if not column:
        return df
    selected = str(selected_value).strip().lower()
    normalized = df[column].astype(str).str.strip().str.lower()
    return df[normalized == selected]


def filter_by_query(df: pd.DataFrame, query: str) -> pd.DataFrame:
    text = query.strip().lower()
    if not text or df.empty:
        return df

    searchable = [
        column
        for column in [
            "account_id",
            "customer_id",
            "customer_name",
            "borrower_name",
            "officer_id",
            "AccountId",
            "AccountNo",
            "CustomerID",
            "AccountName",
            "OfficerId",
            "PSOCode",
        ]
        if column in df.columns
    ]
    if not searchable:
        return df

    mask = pd.Series(False, index=df.index)
    for column in searchable:
        mask = mask | df[column].astype(str).str.lower().str.contains(text, na=False)
    return df[mask]


def format_number(value) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if abs(number) >= 1_000_000:
        return f"{number:,.0f}"
    if abs(number) >= 1_000:
        return f"{number:,.0f}"
    if number.is_integer():
        return f"{int(number):,}"
    return f"{number:,.2f}"


def render_summary_cards(cards: list[dict[str, str | int]]) -> None:
    columns = st.columns(4)
    for column, card in zip(columns, cards, strict=False):
        with column:
            st.metric(str(card["label"]), str(card["value"]))
            st.caption(str(card["note"]))


def render_section_header(title: str, subtitle: str) -> None:
        st.markdown(
                f'''
                <div class="section-head">
                    <h3>{html.escape(title)}</h3>
                    <p>{html.escape(subtitle)}</p>
                </div>
                ''',
                unsafe_allow_html=True,
        )


def render_horizontal_ranking(title: str, subtitle: str, frame: pd.DataFrame, label_col: str, value_col: str, color: str = "") -> None:
    st.subheader(title)
    st.caption(subtitle)
    if frame.empty or label_col not in frame.columns or value_col not in frame.columns:
        st.info("No data available.")
        return

    plot_df = frame[[label_col, value_col]].copy().head(10)
    plot_df[value_col] = pd.to_numeric(plot_df[value_col], errors="coerce").fillna(0)
    max_value = float(plot_df[value_col].max()) if not plot_df.empty else 0
    for _, row in plot_df.iterrows():
        ratio = 0 if max_value == 0 else float(row[value_col]) / max_value
        left, right = st.columns([3, 7], vertical_alignment="center")
        with left:
            st.write(str(row[label_col]))
        with right:
            st.progress(ratio)
            st.caption(format_number(row[value_col]))


def render_donut(title: str, subtitle: str, counts: dict[str, int], colors: dict[str, str]) -> None:
    st.subheader(title)
    st.caption(subtitle)
    total = sum(counts.values())
    if total <= 0:
        st.info("No data available.")
        return

    left, right = st.columns([1.2, 1])
    with left:
        for label, value in counts.items():
            st.write(f"{label}: {value:,}")
            st.progress(0 if total == 0 else value / total)
    with right:
        for label, value in counts.items():
            percentage = 0 if total == 0 else (value / total) * 100
            st.write(f"{label} - {percentage:.1f}%")


def render_stacked_risk(title: str, subtitle: str, frame: pd.DataFrame, group_col: str, risk_col: str, total_limit: int = 5) -> None:
    st.subheader(title)
    st.caption(subtitle)
    if frame.empty or group_col not in frame.columns or risk_col not in frame.columns:
        st.info("No data available.")
        return

    work = frame[[group_col, risk_col]].copy()
    work[group_col] = work[group_col].astype(str).fillna("Unknown")
    work[risk_col] = work[risk_col].astype(str).fillna("Unknown")
    counts = work.groupby([group_col, risk_col]).size().unstack(fill_value=0)
    for band in ["High Risk", "Medium Risk", "Low Risk"]:
        if band not in counts.columns:
            counts[band] = 0
    counts["Total"] = counts.sum(axis=1)
    counts = counts.sort_values("Total", ascending=False).head(total_limit)

    total_max = float(counts["Total"].max()) if not counts.empty else 0
    for idx, row in counts.iterrows():
        ratio = 0 if total_max == 0 else float(row["Total"]) / total_max
        left, middle, right = st.columns([3, 7, 1], vertical_alignment="center")
        with left:
            st.write(str(idx))
        with middle:
            st.progress(ratio)
        with right:
            st.write(f"{int(row['Total']):,}")


def build_risk_distribution_table(frame: pd.DataFrame, risk_col: str) -> pd.DataFrame:
    if frame.empty or risk_col not in frame.columns:
        return pd.DataFrame()

    risk_series = frame[risk_col].fillna("Unknown").astype(str).str.strip().replace("", "Unknown")
    distribution = risk_series.value_counts().rename_axis("RiskBand").reset_index(name="Accounts")
    distribution["SharePct"] = (distribution["Accounts"] / max(1, int(distribution["Accounts"].sum()))) * 100
    order = {"High Risk": 0, "Medium Risk": 1, "Low Risk": 2}
    distribution["_order"] = distribution["RiskBand"].map(order).fillna(99)
    distribution = distribution.sort_values(["_order", "Accounts"], ascending=[True, False]).drop(columns=["_order"])
    return distribution


def build_group_risk_breakdown(frame: pd.DataFrame, group_col: str, risk_col: str, limit: int = 10) -> pd.DataFrame:
    if frame.empty or group_col not in frame.columns or risk_col not in frame.columns:
        return pd.DataFrame()

    work = frame[[group_col, risk_col]].copy()
    work[group_col] = work[group_col].fillna("Unknown").astype(str).str.strip().replace("", "Unknown")
    work[risk_col] = work[risk_col].fillna("Unknown").astype(str)

    breakdown = work.groupby([group_col, risk_col]).size().unstack(fill_value=0)
    for band in ["High Risk", "Medium Risk", "Low Risk"]:
        if band not in breakdown.columns:
            breakdown[band] = 0

    breakdown["TotalAccounts"] = breakdown[["High Risk", "Medium Risk", "Low Risk"]].sum(axis=1)
    breakdown["NonLowRisk"] = breakdown[["High Risk", "Medium Risk"]].sum(axis=1)
    breakdown["NonLowRiskPct"] = (breakdown["NonLowRisk"] / breakdown["TotalAccounts"].replace(0, pd.NA)) * 100
    breakdown = breakdown.fillna(0).sort_values(["NonLowRisk", "TotalAccounts"], ascending=False).reset_index()
    return breakdown.head(limit)


def login_screen() -> None:
    st.markdown(
        """
        <div class="hero">
          <h1>Sign in</h1>
          <p>Use your username and password to access the dashboard.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    left, right = st.columns([1.1, 0.9])
    with left:
        st.markdown('<div class="panel">', unsafe_allow_html=True)
        st.subheader("Login")
        with st.form("login_form", clear_on_submit=False):
            username = st.text_input("Username", placeholder="Enter username")
            password = st.text_input("Password", type="password", placeholder="Enter password")
            submitted = st.form_submit_button("Sign in", use_container_width=True)

        if submitted:
            user = authenticate_user(username.strip(), password)
            if user:
                st.session_state.authenticated = True
                st.session_state.username = user.username
                st.session_state.role = user.role
                st.rerun()
            else:
                st.error("Invalid username or password.")
        st.markdown("</div>", unsafe_allow_html=True)

    with right:
        st.markdown('<div class="panel">', unsafe_allow_html=True)
        st.subheader("Demo Credentials")
        st.write("- admin / changeme")
        st.write("- field_officer / officer123")
        st.markdown("</div>", unsafe_allow_html=True)


def render_app() -> None:
    current_source_name = st.session_state.get("last_upload_name") or CONFIG.raw_data_path.name

    with st.sidebar:
        st.subheader("Session")
        st.write(f"Signed in as: {st.session_state.username}")
        st.write(f"Role: {st.session_state.role}")
        if st.button("Log out", use_container_width=True):
            st.session_state.authenticated = False
            st.session_state.username = ""
            st.session_state.role = ""
            st.rerun()

        st.divider()

        uploaded_file = st.file_uploader("Upload loan data", type=["csv", "xlsx", "xls"])
        st.caption("If no file is uploaded, the current active file is used.")

        preview_df = load_table_from_upload(uploaded_file)
        if not preview_df.empty:
            st.caption(f"{uploaded_file.name} - {len(preview_df):,} rows")
            st.dataframe(preview_df.head(8), use_container_width=True, height=250)
            _, missing_cols = format_required_status(preview_df)
            if missing_cols:
                st.warning(f"Missing required columns: {', '.join(missing_cols)}")
            else:
                st.success("Required columns are present.")

        run_clicked = st.button("Run scoring", type="primary", use_container_width=True)

        if run_clicked:
            try:
                if uploaded_file is not None:
                    if preview_df.empty:
                        raise ValueError("Uploaded file could not be read.")
                    CONFIG.active_raw_data_path.parent.mkdir(parents=True, exist_ok=True)
                    preview_df.to_csv(CONFIG.active_raw_data_path, index=False)
                    st.session_state.last_upload_name = uploaded_file.name

                with st.spinner("Running pipeline..."):
                    run_pipeline(BASE_DIR)

                st.success("Pipeline completed successfully.")
                st.rerun()
            except Exception as exc:
                st.error(f"Pipeline failed: {exc}")

    scored = load_csv(OUTPUTS_DIR / "scored_accounts.csv")
    top_risky = load_csv(OUTPUTS_DIR / "top_risky_accounts.csv")
    visit_plan = load_csv(OUTPUTS_DIR / "daily_visit_plan.csv")
    officer_kpis = load_csv(OUTPUTS_DIR / "officer_kpis.csv")
    feedback_log = load_feedback_log(OUTPUTS_DIR / "field_feedback_log.csv")

    if scored.empty:
        st.info("No output yet. Upload data and click Run scoring to generate results.")
        return

    rule_col = first_existing_column(scored, ["RuleRiskCategory_y", "ModelRiskCategory"])
    if rule_col is None:
        scored = scored.copy()
        scored["RuleRiskCategory_y"] = "Low Risk"
        rule_col = "RuleRiskCategory_y"

    risk_frame = scored.copy()
    risk_frame["OutstandingPct"] = pd.to_numeric(risk_frame.get("PrincipalOS"), errors="coerce").fillna(0)
    if "DisbAmount" in risk_frame.columns:
        risk_frame["OutstandingPct"] = (
            pd.to_numeric(risk_frame["PrincipalOS"], errors="coerce").fillna(0)
            / pd.to_numeric(risk_frame["DisbAmount"], errors="coerce").replace(0, pd.NA)
        ) * 100
    risk_frame["OutstandingPct"] = risk_frame["OutstandingPct"].fillna(0)
    risk_frame["PrincipalOS"] = pd.to_numeric(risk_frame.get("PrincipalOS"), errors="coerce").fillna(0)
    risk_frame["SecurityValue"] = pd.to_numeric(risk_frame.get("SecurityValue"), errors="coerce").fillna(0)

    branch_col = first_existing_column(risk_frame, ["BrCode", "Branch"])
    sector_col = first_existing_column(risk_frame, ["Sector", "RMASector", "SectorCode"])
    account_label_col = first_existing_column(risk_frame, ["AccountNo", "AccountId", "AccountName", "AccountId"])

    filter_left, filter_mid, filter_right, filter_n = st.columns([1.2, 1.2, 1, 0.8])
    with filter_left:
        selected_branch = "All"
        if branch_col:
            branch_options = ["All"] + unique_values(risk_frame, [branch_col])
            selected_branch = st.selectbox("Branch Filter", options=branch_options, index=0)
    with filter_mid:
        selected_sector = "All"
        if sector_col:
            sector_options = ["All"] + unique_values(risk_frame, [sector_col])
            selected_sector = st.selectbox("Sector Filter", options=sector_options, index=0)
    with filter_right:
        risk_options = ["All", "High Risk", "Medium Risk", "Low Risk"]
        selected_risk = st.selectbox("Risk Filter", options=risk_options, index=0)
    with filter_n:
        top_n = st.slider("Top Rows", min_value=5, max_value=25, value=10, step=1)

    search_query = st.text_input(
        "Search Account / Customer / Officer",
        placeholder="Type account no, customer id, borrower, or officer code...",
    )

    synced_frame = risk_frame.copy()
    if branch_col:
        synced_frame = apply_exact_filter(synced_frame, [branch_col], selected_branch)
    if sector_col:
        synced_frame = apply_exact_filter(synced_frame, [sector_col], selected_sector)
    if selected_risk != "All":
        synced_frame = apply_exact_filter(synced_frame, [rule_col], selected_risk)
    synced_frame = filter_by_query(synced_frame, search_query)

    filtered_risk = synced_frame[rule_col].fillna("Unknown").astype(str).str.strip()
    low_count = int((filtered_risk == "Low Risk").sum())
    medium_count = int((filtered_risk == "Medium Risk").sum())
    high_count = int((filtered_risk == "High Risk").sum())
    non_standard_count = int((filtered_risk != "Low Risk").sum())

    st.caption(f"Synced view: {len(synced_frame):,} accounts")

    st.markdown(
        f'''
        <div class="hero">
          <h1>Risk Dashboard</h1>
          <p>File: {html.escape(current_source_name)} | Rule-Based Mode</p>
        </div>
        ''',
        unsafe_allow_html=True,
    )

    render_summary_cards(
        [
            {"label": "Non-Standard Accounts", "value": non_standard_count, "note": "Filtered scope: outside low-risk band."},
            {"label": "High Risk Accounts", "value": high_count, "note": "Filtered scope: flagged as high risk."},
            {"label": "Medium Risk Accounts", "value": medium_count, "note": "Filtered scope: in caution band."},
            {"label": "Low Risk Accounts", "value": low_count, "note": "Filtered scope: currently low risk."},
        ]
    )

    top_amount = synced_frame.sort_values(by="PrincipalOS", ascending=False).head(top_n)
    low_outstanding = synced_frame.sort_values(by="OutstandingPct", ascending=True).head(top_n)
    low_security = synced_frame.sort_values(by="SecurityValue", ascending=True).head(top_n)
    risk_distribution_table = build_risk_distribution_table(synced_frame, rule_col)
    branch_summary = build_group_risk_breakdown(synced_frame, branch_col, rule_col, limit=top_n) if branch_col else pd.DataFrame()
    sector_summary = build_group_risk_breakdown(synced_frame, sector_col, rule_col, limit=top_n) if sector_col else pd.DataFrame()

    render_section_header("Risk Intelligence Tables", "All six views below are synchronized with the filters above.")

    insights_tabs = st.tabs(
        [
            "Top Outstanding",
            "Low % Outstanding",
            "Zero/Low Security",
            "Overall Distribution",
            "Branch-wise Risk",
            "Sector-wise Risk",
        ]
    )

    with insights_tabs[0]:
        top_amount_view = prepare_table(
            top_amount,
            [account_label_col or "AccountNo", "BrCode", "Sector", "PrincipalOS", "OutstandingPct", "SecurityValue", rule_col],
            sort_candidates=["PrincipalOS"],
            ascending=False,
            limit=top_n,
        )
        render_professional_table(
            "Top Outstanding Amount",
            "Highest principal outstanding balances in the current filtered scope.",
            top_amount_view,
            {
                "BrCode": "Branch",
                "Sector": "Sector",
                "PrincipalOS": "Outstanding Amount",
                "OutstandingPct": "Outstanding %",
                "SecurityValue": "Security Value",
                rule_col: "Risk",
            },
            percent_cols=["OutstandingPct"],
            number_cols=["PrincipalOS", "SecurityValue"],
        )

    with insights_tabs[1]:
        low_outstanding_view = prepare_table(
            low_outstanding,
            [account_label_col or "AccountNo", "BrCode", "Sector", "OutstandingPct", "PrincipalOS", "DisbAmount", rule_col],
            sort_candidates=["OutstandingPct"],
            ascending=True,
            limit=top_n,
        )
        render_professional_table(
            "Top Low % Outstanding",
            "Accounts with the lowest outstanding-to-disbursed percentage.",
            low_outstanding_view,
            {
                "BrCode": "Branch",
                "Sector": "Sector",
                "OutstandingPct": "Outstanding %",
                "PrincipalOS": "Outstanding Amount",
                "DisbAmount": "Disbursed Amount",
                rule_col: "Risk",
            },
            percent_cols=["OutstandingPct"],
            number_cols=["PrincipalOS", "DisbAmount"],
        )

    with insights_tabs[2]:
        low_security_view = prepare_table(
            low_security,
            [account_label_col or "AccountNo", "BrCode", "Sector", "SecurityValue", "PrincipalOS", "OutstandingPct", rule_col],
            sort_candidates=["SecurityValue"],
            ascending=True,
            limit=top_n,
        )
        render_professional_table(
            "Top Zero/Low Security",
            "Accounts with least collateral cover in the selected scope.",
            low_security_view,
            {
                "BrCode": "Branch",
                "Sector": "Sector",
                "SecurityValue": "Security Value",
                "PrincipalOS": "Outstanding Amount",
                "OutstandingPct": "Outstanding %",
                rule_col: "Risk",
            },
            percent_cols=["OutstandingPct"],
            number_cols=["SecurityValue", "PrincipalOS"],
        )

    with insights_tabs[3]:
        render_professional_table(
            "Overall Risk Distribution",
            "Risk mix and share percentage in the current filtered portfolio.",
            risk_distribution_table,
            {
                "RiskBand": "Risk Band",
                "Accounts": "Accounts",
                "SharePct": "Share %",
            },
            percent_cols=["SharePct"],
            number_cols=["Accounts"],
        )

    with insights_tabs[4]:
        render_professional_table(
            "Branch-wise Risk",
            "Branch level risk profile with high/medium/low split and non-low share.",
            branch_summary,
            {
                branch_col if branch_col else "Branch": "Branch",
                "High Risk": "High Risk",
                "Medium Risk": "Medium Risk",
                "Low Risk": "Low Risk",
                "NonLowRisk": "Non Low Risk",
                "NonLowRiskPct": "Non Low Risk %",
                "TotalAccounts": "Total Accounts",
            },
            percent_cols=["NonLowRiskPct"],
            number_cols=["High Risk", "Medium Risk", "Low Risk", "NonLowRisk", "TotalAccounts"],
        )

    with insights_tabs[5]:
        render_professional_table(
            "Sector-wise Risk",
            "Sector level risk profile with high/medium/low split and non-low share.",
            sector_summary,
            {
                sector_col if sector_col else "Sector": "Sector",
                "High Risk": "High Risk",
                "Medium Risk": "Medium Risk",
                "Low Risk": "Low Risk",
                "NonLowRisk": "Non Low Risk",
                "NonLowRiskPct": "Non Low Risk %",
                "TotalAccounts": "Total Accounts",
            },
            percent_cols=["NonLowRiskPct"],
            number_cols=["High Risk", "Medium Risk", "Low Risk", "NonLowRisk", "TotalAccounts"],
        )

    with st.expander("Detailed Data Tables", expanded=True):
        tabs = st.tabs(["Top Risky (Full)", "Visit Plan (Full)", "Officer KPIs (Full)", "Scored Accounts (Full)", "Field Feedback"])

        with tabs[0]:
            if top_risky.empty:
                st.info("No top risky output available.")
            else:
                top_risky_table = prepare_table(
                    top_risky,
                    [
                        "AccountNo",
                        "AccountName",
                        "BrCode",
                        "PSOCode",
                        "ProductDescription",
                        "PrincipalOS",
                        "SecurityValue",
                        "PredDefaultProbability",
                        "RuleRiskCategory_y",
                        "ModelRiskCategory",
                    ],
                    sort_candidates=["PredDefaultProbability", "PrincipalOS"],
                    ascending=False,
                    limit=100,
                )
                render_professional_table(
                    "Top Risky Accounts",
                    "Priority recovery list with risk score, collateral context, and exposure.",
                    top_risky_table,
                    {
                        "AccountNo": "Account No",
                        "AccountName": "Account Name",
                        "BrCode": "Branch",
                        "PSOCode": "Officer",
                        "ProductDescription": "Product",
                        "PrincipalOS": "Principal Outstanding",
                        "SecurityValue": "Security Value",
                        "PredDefaultProbability": "Default Probability",
                        "RuleRiskCategory_y": "Rule Risk",
                        "ModelRiskCategory": "Model Risk",
                    },
                    percent_cols=["PredDefaultProbability"],
                    number_cols=["PrincipalOS", "SecurityValue"],
                )

        with tabs[1]:
            if visit_plan.empty:
                st.info("No visit plan output available.")
            else:
                visit_plan_table = prepare_table(
                    visit_plan,
                    [
                        "DailyVisitRank",
                        "OfficerId",
                        "AccountId",
                        "Branch",
                        "RiskBand",
                        "DaysOverdue",
                        "ContactChannel",
                        "VisitAction",
                        "SuggestedNegotiation",
                        "EscalationFlag",
                    ],
                    sort_candidates=["DailyVisitRank", "DaysOverdue"],
                    ascending=True,
                    limit=100,
                )
                render_professional_table(
                    "Field Visit Plan",
                    "Action queue ordered by rank, overdue pressure, and escalation need.",
                    visit_plan_table,
                    {
                        "DailyVisitRank": "Visit Rank",
                        "OfficerId": "Officer",
                        "AccountId": "Account",
                        "Branch": "Branch",
                        "RiskBand": "Risk Band",
                        "DaysOverdue": "Days Overdue",
                        "ContactChannel": "Channel",
                        "VisitAction": "Visit Action",
                        "SuggestedNegotiation": "Negotiation Hint",
                        "EscalationFlag": "Escalation",
                    },
                    number_cols=["DailyVisitRank", "DaysOverdue"],
                )

        with tabs[2]:
            if officer_kpis.empty:
                st.info("No officer KPI output available.")
            else:
                officer_kpi_table = prepare_table(
                    officer_kpis,
                    [
                        "OfficerId",
                        "AssignedCases",
                        "HighRiskCases",
                        "AverageDaysOverdue",
                        "RescheduleCandidateRate",
                        "EscalationCount",
                        "PctCurrent",
                        "CoachingTip",
                    ],
                    sort_candidates=["HighRiskCases", "AssignedCases"],
                    ascending=False,
                    limit=100,
                )
                render_professional_table(
                    "Officer Performance",
                    "Portfolio workload, risk pressure, and coaching cues by officer.",
                    officer_kpi_table,
                    {
                        "OfficerId": "Officer",
                        "AssignedCases": "Assigned Cases",
                        "HighRiskCases": "High-Risk Cases",
                        "AverageDaysOverdue": "Avg Days Overdue",
                        "RescheduleCandidateRate": "Reschedule Candidate Rate",
                        "EscalationCount": "Escalations",
                        "PctCurrent": "Current %",
                        "CoachingTip": "Coaching Tip",
                    },
                    percent_cols=["RescheduleCandidateRate", "PctCurrent"],
                    number_cols=["AssignedCases", "HighRiskCases", "AverageDaysOverdue", "EscalationCount"],
                )

        with tabs[3]:
            scored_table = prepare_table(
                scored,
                [
                    "AccountNo",
                    "AccountName",
                    "BrCode",
                    "ProductDescription",
                    "Sector",
                    "PrincipalOS",
                    "SecurityValue",
                    "PredDefaultProbability",
                    "RuleRiskCategory_y",
                    "ModelRiskCategory",
                ],
                sort_candidates=["PredDefaultProbability", "PrincipalOS"],
                ascending=False,
                limit=100,
            )
            render_professional_table(
                "Scored Portfolio",
                "Comprehensive scored output with model prediction and rule classification.",
                scored_table,
                {
                    "AccountNo": "Account No",
                    "AccountName": "Account Name",
                    "BrCode": "Branch",
                    "ProductDescription": "Product",
                    "Sector": "Sector",
                    "PrincipalOS": "Principal Outstanding",
                    "SecurityValue": "Security Value",
                    "PredDefaultProbability": "Default Probability",
                    "RuleRiskCategory_y": "Rule Risk",
                    "ModelRiskCategory": "Model Risk",
                },
                percent_cols=["PredDefaultProbability"],
                number_cols=["PrincipalOS", "SecurityValue"],
            )

        with tabs[4]:
            st.markdown('<div class="table-card">', unsafe_allow_html=True)
            st.markdown("#### Submit Field Feedback")

            account_options = []
            if not visit_plan.empty and "AccountId" in visit_plan.columns:
                account_options = sorted(visit_plan["AccountId"].astype(str).dropna().unique().tolist())
            if not account_options:
                account_col = first_existing_column(scored, ["AccountNo", "AccountId", "AccountName"])
                if account_col:
                    account_options = sorted(scored[account_col].astype(str).dropna().unique().tolist())

            officer_options = []
            if not visit_plan.empty and "OfficerId" in visit_plan.columns:
                officer_options = sorted(visit_plan["OfficerId"].astype(str).dropna().unique().tolist())
            if not officer_options:
                officer_options = [st.session_state.username or "OFFICER_1"]

            with st.form("feedback_submit_form", clear_on_submit=True):
                c1, c2, c3 = st.columns(3)
                with c1:
                    as_of_date = st.date_input("As Of Date")
                    officer_id = st.selectbox("Officer", options=officer_options)
                with c2:
                    account_id = st.selectbox("Account", options=account_options) if account_options else st.text_input("Account")
                    visit_status = st.selectbox("Visit Status", ["Completed", "Attempted", "Deferred"])
                with c3:
                    outcome = st.selectbox(
                        "Outcome",
                        ["Contacted", "Promise to Pay", "Partial Payment", "Paid", "No Contact", "Dispute", "Resolved"],
                    )
                    promise_status = st.selectbox("Promise Status", ["None", "Kept", "Broken"])

                c4, c5, c6 = st.columns(3)
                with c4:
                    promise_date = st.date_input("Promise To Pay Date")
                    promised_amount = st.number_input("Promised Amount", min_value=0.0, step=100.0)
                with c5:
                    hardship_flag = st.selectbox("Hardship", ["No", "Yes"])
                    dispute_flag = st.selectbox("Dispute", ["No", "Yes"])
                with c6:
                    escalation_flag = st.selectbox("Supervisor Escalation", ["No", "Yes"])
                    next_action = st.selectbox(
                        "Next Action",
                        ["Follow-up Call", "Field Visit", "Escalate", "Close Case"],
                    )

                field_notes = st.text_area("Field Notes", height=90)
                submit_feedback = st.form_submit_button("Save Feedback", use_container_width=True)

            if submit_feedback:
                try:
                    saved_df, _ = append_feedback_record(
                        OUTPUTS_DIR / "field_feedback_log.csv",
                        {
                            "AsOfDate": as_of_date.strftime("%Y-%m-%d"),
                            "OfficerId": officer_id,
                            "AccountId": account_id,
                            "VisitStatus": visit_status,
                            "Outcome": outcome,
                            "PromiseStatus": promise_status,
                            "PromiseToPayDate": promise_date.strftime("%Y-%m-%d"),
                            "PromisedAmount": promised_amount,
                            "ClientHardshipFlag": hardship_flag,
                            "DisputeFlag": dispute_flag,
                            "SupervisorEscalation": escalation_flag,
                            "NextAction": next_action,
                            "FieldNotes": field_notes,
                            "RecordedBy": st.session_state.username,
                        },
                    )
                    st.success(f"Feedback saved. Total records: {len(saved_df):,}")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Failed to save feedback: {exc}")

            refresh_clicked = st.button("Refresh Visit Plan From Feedback", use_container_width=True)
            if refresh_clicked:
                try:
                    latest_feedback = load_feedback_log(OUTPUTS_DIR / "field_feedback_log.csv")
                    refreshed_visit = generate_visit_plan(
                        scored,
                        OUTPUTS_DIR / "daily_visit_plan.csv",
                        feedback_log=latest_feedback,
                    )
                    refreshed_kpi = generate_officer_kpis(refreshed_visit, OUTPUTS_DIR / "officer_kpis.csv")
                    st.success(
                        f"Plan refreshed from feedback. Visit rows: {len(refreshed_visit):,} | KPI rows: {len(refreshed_kpi):,}"
                    )
                    st.rerun()
                except Exception as exc:
                    st.error(f"Failed to refresh plan: {exc}")

            st.markdown("#### Feedback Log")
            if feedback_log.empty:
                st.info("No feedback submitted yet.")
            else:
                feedback_view = prepare_table(
                    feedback_log.sort_values("RecordedAt", ascending=False),
                    [
                        "RecordedAt",
                        "AsOfDate",
                        "OfficerId",
                        "AccountId",
                        "Outcome",
                        "PromiseStatus",
                        "PromisedAmount",
                        "SupervisorEscalation",
                        "NextAction",
                        "FieldNotes",
                    ],
                    sort_candidates=["RecordedAt"],
                    ascending=False,
                    limit=150,
                )
                render_professional_table(
                    "Field Feedback Log",
                    "Latest officer updates used to refresh future visit priorities.",
                    feedback_view,
                    {
                        "RecordedAt": "Recorded At",
                        "AsOfDate": "As Of",
                        "OfficerId": "Officer",
                        "AccountId": "Account",
                        "Outcome": "Outcome",
                        "PromiseStatus": "Promise Status",
                        "PromisedAmount": "Promised Amount",
                        "SupervisorEscalation": "Escalation",
                        "NextAction": "Next Action",
                        "FieldNotes": "Notes",
                    },
                    number_cols=["PromisedAmount"],
                )

            st.markdown("</div>", unsafe_allow_html=True)

ensure_session_state()
if not st.session_state.authenticated:
    login_screen()
else:
    render_app()
