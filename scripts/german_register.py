"""OpenRegister identity details only. Financial retrieval is retired."""
import os
from dotenv import load_dotenv
from scripts.api_usage import get_tracker, RegistryRecord
load_dotenv()
API_KEY=os.getenv("OPENREGISTER_API_KEY")

def get_client():
    from openregister import Openregister
    if not API_KEY:
        raise ValueError(
            "Missing OPENREGISTER_API_KEY in .env"
        )

    return Openregister(api_key=API_KEY, max_retries=0, timeout=30)


# ==========================================
# 1. GET COMPANY INFORMATION
# ==========================================

def get_company(company_id):
    from datetime import datetime, timezone
    from scripts.development_fixtures import german_company
    def retrieve():
        client = get_client()
        raw = client.company.get_details_v1(company_id=company_id).model_dump(mode="json")
        return {"payload": raw, "retrieved_at": datetime.now(timezone.utc).isoformat()}
    raw = get_tracker().execute("OpenRegister", "company_details", company_id, retrieve,
                                cache=True, mock=lambda: {"payload": german_company(company_id), "retrieved_at": None})
    return RegistryRecord(raw["payload"], retrieved_at=raw["retrieved_at"])
