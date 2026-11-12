"""Live checks against the real Knowledge Base. Skipped unless P3_KB_ID is set.

Run from assistant/ with AWS credentials configured:
    $env:P3_KB_ID = "<kb id>"; pytest tests/integration/test_kb_retrieval.py -v
"""

import os

import pytest

from support.retrieval import knowledge_base_id, retrieve

pytestmark = pytest.mark.skipif(not os.environ.get("P3_KB_ID"), reason="P3_KB_ID not set")


@pytest.fixture(scope="module")
def client():
    import boto3

    return boto3.client("bedrock-agent-runtime")


def test_q01_retrieves_current_transfer_timelines(client):
    hits = retrieve(client, knowledge_base_id(), "How long does an incoming ACATS transfer take?")
    assert hits, "no results"
    top = hits[0]
    assert (top.document.document_id, top.document.version, top.section) == ("POL-TRF", "3.2", "4")
    assert "3 to 6 business days" in top.text
    assert top.citation("4.1").as_source() == "Account Transfer Policy v3.2, s.4.1"


def test_no_superseded_results_for_superseded_questions(client):
    for question in [
        "Do I need a Medallion signature guarantee to transfer $180,000 from my bank?",
        "Will you cover the closing fee when I move $40,000 from another brokerage?",
    ]:
        hits = retrieve(client, knowledge_base_id(), question)
        assert hits and all(
            hit.document.version == "3.2" for hit in hits if hit.document.document_id == "POL-TRF"
        )
