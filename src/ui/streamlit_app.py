"""
Streamlit UI -- Governed Analytics Copilot.

Features:
  - Persistent chat history (session state)
  - Sidebar with live metric/dimension catalog
  - Collapsible QuerySpec, Generated SQL, and Audit panels
  - Results table with download button
  - Graceful error display for validation/safety violations
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



def _load_catalog():
    """Fetch /catalog from the API; cache in session_state."""
    try:
        resp = httpx.get(f"{API_BASE}/catalog", timeout=5).json()
        st.session_state.catalog = resp
    except Exception:
        st.session_state.catalog = None


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
                label += " _(derived)_"
            st.markdown(f"- {label}")
            st.caption(f"  {m.get('description', '')}")

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
    st.caption("Governed Analytics Copilot v0.5")



st.title("Governed Analytics Copilot")
st.markdown("Ask a business question in plain English. The copilot will plan, validate, and generate governed SQL.")


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


def _render_response(data: dict):
    """Render a copilot response inside a chat message."""
    success = data.get("success", False)

    if success:
        st.success(f"OK: Query planned successfully  ·  {data.get('latency_ms', 0)} ms")
    else:
        st.error("ERROR: Query has issues -- check audit panel below")

    # Validation / safety errors
    v_errors = data.get("validation_errors", [])
    s_errors = data.get("safety_errors", [])
    if v_errors or s_errors:
        with st.expander("Errors", expanded=True):
            for e in v_errors:
                st.error(f"**Validation:** {e}")
            for e in s_errors:
                st.error(f"**Safety:** {e}")

    # QuerySpec
    with st.expander("QuerySpec", expanded=False):
        st.json(data.get("spec", {}))

    # Generated SQL
    sql = data.get("sql", "")
    if sql:
        with st.expander("Generated SQL", expanded=True):
            st.code(sql, language="sql")

    # Results table
    rows = data.get("rows", [])
    if rows:
        st.subheader("Results")
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
        st.write("**Validation errors:**", v_errors if v_errors else "None")
        st.write("**Safety errors:**", s_errors if s_errors else "None")


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
                resp = httpx.post(
                    f"{API_BASE}/ask",
                    json={"question": question, "mode": "mock"},
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
