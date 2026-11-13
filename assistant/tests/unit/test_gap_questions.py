import json
from pathlib import Path

import pytest

ASSISTANT = Path(__file__).resolve().parents[2]
GAP_QUESTIONS = ASSISTANT / "evals/gap_questions.jsonl"
KB_DIR = ASSISTANT / "Project3-Corpus-Documents/p3-corpus/knowledge-base"
SUPPORT_QA = ASSISTANT / "Project3-Corpus-Documents/p3-corpus/ground-truth/support_qa.jsonl"

ROWS = [json.loads(line) for line in GAP_QUESTIONS.read_text(encoding="utf-8").splitlines()]
CORPUS = "\n".join(path.read_text(encoding="utf-8") for path in KB_DIR.glob("*.md")).lower()


def test_twelve_questions_with_unique_ids():
    assert [row["id"] for row in ROWS] == [f"G{n:02d}" for n in range(1, 13)]


def test_kinds():
    kinds = [row["kind"] for row in ROWS]
    assert kinds.count("off_topic") == 4
    assert kinds.count("near_miss") == 8


def test_rows_are_complete():
    for row in ROWS:
        assert set(row) == {"id", "question", "kind", "absent_terms", "note"}
        assert row["question"].strip() and row["note"].strip() and row["absent_terms"]


def test_no_overlap_with_ground_truth_questions():
    ground_truth = {
        json.loads(line)["question"].lower()
        for line in SUPPORT_QA.read_text(encoding="utf-8").splitlines()
    }
    assert not {row["question"].lower() for row in ROWS} & ground_truth


@pytest.mark.parametrize("row", ROWS, ids=[row["id"] for row in ROWS])
def test_answer_terms_absent_from_corpus(row):
    # If a corpus update ever covers one of these, this fails and the question must be revisited.
    for term in row["absent_terms"]:
        assert term.lower() not in CORPUS, f"{row['id']}: corpus now mentions {term!r}"
