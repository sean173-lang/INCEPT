import os
import json
from dotenv import load_dotenv
from openregister import Openregister

# ==========================================
# LEGALFLOW — German Company Register
# ==========================================

load_dotenv()

API_KEY = os.getenv("OPENREGISTER_API_KEY")


def get_client():
    if not API_KEY:
        raise ValueError(
            "Missing OPENREGISTER_API_KEY in .env"
        )

    return Openregister(api_key=API_KEY)


# ==========================================
# 1. GET COMPANY INFORMATION
# ==========================================

def get_company(company_id):
    client = get_client()
    return client.company.get_details_v1(company_id=company_id)


# ==========================================
# 2. DISPLAY COMPANY INFORMATION
# ==========================================

def display_company(company):

    print("\n" + "=" * 55)
    print("LEGALFLOW — GERMAN COMPANY REPORT")
    print("=" * 55)

    print("\nCOMPANY INFORMATION")
    print("-" * 55)

    for field in [
        "name",
        "id",
        "legal_form",
        "status",
        "address",
        "registration",
        "management"
    ]:
        value = getattr(company, field, None)

        if value is not None:
            print(f"{field}: {value}")

    print("\nFULL API RESPONSE")
    print("-" * 55)

    if hasattr(company, "model_dump"):
        data = company.model_dump(mode="json")
    else:
        data = vars(company)

    print(json.dumps(data, indent=2, ensure_ascii=False, default=str))

    print("\n" + "=" * 55)


# ==========================================
# 3. MAIN APPLICATION
# ==========================================

def main():

    print("\nWelcome to LEGALFLOW")
    print("German Corporate Due Diligence")
    print("----------------------------------")

    company_id = input(
        "\nEnter OpenRegister company ID: "
    ).strip()

    if not company_id:
        print("Please enter a company ID.")
        return

    print("\nRetrieving German company data...")

    company = get_company(company_id)

    display_company(company)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"\nOpenRegister error: {error}")