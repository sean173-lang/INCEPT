"""Isolate tracker state and existing disk caches for every offline test."""
import tempfile
import unittest
import os
from unittest.mock import patch
from scripts.api_usage import UsageTracker, use_tracker


class OfflineTestCase(unittest.TestCase):
    def run(self, result=None):
        with tempfile.TemporaryDirectory() as directory:
            # Existing fixtures explicitly mock provider calls. Authorize only
            # inside this isolated runtime; no disk data or state crosses tests.
            tracker = UsageTracker(approved=True, max_openregister_credits=1000, max_tavily_searches=100)
            with use_tracker(tracker), patch.dict(os.environ, {
                'OPENAI_API_KEY': '', 'INCEPT_AI_LIVE_ENABLED': '0',
                'INCEPT_EXTRACTION_LIVE_ENABLED': '0',
            }), patch('socket.socket.connect', side_effect=AssertionError('Live network disabled in offline tests')):
                return super().run(result)
