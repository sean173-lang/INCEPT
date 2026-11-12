"""Invoke the one deployed n8n workflow and save its validated Markdown report."""
from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
PROJECT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")


def run(company_name: str, register_identifier: str | None = None) -> Path:
    base = (os.getenv("N8N_BASE_URL") or "http://127.0.0.1:5678").rstrip("/")
    token = os.getenv("PROJECT3_WEBHOOK_TOKEN")
    if not token:
        raise RuntimeError("PROJECT3_WEBHOOK_TOKEN is not configured; run the documented setup command")
    url = base + "/webhook/ironhack-company-research"
    try:
        response = requests.post(url, json={"company_name": company_name,
            "register_identifier": register_identifier or ""},
            headers={"X-Project3-Token": token}, timeout=(5, 150), allow_redirects=False)
    except requests.RequestException as exc:
        raise RuntimeError("n8n webhook unavailable (" + type(exc).__name__ + "); no automatic retry") from None
    if not response.ok:
        raise RuntimeError("n8n returned HTTP " + str(response.status_code) + "; no automatic retry")
    try:
        result = response.json()
    except ValueError:
        raise RuntimeError("n8n returned a non-JSON response") from None
    if not isinstance(result, dict) or result.get("ok") is not True:
        step = result.get("failed_step", "unknown step") if isinstance(result, dict) else "unknown step"
        code = result.get("error_code", "research_failed") if isinstance(result, dict) else "research_failed"
        status = result.get("http_status") if isinstance(result, dict) else None
        field = result.get("failed_field") if isinstance(result, dict) else None
        raise RuntimeError("Research failed at " + str(step) + " (" + str(code) + (", field " + str(field) if field else "") + ", HTTP " + str(status or "unknown") + "); no automatic retry")
    markdown = result.get("report_markdown")
    if not isinstance(markdown, str) or len(markdown) < 300:
        raise RuntimeError("n8n returned no complete report")
    validation = result.get("validation") or {}
    if validation.get("source_ids_valid") is not True or validation.get("cited_claims_have_source_ids") is not True:
        raise RuntimeError("n8n report validation metadata is invalid")
    company = result.get("company") or {}
    slug = re.sub(r"[^a-z0-9]+", "-", str(company.get("name") or company_name).lower()).strip("-")[:70] or "company"
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    folder = PROJECT / "reports"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / (stamp + "-" + slug + ".md")
    path.write_text(markdown, encoding="utf-8")
    path.chmod(0o600)
    metadata = {
        "workflow_id": os.getenv("PROJECT3_WORKFLOW_ID"),
        "execution_id": result.get("n8n_execution_id"),
        "company_name": company.get("name"),
        "company_id": company.get("company_id"),
        "openai_model": result.get("model"),
        "openai_status": result.get("openai_status"),
        "openai_usage": result.get("usage"),
        "validation": result.get("validation"),
        "retrieval": result.get("retrieval"),
        "sources": [{k: s.get(k) for k in ("id", "kind", "url", "retrieved_at", "published_at")} for s in result.get("sources", [])],
    }
    metadata_path = path.with_suffix(".meta.json")
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    metadata_path.chmod(0o600)
    print("report=" + str(path.relative_to(ROOT)))
    print("metadata=" + str(metadata_path.relative_to(ROOT)))
    print("workflow_execution=" + str(result.get("n8n_execution_id", "unreported")))
    print("model=" + str(result.get("model", "unreported")))
    print("openai_status=" + str(result.get("openai_status", "unreported")))
    print("validation=passed")
    print("source_count=" + str(len(result.get("sources", []))))
    retrieval = result.get("retrieval") or {}
    print("tavily_http_status=" + str(retrieval.get("tavily_http_status", "unreported")))
    print("tavily_raw_results=" + str(retrieval.get("tavily_results", "unreported")))
    print("tavily_accepted_results=" + str(retrieval.get("tavily_accepted_count", "unreported")))
    print("rag_source_count=" + str(len(result.get("rag_context") or [])))
    usage = result.get("usage") or {}
    print("input_tokens=" + str(usage.get("input_tokens", "unreported")))
    print("output_tokens=" + str(usage.get("output_tokens", "unreported")))
    return path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("company_name")
    parser.add_argument("--register-identifier")
    args = parser.parse_args()
    run(args.company_name, args.register_identifier)
