"""InsightAI 1.0: interface only; trusted calculations live in core/."""

from pathlib import Path
import hashlib
import json
import os
import pandas as pd
import streamlit as st
from pydantic import ValidationError
from core.data_loader import load_data, sheet_names, DataError
from core.data_analysis import (
    numeric_columns,
    category_columns,
    date_columns,
    date_series,
    profile,
    kpis,
    facts,
    aggregate,
    filter_data,
    monthly,
)
from core.data_cleaning import OPERATIONS, clean, replay
from core.chart_builder import build_chart, CHARTS
from core.chat_engine import Plan, make_plan, infer_plan, execute_plan
from core.ai_service import AIService, DEFAULT_MODEL, MAX_CALLS
from core.report_generator import csv_bytes, excel_bytes, pdf_bytes

st.set_page_config(
    page_title="InsightAI · Data to decisions",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown(
    """<style>
.block-container {max-width:1400px;padding-top:2rem;padding-bottom:3rem}
[data-testid="stMetric"] {border:1px solid #94a3b844;border-radius:14px;padding:16px}
[data-testid="stMetricLabel"] {font-size:.82rem}
[data-testid="stSidebar"] {border-right:1px solid #94a3b833}
.hero {background:linear-gradient(115deg,#102f3b,#14545b);padding:32px;border-radius:20px;color:#fff;margin-bottom:22px}
.hero h1 {color:#fff;font-size:2.5rem;margin:0 0 8px;letter-spacing:-.06rem}
.hero p {color:#d2ecea;max-width:750px;margin-bottom:4px;font-size:1.05rem}
.eyebrow {color:#5eead4;font-size:.75rem;letter-spacing:.18rem;font-weight:700;margin-bottom:12px}
@media(max-width:640px){.block-container{padding:1rem}.hero{padding:22px}.hero h1{font-size:1.8rem}}
</style>""",
    unsafe_allow_html=True,
)
ROOT = Path(__file__).parent
ss = st.session_state
for key, value in {
    "actions": [],
    "history": [],
    "messages": [],
    "api_budget": {"calls": 0, "last_call": 0},
    "ai_enabled": False,
    "model": os.getenv("OPENAI_MODEL", DEFAULT_MODEL),
    "filter_epoch": 0,
    "data_revision": 0,
}.items():
    if key not in ss:
        ss[key] = value


def select(label, options, key, default=None, **kwargs):
    if not options:
        return None
    if key in ss and ss[key] not in options:
        del ss[key]
    index = options.index(default) if default in options else 0
    return st.selectbox(label, options, index=index, key=key, **kwargs)


def format_value(value, unit=""):
    return "N/A" if value is None or pd.isna(value) else f"{unit}{value:,.2f}"


def invalidate():
    for key in (
        "ai_result",
        "generated_exports",
        "last_chart",
        "pending_plan",
        "previous_plan",
        "unresolved_question",
    ):
        ss.pop(key, None)
    ss.messages = []


def change_data(actions):
    ss.current, ss.history = replay(ss.original, actions)
    ss.actions = actions
    ss.data_revision += 1
    ss.filter_epoch += 1
    invalidate()
    st.rerun()


def credentials():
    key = os.getenv("OPENAI_API_KEY", "")
    try:
        key = st.secrets.get("OPENAI_API_KEY", key)
    except (FileNotFoundError, KeyError):
        pass
    return key


def service():
    return AIService(credentials(), ss.model, ss.ai_enabled, ss.api_budget)


with st.sidebar:
    st.markdown("## ◈ InsightAI")
    st.caption("YOUR DATA. CLEARER DECISIONS.")
    page = st.radio(
        "Workspace",
        [
            "Home",
            "Data Overview",
            "Data Cleaning",
            "Dashboard",
            "AI Insights",
            "Chat With Your Data",
            "Reports & Export",
            "Settings / About",
        ],
        key="page",
    )
    st.divider()
    upload = st.file_uploader(
        "Upload CSV or Excel",
        type=["csv", "xlsx"],
        help="Up to 15 MB, 100,000 rows, 100 columns, 2 million cells.",
    )
    source_choice = st.selectbox(
        "Sample dataset",
        ["Sales · original", "Employees · example", "Survey · text only", "None"],
    )
    encoding, delimiter = "utf-8-sig", ","
    if upload and upload.name.lower().endswith(".csv"):
        with st.expander("CSV options"):
            encoding = st.selectbox("Encoding", ["utf-8-sig", "cp1252", "latin-1"])
            delimiter = st.selectbox(
                "Delimiter",
                [",", ";", "\t", "|"],
                format_func=lambda x: "Tab" if x == "\t" else x,
            )

if upload:
    data, name = upload.getvalue(), upload.name
elif source_choice != "None":
    filename = {
        "Sales · original": "sales.csv",
        "Employees · example": "employees.csv",
        "Survey · text only": "survey.csv",
    }[source_choice]
    data, name = (ROOT / "sample_data" / filename).read_bytes(), filename
else:
    st.title("Start with your data")
    st.info("Upload a CSV or Excel workbook, or choose a sample in the sidebar.")
    st.stop()
sheet = None
try:
    if name.lower().endswith(".xlsx"):
        file_hash = hashlib.sha256(data).hexdigest()
        if ss.get("xlsx_hash") != file_hash:
            ss.xlsx_sheets = sheet_names(data)
            ss.xlsx_hash = file_hash
        with st.sidebar:
            sheet = select("Excel sheet", ss.xlsx_sheets, "sheet")
    dataset_id = hashlib.sha256(
        data + f"{name}:{sheet}:{encoding}:{delimiter}".encode()
    ).hexdigest()
    if ss.get("dataset_id") != dataset_id:
        original = load_data(data, name, sheet, encoding, delimiter)
        ss.original, ss.current = original, original.copy()
        ss.dataset_id, ss.dataset_name = dataset_id, name
        ss.actions, ss.history = [], []
        ss.data_revision += 1
        ss.filter_epoch += 1
        # Consent is dataset-scoped; API budget is session-scoped and never resets here.
        ss.ai_enabled = False
        invalidate()
    df = ss.current
except DataError as exc:
    st.error(str(exc))
    st.stop()

nums, cats, dates = numeric_columns(df), category_columns(df), date_columns(df)
with st.sidebar:
    st.divider()
    st.markdown("#### Analysis controls")
    metric = select(
        "Metric",
        [None] + nums,
        "metric",
        "Revenue_NGN" if "Revenue_NGN" in nums else (nums[0] if nums else None),
        format_func=lambda x: x or "Record counts only",
    )
    group = select(
        "Breakdown",
        [None] + cats,
        "group",
        "Product" if "Product" in cats else (cats[0] if cats else None),
        format_func=lambda x: x or "No category breakdown",
    )
    unit = st.text_input(
        "Currency / unit prefix",
        value="NGN " if metric == "Revenue_NGN" else "",
        key=f"unit_{metric}",
        max_chars=12,
    )
    st.caption(
        "Choose metrics carefully: totals of IDs, ages or rates may be inappropriate."
    )
    with st.expander("Sales field mapping (optional)"):
        revenue = select(
            "Revenue column",
            [None] + nums,
            "map_revenue",
            "Revenue_NGN",
            format_func=lambda x: x or "Not a sales dataset",
        )
        product = select(
            "Product column",
            [None] + cats,
            "map_product",
            "Product",
            format_func=lambda x: x or "Not mapped",
        )
        region = select(
            "Region column",
            [None] + cats,
            "map_region",
            "Region",
            format_func=lambda x: x or "Not mapped",
        )
        units = select(
            "Units column",
            [None] + nums,
            "map_units",
            "Units_Sold",
            format_func=lambda x: x or "Not mapped",
        )
    st.markdown("#### Shared filters")
    if st.button("Reset filters", width="stretch"):
        ss.filter_epoch += 1
        st.rerun()
    prefix = f"f{ss.filter_epoch}_"
    filter_cols = st.multiselect("Filter columns", cats, key=prefix + "columns")
    selections = {}
    for c in filter_cols:
        values = sorted(df[c].dropna().astype(str).unique().tolist())
        if len(values) > 500:
            st.caption(
                f"{c}: over 500 categories. Enter exact category values below, one per line."
            )
            raw = st.text_area(f"{c} values", key=prefix + c)
            if raw.strip():
                selections[c] = raw.splitlines()
        else:
            options = values + ([None] if df[c].isna().any() else [])
            selections[c] = st.multiselect(
                c,
                options,
                default=options,
                key=prefix + c,
                format_func=lambda v: "(Missing)" if v is None else v,
            )
    date_filter = select(
        "Date range column",
        [None] + dates,
        prefix + "date",
        format_func=lambda x: x or "No date filter",
    )
    start, end, include_missing_dates = None, None, False
    if date_filter and len(df):
        ds = date_series(df[date_filter]).dropna()
        if not ds.empty:
            selected_range = st.date_input(
                "Date range",
                value=(ds.min().date(), ds.max().date()),
                key=prefix + "range",
            )
            if len(selected_range) == 2:
                start, end = selected_range
            else:
                st.info("Select both a start and an end date.")
                st.stop()
            include_missing_dates = st.checkbox(
                "Include undated records", key=prefix + "undated"
            )
    st.caption(
        "Filters apply to dashboard, insights, chat and reports. Cleaning always uses the full dataset."
    )

try:
    filtered = filter_data(
        df, selections, date_filter, start, end, include_missing_dates
    )
except DataError as exc:
    st.error(str(exc))
    st.stop()
context = {
    "Dataset": name,
    "Sheet": sheet or "N/A",
    "Dataset fingerprint": dataset_id[:12],
    "Original rows": len(ss.original),
    "Cleaned rows": len(df),
    "Selected rows": len(filtered),
    "Metric": metric or "Record counts",
    "Breakdown": group or "None",
    "Unit prefix": unit or "Unspecified",
    "Category filters": json.dumps(selections, ensure_ascii=False),
    "Date filter": (
        f"{date_filter}: {start} to {end}; include undated={include_missing_dates}"
        if date_filter
        else "None"
    ),
    "Cleaning revision": ss.data_revision,
}
scope_id = hashlib.sha256(
    json.dumps(context, default=str, sort_keys=True).encode()
).hexdigest()
if ss.get("scope_id") != scope_id:
    invalidate()
    ss.scope_id = scope_id
st.caption(
    f"{name}  /  {len(filtered):,} selected records  /  {len(df.columns)} columns  /  {len(ss.actions)} cleaning steps"
)

if page == "Home":
    st.markdown(
        """<div class="hero"><div class="eyebrow">MEET YOUR DATA, PROPERLY.</div>
    <h1>From rows to a clearer picture.</h1><p>Explore, clean and understand your data in one workspace.
    Every number calculated. Every change in your control.</p></div>""",
        unsafe_allow_html=True,
    )
    a, b, c, d = st.columns(4)
    a.metric("Records loaded", f"{len(df):,}")
    b.metric("Fields to explore", len(df.columns))
    c.metric("Missing cells", f"{int(df.isna().sum().sum()):,}")
    d.metric("Duplicate rows", f"{int(df.duplicated().sum()):,}")
    st.markdown("### A practical path to insight")
    for col, title, text in zip(
        st.columns(3),
        ["01 · Understand", "02 · Refine", "03 · Explain"],
        [
            "Check the overview: types, missing values and unusual observations.",
            "Preview a cleaning change, apply it, and undo it whenever needed.",
            "Filter your dashboard, ask a question and export the evidence.",
        ],
    ):
        with col:
            with st.container(border=True):
                st.subheader(title)
                st.write(text)
    st.markdown("### Your working data")
    st.dataframe(df.head(12), hide_index=True, width="stretch")
    st.info(
        "Start with Data Overview in the sidebar. External AI is optional and disabled until you enable it for this dataset."
    )

elif page == "Data Overview":
    st.title("Know what you’re working with")
    st.write(
        "This profile describes the full working dataset before dashboard filters."
    )
    st.dataframe(profile(df), hide_index=True, width="stretch")
    st.caption(
        "IQR flags are candidates for review, not automatic errors. Mixed-type hints do not change your data."
    )
    tab1, tab2, tab3 = st.tabs(
        ["Preview", "Numeric statistics", "Category frequencies"]
    )
    with tab1:
        preview_rows = st.slider("Preview rows", 5, 500, 25)
        st.dataframe(df.head(preview_rows), hide_index=True, width="stretch")
    with tab2:
        if nums:
            st.dataframe(df[nums].describe().T, width="stretch")
            st.caption(
                "Mean = recorded total / recorded count. Median = middle value. Std = sample standard deviation. Missing values are excluded."
            )
        else:
            st.info(
                "No numeric columns. You can still explore categories and missing values."
            )
    with tab3:
        cat = select("Category to inspect", cats, "overview_cat")
        if cat:
            st.dataframe(
                aggregate(df, cat, None, "count")
                .sort_values("Value", ascending=False)
                .head(100),
                hide_index=True,
            )
            st.caption("Up to 100 most frequent categories. Value means record count.")

elif page == "Data Cleaning":
    st.title("Clean with confidence")
    st.write(
        "Changes affect a working copy. Your original file stays unchanged. Filters do not remove records here."
    )
    c1, c2, c3 = st.columns(3)
    if c1.button("Undo last step", disabled=not ss.actions, width="stretch"):
        change_data(ss.actions[:-1])
    if c2.button("Reset to original", disabled=not ss.actions, width="stretch"):
        change_data([])
    c3.metric("Steps applied", len(ss.actions))
    operation = st.selectbox("Cleaning action", OPERATIONS)
    columns = st.multiselect(
        "Columns to change",
        list(df.columns),
        disabled=operation in ("Remove duplicate rows", "Standardize column names"),
    )
    action = {"operation": operation, "columns": columns}
    if operation == "Convert to number":
        action["strip_commas"] = st.checkbox(
            "Commas are thousands separators", value=False
        )
        action["currency_symbol"] = st.text_input(
            "Currency symbol to remove (optional)", max_chars=10
        )
    if operation == "Convert to date":
        action["date_format"] = st.selectbox(
            "Source date format",
            ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%b-%Y", "%Y-%m-%d %H:%M:%S"],
        )
        st.caption(
            "For example, 15/11/2026 uses %d/%m/%Y. Dates are stored as datetime values, displayed in ISO form."
        )
    if operation.startswith("Convert"):
        action["allow_invalid"] = st.checkbox(
            "I allow values that fail conversion to become missing"
        )
    if operation.startswith("Fill numeric"):
        st.warning(
            "Imputation changes the analysis. Confirm that replacing these values with a mean/median makes sense, especially for money. Missing amounts are never automatically filled with zero."
        )
    try:
        preview, changes = clean(df, action)
        st.markdown("#### Preview this change")
        st.json(changes, expanded=True)
        left, right = st.columns(2)
        left.write("Before · first 10 rows")
        left.dataframe(df.head(10), hide_index=True)
        right.write("After · first 10 rows")
        right.dataframe(preview.head(10), hide_index=True)
        if st.button(
            "Apply this change", type="primary", disabled=len(ss.actions) >= 50
        ):
            change_data(ss.actions + [action])
        if len(ss.actions) >= 50:
            st.info(
                "Session limit: 50 cleaning steps. Undo a step or reset to continue."
            )
    except DataError as exc:
        st.info(str(exc))
    if ss.history:
        st.markdown("#### Applied cleaning history")
        st.dataframe(pd.DataFrame(ss.history), hide_index=True, width="stretch")
    st.download_button(
        "Download full cleaned CSV", csv_bytes(df), "insightai_cleaned.csv", "text/csv"
    )

elif page == "Dashboard":
    st.title("The story in your numbers")
    st.write(
        "Use the shared sidebar controls to keep cards, charts and exported findings in the same scope."
    )
    values = kpis(filtered, metric)
    a, b, c, d = st.columns(4)
    a.metric("Selected records", values["records"])
    if metric:
        b.metric(f"Recorded total · {metric}", format_value(values["total"], unit))
        c.metric("Recorded mean", format_value(values["average"], unit))
        d.metric("Missing metric values", values["missing"])
        st.caption(
            f'Based on {values["recorded"]:,} recorded {metric} values. A row is a record; it is only a transaction if your dataset defines it that way.'
        )
    else:
        b.metric("Missing cells", values["missing_cells"])
        c.metric("Duplicate rows", values["duplicate_rows"])
        d.metric("Fields", len(filtered.columns))
    if revenue and metric == revenue:
        with st.expander("Mapped sales summary", expanded=True):
            s1, s2, s3 = st.columns(3)
            for col, field, label in (
                (s1, product, "Leading product"),
                (s2, region, "Leading region"),
            ):
                if field and len(filtered):
                    breakdown = (
                        aggregate(filtered, field, revenue)
                        .dropna(subset=["Value"])
                        .sort_values("Value", ascending=False)
                    )
                    if not breakdown.empty:
                        col.metric(label, str(breakdown.iloc[0].Group))
            if units:
                s3.metric(
                    "Recorded units", format_value(kpis(filtered, units)["total"])
                )
            st.caption(
                "Revenue is recorded revenue, not profit. Mapped fields can be changed in the sidebar."
            )
    if filtered.empty:
        st.info("No records match the filters. Reset or widen them to continue.")
    else:
        c1, c2, c3 = st.columns(3)
        kind = c1.selectbox("Chart type", CHARTS)
        operation = c2.selectbox(
            "Aggregation",
            ["sum", "mean", "median", "min", "max", "count"],
            help="Count means number of records, not nonmissing metric values.",
        )
        limit = c3.slider("Categories to display", 1, 50, 15)
        ascending = st.checkbox("Sort smallest first")
        chart_group = group
        second = None
        if kind in ("Line", "Area"):
            chart_group = select("Time axis", dates, "chart_date")
        if kind == "Scatter":
            second = select(
                "Second numeric column", nums, "second", nums[-1] if nums else None
            )
        try:
            fig, table = build_chart(
                filtered, kind, metric, chart_group, second, operation, limit, ascending
            )
            st.plotly_chart(
                fig,
                width="stretch",
                config={
                    "displaylogo": False,
                    "toImageButtonOptions": {
                        "format": "png",
                        "filename": "insightai_chart",
                    },
                },
            )
            ss.last_chart = {"table": table, "kind": kind}
            st.caption(
                "Download a chart PNG using the camera icon. Hover for values. Distribution/scatter/box charts show up to the first 10,000 filtered rows; aggregate charts use all selected records."
            )
            with st.expander("Inspect the chart data"):
                st.dataframe(table, width="stretch")
            st.download_button(
                "Download chart data",
                csv_bytes(table.reset_index() if kind == "Correlation" else table),
                "insightai_chart.csv",
                "text/csv",
            )
        except DataError as exc:
            st.info(str(exc))

elif page == "AI Insights":
    st.title("Evidence first. Interpretation second.")
    verified = facts(filtered, metric, group, dates[0] if len(dates) == 1 else None)
    for fact in verified:
        with st.container(border=True):
            st.caption(fact["id"] + " · CALCULATED FINDING")
            st.write(fact["text"])
    st.markdown("### Optional AI commentary")
    st.caption(
        "AI receives only the findings shown above, including category labels. Review these before sending. It does not receive raw rows. Model commentary can still be wrong."
    )
    if not ss.ai_enabled:
        st.info(
            "Enable external processing in Settings / About to request an explanation. These calculated findings work without an API key."
        )
    if st.button(
        "Generate AI commentary", disabled=not ss.ai_enabled or filtered.empty
    ):
        with st.spinner("Interpreting the verified findings…"):
            try:
                ss.ai_result = service().explain(verified)
                ss.pop("generated_exports", None)
            except DataError as exc:
                st.warning(str(exc))
    if ss.get("ai_result"):
        result = ss.ai_result
        st.write(result["executive_summary"])
        st.caption("References: " + ", ".join(result["evidence_ids"]))
        for field in ("hypotheses_to_investigate", "recommendations", "limitations"):
            st.markdown("#### " + field.replace("_", " ").title())
            for text in result[field]:
                st.write("• " + text)

elif page == "Chat With Your Data":
    st.title("Ask your data")
    st.caption(
        "Answers use the current filters and selected metric. Changing the dataset, cleaning, metric or filters clears this conversation to prevent stale answers."
    )
    st.info(
        "Try “Which product generated the most revenue?”, “What percentage of revenue comes from Laptop?”, “How many records are missing information?” or “Compare 2026-01 and 2026-02”."
    )
    if st.button("Clear chat history"):
        ss.messages = []
        ss.pop("previous_plan", None)
        ss.pop("pending_plan", None)
        st.rerun()

    def save_result(result, question):
        ss.messages.extend(
            [
                {"role": "user", "text": question},
                {
                    "role": "assistant",
                    "text": result["answer"],
                    "table": result["table"],
                    "plan": result["plan"],
                    "records": result["records"],
                },
            ]
        )
        ss.messages = ss.messages[-30:]
        ss.previous_plan = result["plan"]

    for message in ss.messages:
        with st.chat_message(message["role"]):
            st.write(message["text"])
            if message.get("table") is not None:
                st.dataframe(message["table"], hide_index=True, width="stretch")
            if "plan" in message:
                with st.expander("Calculation and scope"):
                    st.caption(
                        f'{message["records"]} records after question-specific filters.'
                    )
                    st.json(message["plan"])
    with st.expander("Structured question form · precise local control"):
        form_op = st.selectbox(
            "Calculation",
            [
                "summary",
                "missing",
                "aggregate",
                "group",
                "share",
                "correlation",
                "trend",
                "compare",
            ],
        )
        form_agg = st.selectbox(
            "Calculation method", ["sum", "mean", "median", "min", "max", "count"]
        )
        form_category = st.text_input("Exact category (for share)")
        form_date = select(
            "Date field (for trend / compare)",
            [None] + dates,
            "form_date",
            dates[0] if dates else None,
        )
        form_periods = st.text_input(
            "Two months (for compare)", placeholder="2026-01,2026-02"
        )
        form_limit = st.number_input("Maximum result categories", 1, 50, 5)
        if st.button("Run local calculation"):
            try:
                plan = make_plan(
                    operation=form_op,
                    metric=metric,
                    group=group,
                    aggregation=form_agg,
                    category=form_category or None,
                    date=form_date,
                    limit=int(form_limit),
                    periods=[p.strip() for p in form_periods.split(",") if p.strip()],
                )
                save_result(
                    execute_plan(filtered, plan),
                    f'{form_op}: {metric or "records"} / {group or "all"}',
                )
                st.rerun()
            except (DataError, ValidationError) as exc:
                st.warning(
                    str(exc)
                    if isinstance(exc, DataError)
                    else "Please check the structured question fields."
                )
    previous = (
        Plan.model_validate(ss.previous_plan) if ss.get("previous_plan") else None
    )
    prompt = st.chat_input("Ask a question about this selection", max_chars=2000)
    if prompt:
        try:
            result = execute_plan(
                filtered, infer_plan(prompt, filtered, metric, previous)
            )
            save_result(result, prompt)
            ss.pop("pending_plan", None)
            st.rerun()
        except (DataError, ValidationError) as exc:
            ss.messages.extend(
                [
                    {"role": "user", "text": prompt},
                    {
                        "role": "assistant",
                        "text": (
                            str(exc)
                            if isinstance(exc, DataError)
                            else "That question produced an invalid plan. Try the structured question form."
                        ),
                    },
                ]
            )
            ss.messages = ss.messages[-30:]
            ss.unresolved_question = prompt
            st.rerun()
    if ss.ai_enabled and ss.get("unresolved_question"):
        st.caption(
            "Optional planner sends this question, column names/types and the last plan to OpenAI. You must review its proposed calculation before running it."
        )
        st.write(ss.unresolved_question)
        if st.button("Ask AI to propose a calculation"):
            try:
                ss.pending_plan = (
                    service()
                    .propose(ss.unresolved_question, filtered, previous)
                    .model_dump()
                )
            except DataError as exc:
                st.warning(str(exc))
    if ss.get("pending_plan"):
        st.warning(
            "Review the metric, aggregation, filters and denominator below. A valid plan can still misunderstand your question."
        )
        st.json(ss.pending_plan)
        if st.button("Run this reviewed plan"):
            try:
                result = execute_plan(filtered, ss.pending_plan)
                save_result(result, ss.get("unresolved_question", "Reviewed AI plan"))
                ss.pop("pending_plan", None)
                ss.pop("unresolved_question", None)
                st.rerun()
            except (DataError, ValidationError) as exc:
                st.warning(
                    str(exc)
                    if isinstance(exc, DataError)
                    else "The AI plan failed validation; it was not executed."
                )

elif page == "Reports & Export":
    st.title("Take the evidence with you")
    st.write(
        "Cleaned CSV contains the full working dataset. Selection CSV, Excel and PDF use the active filters shown below."
    )
    st.json(context, expanded=False)
    st.caption(
        "Spreadsheet exports prefix potentially executable text with an apostrophe. Numeric values remain numeric."
    )
    left, right = st.columns(2)
    left.download_button(
        "Full cleaned CSV",
        csv_bytes(df),
        "insightai_cleaned.csv",
        "text/csv",
        width="stretch",
    )
    right.download_button(
        "Filtered selection CSV",
        csv_bytes(filtered),
        "insightai_selection.csv",
        "text/csv",
        width="stretch",
    )
    st.caption(
        "PDF includes a recorded-total category chart when a metric and breakdown are selected. It does not embed every interactive dashboard chart."
    )
    if st.button("Build Excel and PDF reports", type="primary"):
        with st.spinner("Building your report…"):
            breakdown = aggregate(filtered, group, metric) if group and metric else None
            try:
                ss.generated_exports = {
                    "xlsx": excel_bytes(filtered, context, ss.history, breakdown),
                    "pdf": pdf_bytes(
                        filtered,
                        name,
                        context,
                        ss.history,
                        metric,
                        group,
                        dates[0] if len(dates) == 1 else None,
                        ss.get("ai_result"),
                    ),
                }
            except Exception:
                st.error(
                    "Report generation could not complete. Try a smaller selection; CSV export remains available."
                )
    if ss.get("generated_exports"):
        left, right = st.columns(2)
        left.download_button(
            "Download Excel workbook",
            ss.generated_exports["xlsx"],
            "insightai_analysis.xlsx",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            width="stretch",
        )
        right.download_button(
            "Download PDF report",
            ss.generated_exports["pdf"],
            "insightai_report.pdf",
            "application/pdf",
            width="stretch",
        )

elif page == "Settings / About":
    st.title("Your workspace, your controls")
    with st.container(border=True):
        st.subheader("External AI processing")
        st.write(
            "AI requests may incur OpenAI API charges. This application makes no request until you enable processing and click an AI action. Each browser session allows up to 10 attempts, with no automatic retries and a 1,600-output-token cap per request. These are usage controls, not an account-wide spending cap."
        )
        st.checkbox("Enable external AI processing for this dataset", key="ai_enabled")
        st.text_input("OpenAI model ID", key="model")
        st.caption(
            f'API attempts this session: {ss.api_budget["calls"]}/{MAX_CALLS}. Configure account/project spending limits separately. Switching datasets disables consent, but does not reset this counter.'
        )
        st.info(
            "An API key is configured."
            if credentials()
            else "No API key configured. Set OPENAI_API_KEY as an environment variable or in .streamlit/secrets.toml. Local features do not need one."
        )
    st.markdown("### Privacy and operating limits")
    st.write(
        "Uploaded datasets and chat live in Streamlit session memory; this app does not write them to a database or share a global data cache. Hosting infrastructure, browser memory and external AI providers have their own retention behavior. This is not a guarantee of secure deletion or tenant isolation suitable for regulated data."
    )
    st.write(
        "Insights requests send displayed aggregate findings and category labels. Planner requests send your question, schema and prior structured plan. Review labels and questions for sensitive information. Responses use store=False; provider retention policies still apply."
    )
    st.write(
        "Uploads: 15 MB, 100,000 rows, 100 columns, 2 million cells, 80 MB estimated DataFrame memory. XLSX expanded bytes are capped at 80 MB. Cleaning history: 50 steps. Chat: last 30 messages. Browser refresh or session loss can discard work; export it when needed."
    )
    st.markdown("### Beginner’s guide")
    st.write(
        "Pandas computes the numbers. Plotly draws the charts. Streamlit manages the screen and session. Optional OpenAI commentary interprets a small summary. A validated plan selects trusted calculations; generated code is never executed."
    )
    st.write(
        "Use the Streamlit menu → Settings to switch between light and dark themes. Dates are inferred only when already datetime or unambiguous ISO; use Data Cleaning for other formats."
    )
    st.caption(
        "InsightAI 1.0 · Original sales sample preserved · No deployment performed"
    )

st.divider()
st.caption("INSIGHTAI  /  Explore with curiosity. Decide with evidence.")
