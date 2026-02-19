"""
Private Compliance Agent – Entry point.

Orchestrates the adverse media pipeline: PDF entity extraction,
OSINT search, and LLM-based risk report. All processing is local.
"""

import os
import sys

import fitz

from core import AdverseMediaAgent

# Target PDF to screen (place in project root or set full path)
PDF_PATH = "dummy_profile.pdf"

# ASCII banner for the final report
REPORT_BANNER = """
================================================================================
                        ADVERSE MEDIA REPORT
================================================================================
"""


def load_pdf_context(pdf_path: str) -> str:
    """Extract full text from PDF for use as context in risk analysis."""
    doc = fitz.open(pdf_path)
    try:
        chunks = [page.get_text() for page in doc]
        return "\n".join(chunks).strip() or "(No text extracted)"
    finally:
        doc.close()


def main() -> None:
    if not os.path.exists(PDF_PATH):
        print(f"Error: PDF file not found: {PDF_PATH}", file=sys.stderr)
        print("Please add the target PDF to this directory or set PDF_PATH.", file=sys.stderr)
        sys.exit(1)

    print("Initializing Adverse Media Agent (local LLM)...")
    agent = AdverseMediaAgent()

    print("\n[1/3] Extracting entity from PDF...")
    entity_name = agent.extract_entity_from_pdf(PDF_PATH)
    print(f"      Entity identified: {entity_name}")

    print("\n[2/3] Searching OSINT sources for adverse media...")
    search_results = agent.search_adverse_media(entity_name)
    print(f"      Retrieved {len(search_results)} result(s).")

    pdf_context = load_pdf_context(PDF_PATH)

    print("\n[3/3] Analyzing risk (Senior AML Investigator)...")
    report = agent.analyze_risk(entity_name, pdf_context, search_results)

    print(REPORT_BANNER)
    print(report)
    print("================================================================================\n")


if __name__ == "__main__":
    main()
