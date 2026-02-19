"""
Streamlit UI -- Governed Analytics Copilot.

Features:
  - Persistent chat history (session state)
  - Sidebar with live metric/dimension catalog
  - Collapsible QuerySpec, Generated SQL, and Audit panels
  - Results table with download button
  - Graceful error display for validation/safety violations
  - RBAC role selector
  - Auto-chart visualisation
  - Metric suggestions (typeahead)
  - Cache stats display
  - Explanation panel for blocked queries
"""
import streamlit as st
import httpx
import pandas as pd
import json


API_BASE = "http://localhost:8000"
_TIMEOUT = 30

st.set_page_config(
    page_title="Governed Analytics Copilot",
    page_icon="chart_with_upwards_trend",
    layout="wide",
    initial_sidebar_state="expanded",
)


if "messages" not in st.session_state:
    st.session_state.messages = []

if "catalog" not in st.session_state:
    st.session_state.catalog = None

if "selected_role" not in st.session_state:
    st.session_state.selected_role = None



def _load_catalog():
    """Fetch /catalog from the API; cache in session_state."""
    try:
        resp = httpx.get(f"{API_BASE}/catalog", timeout=5).json()
        st.session_state.catalog = resp
    except Exception:
        st.session_state.catalog = None


def _fetch_suggestions(query: str) -> list[dict]:
    """Fetch metric/dimension suggestions from the API."""
    if not query or len(query) < 2:
        return []
    try:
        resp = httpx.get(f"{API_BASE}/ask/suggest", params={"q": query}, timeout=3)
        data = resp.json()
        return data.get("suggestions", [])
    except Exception:
        return []


def _fetch_cache_stats() -> dict | None:
    """Fetch cache statistics."""
    try:
        resp = httpx.get(f"{API_BASE}/ask/cache/stats", timeout=3)
        return resp.json()
    except Exception:
        return None


with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/graph-report.png", width=64)
    st.title("Catalog")

    if st.button("Refresh catalog", use_container_width=True):
        _load_catalog()

    if st.session_state.catalog is None:
        _load_catalog()

    catalog = st.session_state.catalog

    if catalog:
        # Metrics
        st.subheader("Metrics")
        for m in catalog.get("metrics", []):
            label = f"**{m['name']}**"
            if m.get("is_derived"):
                label += " _(derived -- not queryable)_"
            st.markdown(f"- {label}")
            st.caption(f"  {m.get('description', '')}")
            dims = m.get("allowed_dimensions", [])
            if dims:
                st.caption(f"  Allowed breakdowns: {', '.join(dims)}")

        st.divider()

        # Dimensions
        st.subheader("Dimensions")
        for d in catalog.get("dimensions", []):
            grains = d.get("grains", [])
            grain_str = f" (grains: {', '.join(grains)})" if grains else ""
            st.markdown(f"- **{d['name']}**{grain_str}")

        st.divider()

        # Settings
        st.subheader("Limits")
        st.write(f"Max rows: **{catalog.get('max_rows', 200)}**")
        st.write(f"Allowed tables: **{len(catalog.get('allowed_tables', []))}**")
    else:
        st.info("API not reachable -- start the FastAPI server first.\n\n```\nuvicorn src.api.main:app --reload\n```")

    st.divider()

    # ── RBAC Role Selector ──────────────────────────────
    st.subheader("Role (RBAC)")
    role_options = ["(none)", "finance", "marketing", "analyst", "viewer"]
    selected = st.selectbox(
        "Select your role",
        role_options,
        index=0,
        help="Choose a role to enforce access control. '(none)' disables RBAC.",
    )
    st.session_state.selected_role = None if selected == "(none)" else selected

    st.divider()

    # ── Cache Stats ─────────────────────────────────────
    st.subheader("Cache")
    cache_stats = _fetch_cache_stats()
    if cache_stats:
        c1, c2 = st.columns(2)
        c1.metric("Entries", cache_stats.get("size", 0))
        c2.metric("Hit Rate", f"{cache_stats.get('hit_rate', 0):.0%}")
        if st.button("Clear cache", use_container_width=True):
            try:
                httpx.post(f"{API_BASE}/ask/cache/clear", timeout=3)
                st.success("Cache cleared!")
            except Exception:
                st.warning("Could not clear cache.")

    st.divider()
    st.caption("Governed Analytics Copilot v0.6")



st.title("Governed Analytics Copilot")
st.markdown("Ask a business question in plain English. The copilot will plan, validate, and generate governed SQL.")


# ── Metric Suggestion Box ───────────────────────────────
with st.expander("Metric & dimension search", expanded=False):
    search_input = st.text_input(
        "Start typing a metric or dimension name…",
        placeholder="e.g. revenue, orders, country",
        key="suggestion_input",
    )
    if search_input:
        suggestions = _fetch_suggestions(search_input)
        if suggestions:
            for s in suggestions:
                badge = "metric" if s["kind"] == "metric" else "dim"
                derived = " _(derived)_" if s.get("is_derived") else ""
                score_pct = f"{s['score']:.0%}"
                st.markdown(
                    f"- **{s['name']}** `{badge}` {derived} — {s['description']}  "
                    f"_(match: {score_pct})_"
                )
        else:
            st.caption("No suggestions found.")


with st.expander("Example questions", expanded=False):
    examples = [
        "Revenue by country last 6 months",
        "Monthly orders this year",
        "Top 10 brands by items sold last 3 months",
        "Average order value by category",
        "Weekly revenue in US last 12 weeks",
        "Active users last 30 days",
    ]
    cols = st.columns(2)
    for i, ex in enumerate(examples):
        if cols[i % 2].button(ex, key=f"ex_{i}", use_container_width=True):
            st.session_state.prefill = ex


def _render_chart(chart: dict, rows: list[dict]):
    """Render a chart based on the ChartSpec returned by the API."""
    if not chart or not rows:
        return

    df = pd.DataFrame(rows)
    chart_type = chart.get("chart_type", "table")
    title = chart.get("title", "")

    st.subheader(f"📊 {title}")

    if chart_type == "metric":
        # Single KPI card
        kpi_val = chart.get("kpi_value", "—")
        kpi_label = chart.get("kpi_label", "")
        st.metric(label=kpi_label.replace("_", " ").title(), value=kpi_val)

    elif chart_type == "line":
        x = chart.get("x_column")
        y = chart.get("y_column")
        if x and y and x in df.columns and y in df.columns:
            color = chart.get("color_column")
            if color and color in df.columns:
                st.line_chart(df, x=x, y=y, color=color)
            else:
                st.line_chart(df.set_index(x)[[y]])

    elif chart_type == "bar":
        x = chart.get("x_column")
        y = chart.get("y_column")
        if x and y and x in df.columns and y in df.columns:
            st.bar_chart(df.set_index(x)[[y]])

    elif chart_type == "pie":
        x = chart.get("x_column")
        y = chart.get("y_column")
        if x and y and x in df.columns and y in df.columns:
            # Streamlit doesn't have native pie chart — use a table + bar as fallback
            st.bar_chart(df.set_index(x)[[y]])
            st.caption("(Pie chart shown as bar — full pie rendering available with Plotly)")

    else:
        # table fallback
        st.dataframe(df, use_container_width=True)


def _render_response(data: dict):
    """Render a copilot response inside a chat message."""
    success = data.get("success", False)
    cached = data.get("cached", False)

    if success:
        cache_badge = "  ⚡ cached" if cached else ""
        st.success(f"✅ Query planned successfully  ·  {data.get('latency_ms', 0)} ms{cache_badge}")
    else:
        st.error("❌ Query has issues -- check details below")

    # RBAC errors
    rbac_errors = data.get("rbac_errors", [])
    if rbac_errors:
        with st.expander("🔒 Access Control (RBAC) Errors", expanded=True):
            for e in rbac_errors:
                st.error(f"**RBAC:** {e}")

    # Validation / safety errors
    v_errors = data.get("validation_errors", [])
    s_errors = data.get("safety_errors", [])
    if v_errors or s_errors:
        with st.expander("⚠️ Validation & Safety Errors", expanded=True):
            for e in v_errors:
                st.error(f"**Validation:** {e}")
            for e in s_errors:
                st.error(f"**Safety:** {e}")

    # Explanation (LLM-based)
    explanation = data.get("explanation", "")
    if explanation:
        with st.expander("💡 Explanation & Fix Suggestions", expanded=True):
            st.markdown(explanation)

    # Cost warnings
    cost_warnings = data.get("cost_warnings", [])
    cost_score = data.get("cost_score", 0)
    if cost_warnings or cost_score > 50:
        with st.expander(f"⏱️ Performance (cost score: {cost_score}/100)", expanded=False):
            for w in cost_warnings:
                st.warning(w)
            if cost_score > 70:
                st.error(f"⚠️ High cost score ({cost_score}/100) — query may be slow.")

    # QuerySpec
    with st.expander("QuerySpec", expanded=False):
        st.json(data.get("spec", {}))

    # Generated SQL
    sql = data.get("sql", "")
    if sql:
        with st.expander("Generated SQL", expanded=True):
            st.code(sql, language="sql")

    # Chart auto-generation
    rows = data.get("rows", [])
    chart = data.get("chart")
    if chart and rows:
        _render_chart(chart, rows)

    # Results table
    if rows:
        st.subheader("📋 Results")
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True)
        st.download_button(
            "Download CSV",
            df.to_csv(index=False),
            file_name="copilot_results.csv",
            mime="text/csv",
        )
    elif success:
        st.info("No result rows yet (SQL execution available in Phase 6).")

    # Audit panel
    with st.expander("Audit Trail", expanded=False):
        st.write("**Question:**", data.get("question", ""))
        st.write("**Latency:**", f"{data.get('latency_ms', 0)} ms")
        st.write("**Cached:**", "Yes" if cached else "No")
        st.write("**Role:**", data.get("role", "—"))
        st.write("**Cost score:**", f"{cost_score}/100")
        st.write("**Validation errors:**", v_errors if v_errors else "None")
        st.write("**Safety errors:**", s_errors if s_errors else "None")
        st.write("**RBAC errors:**", rbac_errors if rbac_errors else "None")


for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if msg["role"] == "user":
            st.markdown(msg["content"])
        else:
            _render_response(msg["data"]) if "data" in msg else st.markdown(msg["content"])



# Handle prefilled example question
prefill = st.session_state.pop("prefill", None)
question = st.chat_input("Ask a business question...") or prefill

if question:
    # Display user message
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    # Call API
    with st.chat_message("assistant"):
        with st.spinner("Planning and validating..."):
            try:
                payload = {
                    "question": question,
                    "mode": "mock",
                    "role": st.session_state.selected_role,
                }
                resp = httpx.post(
                    f"{API_BASE}/ask",
                    json=payload,
                    timeout=_TIMEOUT,
                )
                resp.raise_for_status()
                data = resp.json()
            except httpx.ConnectError:
                st.error("Cannot reach the API. Start it with:\n```\nuvicorn src.api.main:app --reload\n```")
                st.stop()
            except httpx.HTTPStatusError as exc:
                st.error(f"API returned {exc.response.status_code}: {exc.response.text}")
                st.stop()
            except Exception as exc:
                st.error(f"Unexpected error: {exc}")
                st.stop()

        _render_response(data)
        st.session_state.messages.append({"role": "assistant", "data": data})

