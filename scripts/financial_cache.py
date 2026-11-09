"""Save and load OpenRegister financial API responses."""

import json
from pathlib import Path
from datetime import datetime, timezone

CACHE_DIR = Path("data/financials")


def save_financials(company_id, result):
    """Save a successful financial API response."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    filename = company_id.replace("/", "_") + ".json"
    filepath = CACHE_DIR / filename

    payload = {
        "company_id": company_id,
        "saved_at": datetime.now(timezone.utc).isoformat(),
        "result": result,
    }

    with filepath.open("w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2, ensure_ascii=False, default=str)

    return filepath


def load_financials(company_id):
    """Load a previously saved financial API response."""
    filename = company_id.replace("/", "_") + ".json"
    filepath = CACHE_DIR / filename

    if not filepath.exists():
        return None

    with filepath.open("r", encoding="utf-8") as file:
        return json.load(file)["result"]
