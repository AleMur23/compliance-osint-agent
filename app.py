"""
Streamlit web interface for the Adverse Media & OSINT Compliance Agent.
Enterprise flow: Document Extraction (Step 1) → Standalone OSINT (Step 2).
"""

import os
import tempfile
from pathlib import Path

import fitz
import streamlit as st

from core import AdverseMediaAgent

# Load .env (GROQ_API_KEY, TAVILY_API_KEY)
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

# --- Sidebar: Clear visual flow ---
st.sidebar.title("⚙️ Engine Settings")

st.sidebar.markdown("### 🧠 1. Document Extraction (LLM)")
backend_choice = st.sidebar.radio(
    "Backend",
    options=[
        "Local (Ollama - 100% Private)",
        "Cloud Demo (Groq - Ultra Fast)",
    ],
    index=0,
    key="backend_radio",
)

backend = "ollama" if "Ollama" in backend_choice else "groq"
groq_key = os.environ.get("GROQ_API_KEY") or None
tavily_key = (os.environ.get("TAVILY_API_KEY") or "").strip() or None

if backend == "groq":
    if not groq_key or not groq_key.strip():
        st.sidebar.error(
            "**Groq selected:** Set `GROQ_API_KEY` in your `.env` file to use Cloud Demo."
        )
    else:
        st.sidebar.caption(
            "⚠️ Cloud Demo sends data to Groq's API. For sensitive data use Local (Ollama)."
        )

st.sidebar.markdown(
    "<div style='text-align: center; font-size: 24px;'>⬇️</div>",
    unsafe_allow_html=True,
)
st.sidebar.markdown("### 🌐 2. OSINT Search (Tavily)")
st.sidebar.caption("Tavily powers web screening for adverse media. Usage is tracked below.")

if not tavily_key:
    st.sidebar.error(
        "**OSINT:** Set `TAVILY_API_KEY` in your `.env` file to run adverse media searches."
    )
else:
    st.sidebar.metric("Tavily Credits Remaining", st.session_state.tavily_credits)

def _get_agent():
    """Build agent from current sidebar backend; uses env for Groq and Tavily."""
    if not tavily_key:
        raise ValueError("TAVILY_API_KEY is not set. Add it to .env for OSINT search.")
    if backend == "groq" and not (groq_key and groq_key.strip()):
        raise ValueError("GROQ_API_KEY is not set. Add it to .env to use Groq.")
    return AdverseMediaAgent(
        backend=backend,
        groq_api_key=(groq_key or "").strip() or None,
    )

def _model_label() -> str:
    if backend == "ollama":
        return "Ollama (llama3.2)"
    return "Groq"

# --- Main area ---
st.title("Secure document handling")
st.caption(f"Model active: **{_model_label()}**")
st.markdown("---")

# ----- Step 1: Document upload & extraction (unchanged) -----
st.subheader("Step 1: Document upload & extraction")
uploaded_file = st.file_uploader(
    "Choose a PDF document",
    type=["pdf"],
    help="Only PDF files are supported.",
    key="pdf_upload",
)

extract_clicked = st.button("Extract Information", type="primary", key="extract_btn")

if extract_clicked:
    if uploaded_file is None:
        st.warning("Please upload a PDF file first.")
        st.stop()
    if backend == "groq" and not (groq_key and groq_key.strip()):
        st.error("Cannot run: Groq is selected but `GROQ_API_KEY` is not set in `.env`.")
        st.stop()

    tmp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(uploaded_file.getvalue())
            tmp_path = Path(tmp.name)

        with st.spinner("Extracting structured information…"):
            try:
                agent = _get_agent()
                extracted = agent.extract_entity_from_pdf(tmp_path)
                doc = fitz.open(tmp_path)
                pdf_context = "\n".join(page.get_text() for page in doc).strip()
                doc.close()
                if not pdf_context:
                    pdf_context = "(No text could be extracted from the PDF.)"
            except ValueError as e:
                st.error(str(e))
                st.stop()
            except Exception as e:
                st.error(f"Extraction failed: {e}")
                st.exception(e)
                st.stop()
            finally:
                if tmp_path and tmp_path.exists():
                    try:
                        tmp_path.unlink()
                    except OSError:
                        pass

        st.session_state.extracted = extracted
        st.session_state.pdf_context = pdf_context
        st.success("Information extracted. You can load Subject or Employer into OSINT below.")
        st.rerun()

    except Exception as e:
        st.error(f"An error occurred: {e}")
        raise

# Show extracted fields when Step 1 is complete
if st.session_state.extracted:
    ex = st.session_state.extracted
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

run_osint_clicked = st.button("Run OSINT Search", type="primary", key="run_osint")

if run_osint_clicked:
    entity_to_search = (st.session_state.get("osint_entity_input") or "").strip()
    if not entity_to_search:
        st.warning("Enter an entity name to search for adverse media.")
        st.stop()
    if not tavily_key:
        st.error("TAVILY_API_KEY is not set. Add it to .env to run OSINT.")
        st.stop()
    if backend == "groq" and not (groq_key and groq_key.strip()):
        st.error("Groq is selected but GROQ_API_KEY is not set in .env.")
        st.stop()

    try:
        agent = _get_agent()
    except ValueError as e:
        st.error(str(e))
        st.stop()

    with st.status("Running OSINT and risk analysis…", expanded=True) as status:
        st.write(f"**1. Searching adverse media for: {entity_to_search}**")
        try:
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
