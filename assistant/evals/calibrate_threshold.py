"""Run the calibration questions against the live KB and write the threshold evidence.

Run from assistant/ with AWS credentials configured:
    $env:P3_KB_ID = "<kb id>"; python evals/calibrate_threshold.py

Writes docs/results/threshold-calibration-YYYYMMDD.md. It recommends a threshold;
copying it into the Support agent's code is a separate, reviewed change.
"""

import json
import sys
from datetime import date
from pathlib import Path

ASSISTANT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ASSISTANT / "src"))

from support.calibration import (  # noqa: E402
    ANSWERABLE,
    GAP,
    choose_threshold,
    render_markdown,
    score_question,
)
from support.retrieval import knowledge_base_id, retrieve  # noqa: E402

SUPPORT_QA = ASSISTANT / "Project3-Corpus-Documents/p3-corpus/ground-truth/support_qa.jsonl"
GAP_QUESTIONS = ASSISTANT / "evals/gap_questions.jsonl"
RESULTS = ASSISTANT / "docs/results"


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def main() -> int:
    import boto3

    client = boto3.client("bedrock-agent-runtime")
    kb_id = knowledge_base_id()

    rows = []
    for item in load_jsonl(SUPPORT_QA):
        kind = GAP if item["case"] == "gap" else ANSWERABLE
        hits = retrieve(client, kb_id, item["question"])
        rows.append(
            score_question(
                id=item["id"],
                question=item["question"],
                kind=kind,
                case=item["case"],
                hits=hits,
                sources=item["sources"],
            )
        )
        print(f"{item['id']}: {rows[-1].top_score:.4f}")
    for item in load_jsonl(GAP_QUESTIONS):
        hits = retrieve(client, kb_id, item["question"])
        rows.append(
            score_question(
                id=item["id"], question=item["question"], kind=GAP, case=item["kind"], hits=hits
            )
        )
        print(f"{item['id']}: {rows[-1].top_score:.4f}")

    threshold = choose_threshold(rows)
    stamp = date.today().strftime("%Y%m%d")
    RESULTS.mkdir(parents=True, exist_ok=True)
    md = RESULTS / f"threshold-calibration-{stamp}.md"
    md.write_text(render_markdown(rows, threshold, run=date.today().isoformat()), encoding="utf-8")

    print(f"\nthreshold {threshold.value:.3f} (separated: {threshold.separated})")
    if threshold.answerable_below:
        print(f"answerable below threshold: {', '.join(threshold.answerable_below)}")
    print(f"evidence: {md.relative_to(ASSISTANT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
