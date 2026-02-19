# Enterprise-Grade Compliance Agent: Secure Document Handling & Agentic OSINT Adverse Media Screener

A production-oriented KYC/AML workflow that combines **structured document extraction** with **agentic OSINT adverse media screening**, designed for FinTech and regulated environments where data privacy and auditability matter.

---

## 1. Overview / Elevator Pitch

This agent reduces **Know Your Customer (KYC)** and **Enhanced Due Diligence (EDD)** friction by:

- **Extracting structured data** from KYC/EDD PDFs (subject, employer, income, summary) via an LLM, with strict JSON output to cut down manual data entry and errors.
- **Running targeted adverse media screening** using the Tavily API (news, legal, and government-oriented sources) instead of generic search, which helps **reduce false positives** and noise from forums and Q&A sites.
- **Keeping sensitive document content optional on-premises** by supporting a **dual LLM architecture**: local **Ollama** for air-gapped, 100% private processing, or **Groq** in the cloud for ultra-fast demos when privacy is relaxed.

The result is a **human-in-the-loop** tool that fits into existing compliance workflows: analysts upload a document, review extracted fields, run OSINT on the subject or employer, and get a structured risk report with sources—without sending PII to third parties unless they explicitly choose the cloud LLM.

---

## 2. Key Features

| Feature | Description |
|--------|-------------|
| **Dual LLM architecture** | **Local (Ollama, llama3.2)** for 100% data privacy and air-gapped compliance; **Cloud (Groq, Llama-3.3-70b-versatile)** for ultra-fast processing in demos or non-sensitive environments. |
| **Agentic OSINT** | Integration with the **Tavily API** for forensic web screening: advanced search targeting news, legal, and government sources, with image retrieval and strict anti-hallucination prompts so the LLM only cites provided URLs. |
| **Human-in-the-loop UI** | **Streamlit** interface with editable search entities, “Load Subject” / “Load Employer” from extracted data, simulated Tavily credit tracking (FinOps-style), and clickable media thumbnails with visible source URLs. |
| **Structured extraction** | **LangChain** + **Pydantic** enforce strict JSON parsing of KYC documents: **Subject**, **Employer**, **Income/Financials** (amounts, currency, dates, regularity), and **Summary**, reducing drift and manual cleanup. |

---

## 3. System Architecture

The application follows a **2-step pipeline**:

```
┌─────────────────────────────────────────────────────────────────┐
│  Step 1: AI PDF Extraction (LLM)                                 │
│  Upload PDF → PyMuPDF text extraction → LLM (Ollama/Groq)       │
│  → Pydantic-validated JSON (subject, employer, income, summary)  │
└─────────────────────────────────────────────────────────────────┘
                                ↓
┌─────────────────────────────────────────────────────────────────┐
│  Step 2: Automated OSINT Risk Analysis                           │
│  Entity (from Step 1 or manual) → Tavily search (text + images) │
│  → LLM compares document context + search results               │
│  → Adverse Media Report (summary, true/false positive, sources)   │
└─────────────────────────────────────────────────────────────────┘
```

- **Step 1** is driven by the chosen LLM backend (Ollama or Groq) and populates the UI with structured fields; users can then load **Subject** or **Employer** into the OSINT search.
- **Step 2** is **standalone and editable**: users can run OSINT on any entity (with or without a prior document), and the report includes a **Sources & References** section built from the exact URLs returned by Tavily.

---

## 4. Installation & Local Setup

### Prerequisites

- **Python 3.10+**
- **Ollama** (for local LLM): [ollama.com](https://ollama.com)
- **TAVILY_API_KEY** (required for OSINT): [tavily.com](https://tavily.com)
- **GROQ_API_KEY** (optional, only for Cloud Demo backend): [console.groq.com](https://console.groq.com)

### Clone and install

```bash
# Clone the repository
git clone <your-repo-url>
cd compliance-agent

# Create and activate a virtual environment (Unix/macOS)
python3 -m venv .venv
source .venv/bin/activate

# Windows (PowerShell)
# python -m venv .venv
# .venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt
```

### Environment variables

Create a `.env` file in the project root:

```env
TAVILY_API_KEY=tvly-your-tavily-api-key
GROQ_API_KEY=gsk_your-groq-api-key
```

- **TAVILY_API_KEY** is **required** for adverse media search.
- **GROQ_API_KEY** is only needed if you use the “Cloud Demo (Groq)” backend in the UI.

### Local LLM (Ollama)

For the default **Local (Ollama)** backend, install Ollama and pull the model:

```bash
ollama run llama3.2
```

Keep the Ollama service running (default `http://localhost:11434`) when using the local backend.

---

## 5. Usage

Start the Streamlit app from the project root:

```bash
streamlit run app.py --logger.level=error
```

Then:

1. **Step 1 — Document extraction:** Upload a KYC/EDD PDF and click **Extract Information**. Review the extracted Subject, Employer, Income, and Summary.
2. **Step 2 — OSINT:** Optionally click **Load Extracted Subject** or **Load Extracted Employer**, or type any entity name. Click **Run OSINT Search** to run Tavily search and generate the adverse media report. The report and related media thumbnails (with clickable URLs) appear below.

Use the sidebar to switch between **Local (Ollama)** and **Cloud Demo (Groq)** and to see the simulated Tavily credits remaining.

---

## 6. Disclaimer

**OSINT and media thumbnails:**  
Adverse media results and any thumbnails or links displayed are derived from **third-party web sources** (e.g. via Tavily). They are provided for **supporting human review only**. Accuracy, relevance, and completeness of scraped or aggregated content are not guaranteed. Always validate findings against primary sources and your internal policies before making any compliance or risk decisions.

---

## Tech stack (summary)

- **LLM / orchestration:** LangChain, LangChain Core, LangChain Community, LangChain Groq  
- **Local LLM:** Ollama (llama3.2)  
- **Cloud LLM:** Groq (llama-3.3-70b-versatile)  
- **OSINT:** Tavily API (tavily-python)  
- **PDF:** PyMuPDF  
- **Validation:** Pydantic  
- **UI:** Streamlit  
- **Env:** python-dotenv  

See `requirements.txt` for pinned versions and optional dependencies.
