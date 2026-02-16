"""
Streamlit page — Query History.
"""
import streamlit as st

st.set_page_config(page_title="Query History", layout="wide")
st.title("Query History")
st.caption("Browse past copilot queries stored in `marts.copilot_query_logs`.")

st.info("History will be available after Phase 6 wires up query logging.")

# Phase 6: fetch from copilot_query_logs and display with date/success filters.
