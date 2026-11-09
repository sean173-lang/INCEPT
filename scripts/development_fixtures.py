"""Synthetic examples for safe development. These are not real company data."""

def german_company(company_id):
    return {'id': company_id, 'name': {'name': 'LEGALFLOW DEMO GmbH'}, 'status': 'active',
            'incorporated_at': '2020-01-01', 'company_register': {'register_number': 'DEMO-1', 'register_court': 'Synthetic court'}}


def uk_response(endpoint, params=None):
    if endpoint == '/search/companies':
        return {'items': [{'title': 'LEGALFLOW DEMO LTD', 'company_number': '00000000'}]}
    if endpoint.endswith('/officers') or endpoint.endswith('/filing-history'):
        return {'items': []}
    return {'company_name': 'LEGALFLOW DEMO LTD', 'company_number': '00000000',
            'company_status': 'active', 'date_of_creation': '2020-01-01'}


def financials(company_id):
    return {'provider': 'OpenRegister', 'company_id': company_id, 'status': 'unavailable',
            'request_status': 'succeeded', 'financial_data_status': 'no_figures_returned',
            'publication_status': 'unknown', 'raw': {'reports': [], 'indicators': []},
            'reason': 'Synthetic development fixture: no financial figures supplied.'}
