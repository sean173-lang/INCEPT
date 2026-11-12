"""Create/update and activate the single Project 3 n8n workflow.

Credentials are loaded from the ignored repository .env and created as n8n
credential records. Values never enter the exported workflow JSON or stdout.
"""
from __future__ import annotations

import os
import secrets
import stat
from pathlib import Path

import requests
from dotenv import dotenv_values, load_dotenv

from build_workflow import build, write_sanitized

ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = ROOT / ".env"
NAMES = {
    "webhook": "Ironhack Project 3 Webhook Auth",
    "openregister": "Ironhack Project 3 OpenRegister",
    "tavily": "Ironhack Project 3 Tavily",
    "openai": "Ironhack Project 3 OpenAI",
}


def set_env(values: dict[str, str]) -> None:
    old = ENV_FILE.read_text(encoding="utf-8") if ENV_FILE.exists() else ""
    lines = old.splitlines()
    for key, value in values.items():
        prefix = key + "="
        lines = [line for line in lines if not line.startswith(prefix)]
        lines.append(prefix + value)
    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    ENV_FILE.chmod(stat.S_IRUSR | stat.S_IWUSR)


def main() -> None:
    load_dotenv(ENV_FILE, override=True)
    base = (os.getenv("N8N_BASE_URL") or "http://127.0.0.1:5678").rstrip("/")
    api_key = os.getenv("N8N_API_KEY")
    if not api_key:
        raise SystemExit("N8N_API_KEY is required in ignored .env")
    provider_keys = {k: os.getenv(v) for k, v in {
        "openregister": "OPENREGISTER_API_KEY", "tavily": "TAVILY_API_KEY", "openai": "OPENAI_API_KEY"}.items()}
    missing = [k for k, v in provider_keys.items() if not v]
    if missing:
        raise SystemExit("Missing configured provider key(s): " + ", ".join(missing))
    session = requests.Session()
    session.trust_env = False
    headers = {"X-N8N-API-KEY": api_key}

    def request(method, path, **kwargs):
        response = session.request(method, base + "/api/v1" + path, headers=headers,
                                   timeout=20, allow_redirects=False, **kwargs)
        if not response.ok:
            raise RuntimeError("n8n API returned HTTP " + str(response.status_code) + " for " + path)
        return response.json() if response.content else {}

    credential_rows = request("GET", "/credentials", params={"limit": 250}).get("data", [])
    existing = {row.get("name"): row for row in credential_rows}
    webhook_secret = os.getenv("PROJECT3_WEBHOOK_TOKEN") or secrets.token_urlsafe(32)
    pending = {"PROJECT3_WEBHOOK_TOKEN": webhook_secret}
    credential_ids = {}
    specifications = {
        "webhook": ("httpHeaderAuth", {"name": "X-Project3-Token", "value": webhook_secret}),
        "openregister": ("httpHeaderAuth", {"name": "Authorization", "value": "Bearer " + provider_keys["openregister"], "allowedHttpRequestDomains": "domains", "allowedDomains": "api.openregister.de"}),
        "tavily": ("httpHeaderAuth", {"name": "Authorization", "value": "Bearer " + provider_keys["tavily"], "allowedHttpRequestDomains": "domains", "allowedDomains": "api.tavily.com"}),
        "openai": ("httpHeaderAuth", {"name": "Authorization", "value": "Bearer " + provider_keys["openai"], "allowedHttpRequestDomains": "domains", "allowedDomains": "api.openai.com"}),
    }
    for key, (credential_type, data) in specifications.items():
        name = NAMES[key]
        row = existing.get(name)
        if row:
            credential_ids[key] = {"id": row["id"], "name": name}
        else:
            created = request("POST", "/credentials", json={"name": name, "type": credential_type, "data": data})
            credential_ids[key] = {"id": created["id"], "name": name}
    set_env(pending)

    workflow = build(credential_ids)
    workflow_rows = request("GET", "/workflows", params={"limit": 250}).get("data", [])
    matches = [row for row in workflow_rows if row.get("name") == "INCEPT — Company Research Agent"]
    if len(matches) > 1:
        raise RuntimeError("Multiple Project 3 workflow copies exist; refusing to choose one")
    if matches:
        wid = matches[0]["id"]
        request("PUT", "/workflows/" + wid, json=workflow)
    else:
        created = request("POST", "/workflows", json=workflow)
        wid = created["id"]
    current = request("GET", "/workflows/" + wid)
    if not current.get("active"):
        request("POST", "/workflows/" + wid + "/activate")
    verified = request("GET", "/workflows/" + wid)
    if not verified.get("active") or verified.get("name") != "INCEPT — Company Research Agent":
        raise RuntimeError("Workflow activation verification failed")
    set_env({"PROJECT3_WORKFLOW_ID": wid})
    write_sanitized()
    print("workflow_id=" + wid)
    print("workflow_name=INCEPT — Company Research Agent")
    print("workflow_active=true")
    print("webhook_path=ironhack-company-research")
    print("credential_values_exported=false")


if __name__ == "__main__":
    main()
