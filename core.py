"""
Private Compliance Agent – Core module.

Local document extraction and automated OSINT Adverse Media screening.
Supports dual LLM backends: Ollama (local/on-prem) and Groq (fast public demos).
"""

import json
import logging
import os
import re
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

import fitz
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_community.llms import Ollama
from langchain_groq import ChatGroq
from pydantic import BaseModel, Field
from tavily import TavilyClient

logger = logging.getLogger(__name__)


def _llm_response_text(response: Any) -> str:
    """Extract plain text from LLM response (Ollama returns str, ChatGroq returns AIMessage)."""
    if hasattr(response, "content"):
        return (response.content or "").strip()
    return (response or "").strip()


class ExtractedEntity(BaseModel):
    """Structured KYC/EDD entity extraction from a document."""

    subject_name: str = Field(description="Full name of the primary subject (person or company)")
    employer: str = Field(description="Employer or organization name, or empty if not stated")
    income_description: str = Field(description="A detailed breakdown of all income sources mentioned. You MUST extract and list exact amounts, currency, specific dates, deductions, net pay, and regularity (e.g., monthly, annual) if present in the text. Do not generalize; extract the exact numerical data.")
    summary: str = Field(description="A concise 2-sentence summary of the actual facts and data presented in the document. DO NOT output instructions.")


class AdverseMediaAgent:
    """
    Agent for adverse media screening: PDF entity extraction, OSINT search,
    and local LLM-based risk analysis. All processing stays on-premises.
    """

    def __init__(
        self,
        backend: str = "ollama",
        groq_api_key: str | None = None,
        model_name: str = "llama3.2",
        base_url: str = "http://localhost:11434",
        **ollama_kwargs: Any,
    ) -> None:
        """
        Initialize the agent with either a local Ollama LLM or Groq.

        Args:
            backend: "ollama" for local inference, "groq" for Groq API.
            groq_api_key: API key for Groq (required if backend=="groq");
                can also be set via GROQ_API_KEY env var.
            model_name: Ollama model (e.g. 'llama3.2'); used only when backend=="ollama".
            base_url: Ollama API base URL; used only when backend=="ollama".
            **ollama_kwargs: Optional kwargs for Ollama (e.g. temperature).
        """
        # Tavily OSINT client (required for search_adverse_media)
        tavily_key = os.environ.get("TAVILY_API_KEY")
        if not tavily_key or not str(tavily_key).strip():
            raise ValueError(
                "TAVILY_API_KEY is required. Set it in your environment or .env file."
            )
        self.tavily_client = TavilyClient(api_key=tavily_key.strip())

        self.backend = backend
        if backend == "ollama":
            self.model_name = model_name
            self.llm = Ollama(
                model=model_name,
                base_url=base_url,
                **ollama_kwargs,
            )
            logger.info(
                "AdverseMediaAgent initialized with backend=ollama, model=%s, base_url=%s",
                model_name,
                base_url,
            )
        elif backend == "groq":
            api_key = groq_api_key or os.environ.get("GROQ_API_KEY")
            if not api_key:
                raise ValueError(
                    "Groq backend requires groq_api_key or GROQ_API_KEY environment variable."
                )
            self.model_name = "llama-3.3-70b-versatile"
            self.llm = ChatGroq(
                model=self.model_name,
                api_key=api_key,
            )
            logger.info(
                "AdverseMediaAgent initialized with backend=groq, model=%s",
                self.model_name,
            )
        else:
            raise ValueError(
                f'backend must be "ollama" or "groq", got: {backend!r}'
            )

    def extract_entity_from_pdf(self, pdf_path: str | Path) -> dict[str, str]:
        """
        Read the PDF and extract structured KYC/EDD fields via the LLM.

        Uses PyMuPDF for text extraction and the LLM as a KYC analyst to
        extract subject_name, employer, income_description, and summary.
        Output is enforced as JSON and validated with Pydantic.

        Args:
            pdf_path: Path to the PDF file.

        Returns:
            Dict with keys: subject_name, employer, income_description, summary.

        Raises:
            FileNotFoundError: If the PDF path does not exist.
            ValueError: If the PDF cannot be read or JSON extraction fails.
        """
        path = Path(pdf_path)
        if not path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        try:
            doc = fitz.open(path)
            text_chunks = [page.get_text() for page in doc]
            doc.close()
        except Exception as e:
            logger.exception("Failed to read PDF: %s", pdf_path)
            raise ValueError(f"Could not read PDF: {e}") from e

        full_text = "\n".join(text_chunks).strip()
        if not full_text:
            raise ValueError(f"No text extracted from PDF: {pdf_path}")

        parser = PydanticOutputParser(pydantic_object=ExtractedEntity)
        format_instructions = parser.get_format_instructions()

        prompt = PromptTemplate.from_template(
            """You are a KYC (Know Your Customer) analyst. Extract the following information from the document as a single JSON object.

Document text:
---
{document_text}
---

{format_instructions}

Output ONLY valid JSON with the four keys. No markdown, no code fences, no explanation."""
        )
        chain = prompt | self.llm
        response = chain.invoke({
            "document_text": full_text,
            "format_instructions": format_instructions,
        })
        raw = _llm_response_text(response)
        # Strip optional markdown code block
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```\s*$", "", raw).strip()
        try:
            entity = parser.parse(raw)
        except Exception as e:
            logger.exception("LLM output did not parse as ExtractedEntity: %s", raw[:200])
            raise ValueError(f"Extraction failed: {e}") from e
        out = entity.model_dump()
        logger.info("Extracted entity from PDF: subject_name=%s", out.get("subject_name"))
        return out

    def search_adverse_media(self, target_entity: str) -> dict[str, Any]:
        """
        Perform Tavily advanced search for adverse media mentions of the target.

        Args:
            target_entity: The entity to search for (e.g. subject name or employer).

        Returns:
            Dict with "results" (list of text-result dicts with title, url, content,
            href, body) and "images" (list of up to 3 image URLs). On failure,
            returns {"results": [], "images": []}.
        """
        query = (
            f"{target_entity} fraud OR money laundering OR scam OR indictment OR SEC OR illegal"
        )
        empty = {"results": [], "images": []}
        try:
            response = self.tavily_client.search(
                query=query,
                search_depth="advanced",
                max_results=5,
                include_raw_content=False,
                include_images=True,
            )
            raw_list = response.get("results") or []
            results = []
            for r in raw_list:
                title = r.get("title", "")
                url = r.get("url", "")
                content = r.get("content", "")
                results.append({
                    "title": title,
                    "url": url,
                    "content": content,
                    "href": url,
                    "body": content,
                })
            raw_images = response.get("images") or []
            image_urls = []
            for img in raw_images[:3]:
                if isinstance(img, dict) and img.get("url"):
                    image_urls.append(img["url"])
                elif isinstance(img, str) and img.strip():
                    image_urls.append(img.strip())
            logger.info(
                "Tavily adverse media search for '%s' returned %d results, %d images",
                target_entity,
                len(results),
                len(image_urls),
            )
            return {"results": results, "images": image_urls}
        except Exception as e:
            logger.warning("Tavily adverse media search failed for '%s': %s", target_entity, e)
            return empty

    def get_tavily_usage(self) -> dict[str, Any]:
        """
        Fetch current Tavily API usage/credits (key-level).

        Returns:
            Dict with 'usage', 'limit', 'status', etc. If the request fails,
            returns {"status": "unknown"}.
        """
        api_key = os.environ.get("TAVILY_API_KEY") or ""
        if not api_key.strip():
            return {"status": "unknown"}
        try:
            req = Request(
                "https://api.tavily.com/usage",
                headers={"Authorization": f"Bearer {api_key.strip()}"},
            )
            with urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
            key_info = data.get("key") or data
            return {
                "status": "ok",
                "usage": key_info.get("usage"),
                "limit": key_info.get("limit"),
                "search_usage": key_info.get("search_usage"),
            }
        except (HTTPError, URLError, json.JSONDecodeError, OSError) as e:
            logger.debug("Tavily usage fetch failed: %s", e)
            return {"status": "unknown"}

    def analyze_risk(
        self,
        entity_name: str,
        pdf_context: str,
        search_results: list[dict[str, Any]],
    ) -> str:
        """
        Compare PDF context with OSINT search results and produce an
        Adverse Media Report via the local LLM (Senior AML Investigator role).

        Args:
            entity_name: Name of the screened entity.
            pdf_context: Relevant text or metadata extracted from the PDF.
            search_results: List of text-result dicts (e.g. search_data["results"])
                with 'title', 'href', and 'body'. The Langchain prompt formats these.

        Returns:
            Full Adverse Media Report string (Executive Summary, True/False
            Positive assessment, Key Findings with sources, Risk Level).
        """
        search_blob = "\n\n".join(
            f"Title: {r.get('title', '')}\nURL: {r.get('href', '')}\nSummary: {r.get('body', '')}"
            for r in (search_results or [])
        )
        if not search_blob.strip():
            search_blob = "(No adverse media search results available.)"

        prompt = PromptTemplate.from_template(
            """You are a Senior AML (Anti-Money Laundering) Investigator. Your task is to compare the subject's KYC document with open-source adverse media search results and produce a structured Adverse Media Report.

CRITICAL ANTI-HALLUCINATION RULE: You must ONLY cite and use the EXACT URLs provided in the search_results. If the search results are empty, irrelevant, or contain garbage links, state clearly that no valid adverse media was found and assess the risk as Low. DO NOT make up, guess, or invent URLs.

Subject under review: {entity_name}

---
KYC / Document context (from PDF):
---
{pdf_context}
---

---
Adverse media search results (OSINT):
---
{search_results}
---

Write a structured Adverse Media Report containing the following sections. Use clear headings and bullet points where appropriate.

1. Executive Summary
   - Brief overview of the subject and whether any adverse findings appear to relate to them.

2. True Positive / False Positive Assessment
   - Does the news or content in the search results actually refer to the same person or company described in the PDF? Or are these likely different individuals/entities (false positives)? Explain your reasoning.

3. Key Findings (with sources)
   - List each relevant finding with the source URL. If none are true positives, state that clearly.

4. Risk Level
   - Conclude with one of: High, Medium, or Low. Justify based on the true positive findings and their severity.

5. Sources & References
   - List every source URL used in your findings (from the search results provided). One URL per line for human review.

Output the full report only. No meta-commentary before or after."""
        )
        chain = prompt | self.llm
        report = chain.invoke({
            "entity_name": entity_name,
            "pdf_context": pdf_context,
            "search_results": search_blob,
        })
        out = _llm_response_text(report)
        # Explicit Sources & References section from search_results URLs
        urls = [r.get("href", "").strip() for r in (search_results or []) if r.get("href")]
        if urls:
            out += "\n\n---\n\n## Sources & References\n\n"
            for u in urls:
                out += f"- {u}\n"
        logger.info("Risk analysis completed for entity: %s", entity_name)
        return out
