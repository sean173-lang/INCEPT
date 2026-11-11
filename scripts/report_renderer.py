"""Shared safe Markdown escaping for INCEPT reports and drafts."""
import html
import re

def text(value):
    """Keep source-provided values from creating Markdown headings or links."""
    value = html.escape(str(value if value is not None else "Not available"))
    return re.sub(r"([\\`*{}_\[\]()#!|>])", r"\\\1", " ".join(value.split()))
