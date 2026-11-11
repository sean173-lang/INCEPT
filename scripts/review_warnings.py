"""Stable, categorized review warnings shared by reports and corporate evidence."""
import hashlib
from typing import Literal
from scripts.service_schemas import Schema


class ReviewWarning(Schema):
    warning_id: str
    category: Literal['missing_information', 'identity_conflict', 'freshness', 'provenance', 'authority', 'provider_failure', 'unverified_evidence']
    message: str
    source_ids: list[str]


def corporate_warnings(result):
    messages=[]
    for message in result.missing_evidence:
        lower=message.lower()
        category=('provenance' if 'provenance' in lower or 'timestamp' in lower else
                  'freshness' if 'older than 30 days' in lower else
                  'provider_failure' if 'unavailable (' in lower or 'no automatic retry' in lower else
                  'unverified_evidence' if 'synthetic' in lower or 'excluded:' in lower else 'missing_information')
        messages.append((category,message))
    messages += [('identity_conflict','Identity discrepancy: '+value) for value in result.discrepancies]
    # Registry matching never proves the instructing representative's authority.
    if result.provider:
        messages.append(('authority','Register records do not establish the authority of the person instructing the firm.'))
    ids=[s.source_id for s in result.sources[:1]]
    warnings=[];seen=set()
    for category,message in messages:
        if message in seen:continue
        seen.add(message)
        identifier='corporate:'+category+':'+hashlib.sha256(message.encode()).hexdigest()[:12]
        warnings.append(ReviewWarning(warning_id=identifier,category=category,message=message,source_ids=ids))
    return warnings
