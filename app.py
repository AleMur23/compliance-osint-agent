"""
Streamlit web interface for the Adverse Media & OSINT Compliance Agent.
Enterprise flow: Document Extraction (Step 1) → Standalone OSINT (Step 2).
"""

import os
import tempfile
from pathlib import Path

import fitz
import streamlit as st

from api_usage import (
    MAX_GLOBAL_REQUESTS,
    get_global_api_count,
    increment_global_api_count,
)
from core import AdverseMediaAgent

# Load .env (GROQ_API_KEY, TAVILY_API_KEY) for cloud-only MVP
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Page config (must be first Streamlit command)
st.set_page_config(
    page_title="OSINT Compliance Agent",
    page_icon="🛡️",
    layout="wide",
)

# Session state
if "extracted" not in st.session_state:
    st.session_state.extracted = None
if "pdf_context" not in st.session_state:
    st.session_state.pdf_context = None
if "search_term" not in st.session_state:
    st.session_state.search_term = ""
if "last_report" not in st.session_state:
    st.session_state.last_report = None
if "last_search_data" not in st.session_state:
    st.session_state.last_search_data = None
if "osint_entity_input" not in st.session_state:
    st.session_state.osint_entity_input = ""
if "tavily_credits" not in st.session_state:
    st.session_state.tavily_credits = 280
if "used_dummy_profile" not in st.session_state:
    st.session_state.used_dummy_profile = False

# --- Sidebar ---
st.sidebar.title("⚙️ Settings")

st.sidebar.markdown(
    "🚨 **Cloud Demo (Not Air-Gapped)**: Uses public APIs (Groq & Tavily) to accommodate "
    "server limits. **Do NOT upload real PII.** The 100% private, offline version is available "
    "on the GitHub `main` branch."
)
global_api_count = get_global_api_count()
limit_reached = global_api_count >= MAX_GLOBAL_REQUESTS
st.sidebar.caption(f"**Global API Usage:** {global_api_count}/{MAX_GLOBAL_REQUESTS} requests")
if limit_reached:
    st.sidebar.error(
        "Demo limit reached. Run the app locally from the GitHub repo for unlimited use."
    )
st.sidebar.markdown("---")

groq_key = (os.environ.get("GROQ_API_KEY") or "").strip() or None
tavily_key = (os.environ.get("TAVILY_API_KEY") or "").strip() or None

if not groq_key:
    st.sidebar.error("Set `GROQ_API_KEY` in your `.env` file.")
if not tavily_key:
    st.sidebar.error("Set `TAVILY_API_KEY` in your `.env` file to run OSINT searches.")

if tavily_key:
    st.sidebar.metric("Tavily Credits Remaining", st.session_state.tavily_credits)

def _get_agent():
    """Build agent (Groq + Tavily); keys from env."""
    return AdverseMediaAgent(groq_api_key=groq_key or None)

# --- Main area ---
st.title("Secure document handling")
st.caption("Model: **Groq (llama-3.3-70b-versatile)**")
st.markdown("---")

if limit_reached:
    st.error(
        "**Demo limit reached.** The global API request limit has been reached. "
        "To continue, run the app locally from the GitHub repository (no limit when self-hosted)."
    )
    st.markdown("---")

# ----- Step 1: Document upload & extraction -----
st.subheader("Step 1: Document upload & extraction")
st.markdown(
    "Upload a KYC document or test safely with our synthetic profile. "
    "*Note: Data is processed via secure but public APIs.*"
)
uploaded_file = st.file_uploader(
    "Choose a PDF document",
    type=["pdf"],
    help="Only PDF files are supported.",
    key="pdf_upload",
)

use_dummy = st.button(
    "📄 Load 'dummy_profile.pdf' (Safe Test)",
    key="use_dummy_btn",
    disabled=limit_reached,
)

def _run_extraction(pdf_bytes: bytes, *, from_dummy: bool = False) -> None:
    """Run extraction on PDF bytes and update session state."""
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(pdf_bytes)
            tmp_path = Path(tmp.name)
        agent = _get_agent()
        extracted = agent.extract_entity_from_pdf(tmp_path)
        doc = fitz.open(tmp_path)
        pdf_context = "\n".join(page.get_text() for page in doc).strip()
        doc.close()
        if not pdf_context:
            pdf_context = "(No text could be extracted from the PDF.)"
        st.session_state.extracted = extracted
        st.session_state.pdf_context = pdf_context
        st.session_state.used_dummy_profile = from_dummy
    finally:
        if tmp_path and tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass

if use_dummy:
    if limit_reached:
        st.stop()
    if not groq_key:
        st.error("Cannot run: `GROQ_API_KEY` is not set in `.env`.")
        st.stop()
    dummy_path = Path("dummy_profile.pdf")
    if not dummy_path.exists():
        st.error("`dummy_profile.pdf` not found in the project root. Add the file to enable safe test.")
        st.stop()
    with st.spinner("Loading dummy profile and extracting…"):
        try:
            increment_global_api_count()
            pdf_bytes = open(dummy_path, "rb").read()
            _run_extraction(pdf_bytes, from_dummy=True)
            st.success("✅ **Dummy profile loaded and extracted.** You can load Subject or Employer into OSINT below.")
            st.rerun()
        except Exception as e:
            st.error(f"Dummy profile extraction failed: {e}")
            st.exception(e)
    st.stop()

extract_clicked = st.button(
    "Extract Information",
    type="primary",
    key="extract_btn",
    disabled=limit_reached,
)

if extract_clicked:
    if limit_reached:
        st.stop()
    if uploaded_file is None:
        st.warning("Please upload a PDF file first.")
        st.stop()
    if not groq_key:
        st.error("Cannot run: `GROQ_API_KEY` is not set in `.env`.")
        st.stop()

    try:
        with st.spinner("Extracting structured information…"):
            try:
                increment_global_api_count()
                _run_extraction(uploaded_file.getvalue(), from_dummy=False)
                st.session_state.used_dummy_profile = False
                st.success("Information extracted. You can load Subject or Employer into OSINT below.")
                st.rerun()
            except ValueError as e:
                st.error(str(e))
                st.stop()
            except Exception as e:
                st.error(f"Extraction failed: {e}")
                st.exception(e)
                st.stop()
    except Exception as e:
        st.error(f"An error occurred: {e}")
        raise

# Show extracted fields when Step 1 is complete
if st.session_state.extracted:
    ex = st.session_state.extracted
    if st.session_state.used_dummy_profile:
        st.info("📄 **Using synthetic profile:** *dummy_profile.pdf* (safe test data).")
    st.markdown("#### Extracted information")
    col1, col2 = st.columns(2)
    with col1:
        st.text_input("Subject", value=ex.get("subject_name", ""), disabled=True, key="disp_subject")
        st.text_input("Employer", value=ex.get("employer", "") or "—", disabled=True, key="disp_employer")
    with col2:
        st.text_area("Income / source of funds", value=ex.get("income_description", "") or "—", disabled=True, height=120, key="disp_income")
    st.text_area("Summary", value=ex.get("summary", "") or "—", disabled=True, height=120, key="disp_summary")
    st.markdown("---")

# ----- Step 2: Standalone OSINT (always visible) -----
st.header("Adverse Media Screening")
st.caption("GPT powered OSINT search. Run a search on any entity below.")

# Load-from-extraction buttons (only when we have extracted data)
if st.session_state.extracted:
    ex = st.session_state.extracted
    sub_name = (ex.get("subject_name") or "").strip()
    emp_name = (ex.get("employer") or "").strip()
    load_col1, load_col2, _ = st.columns([1, 1, 2])
    with load_col1:
        if st.button("Load Extracted Subject", key="load_subject"):
            st.session_state.search_term = sub_name
            st.session_state.osint_entity_input = sub_name
            st.rerun()
    with load_col2:
        if st.button("Load Extracted Employer", key="load_employer", disabled=not emp_name):
            st.session_state.search_term = emp_name
            st.session_state.osint_entity_input = emp_name
            st.rerun()

# Editable search term; Load buttons set osint_entity_input
st.text_input(
    "Entity to search for Adverse Media:",
    key="osint_entity_input",
    placeholder="e.g. Person or company name",
)

run_osint_clicked = st.button(
    "Run OSINT Search",
    type="primary",
    key="run_osint",
    disabled=limit_reached,
)

if run_osint_clicked:
    if limit_reached:
        st.stop()
    entity_to_search = (st.session_state.get("osint_entity_input") or "").strip()
    if not entity_to_search:
        st.warning("Enter an entity name to search for adverse media.")
        st.stop()
    if not tavily_key:
        st.error("TAVILY_API_KEY is not set. Add it to .env to run OSINT.")
        st.stop()
    if not groq_key:
        st.error("GROQ_API_KEY is not set. Add it to .env to run OSINT.")
        st.stop()

    try:
        agent = _get_agent()
    except ValueError as e:
        st.error(str(e))
        st.stop()

    with st.status("Running OSINT and risk analysis…", expanded=True) as status:
        st.write(f"**1. Searching adverse media for: {entity_to_search}**")
        try:
            increment_global_api_count()
            search_data = agent.search_adverse_media(entity_to_search)
            st.session_state.tavily_credits -= 1
            st.write(f"✓ Found **{len(search_data['results'])}** result(s), **{len(search_data.get('images', []))}** image(s)")
        except Exception as e:
            status.update(label="Error", state="error")
            st.exception(e)
            st.stop()

        st.write("**2. Generating risk report…**")
        pdf_context = st.session_state.get("pdf_context") or "No document context (standalone OSINT search)."
        try:
            report = agent.analyze_risk(
                entity_name=entity_to_search,
                pdf_context=pdf_context,
                search_results=search_data["results"],
            )
            st.write("✓ Report generated")
        except Exception as e:
            status.update(label="Error", state="error")
            st.exception(e)
            st.stop()

        status.update(label="Complete", state="complete")

    st.session_state.last_report = report
    st.session_state.last_search_data = search_data
    st.rerun()

# Display last report and images (when available)
if st.session_state.last_report:
    st.markdown("---")
    st.subheader("📋 Report")
    st.markdown(st.session_state.last_report)

    search_data = st.session_state.last_search_data or {}
    images = search_data.get("images") or []
    if images:
        with st.expander("📸 Related Media Thumbnails", expanded=True):
            n = len(images)
            cols = st.columns(n)
            for i, img_url in enumerate(images):
                with cols[i]:
                    st.markdown(
                        f'<a href="{img_url}" target="_blank"><img src="{img_url}" style="width:100%; border-radius:8px;"></a>',
                        unsafe_allow_html=True,
                    )
                    display_url = f"{img_url[:40]}..." if len(img_url) > 40 else img_url
                    st.caption(f"Source: [{display_url}]({img_url})")
