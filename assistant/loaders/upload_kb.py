"""Split the KB corpus into chunks and upload them, with sidecars, to S3.

Run from assistant/:
    python loaders/upload_kb.py --dry-run                 # no AWS calls; shows what would upload
    python loaders/upload_kb.py --bucket <corpus-bucket>  # or set P3_KB_BUCKET

Uses your local AWS credentials (`aws configure`). Never put the bucket name, account ID or
keys in this file. After uploading, sync the Bedrock data source so it re-indexes.
"""

import argparse
import os
import sys
from pathlib import Path

ASSISTANT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ASSISTANT / "src"))

from support.kb_metadata import split_corpus  # noqa: E402
from support.kb_upload import normalise_prefix, plan_upload, upload  # noqa: E402

CORPUS = ASSISTANT / "Project3-Corpus-Documents/p3-corpus/knowledge-base"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--bucket", default=os.environ.get("P3_KB_BUCKET"))
    parser.add_argument("--prefix", default="chunks/")
    parser.add_argument("--region", default=None, help="defaults to your AWS profile's region")
    parser.add_argument("--dry-run", action="store_true", help="plan only; make no AWS calls")
    parser.add_argument(
        "--delete-stale", action="store_true", help="delete files under the prefix not produced"
    )
    args = parser.parse_args(argv)

    chunks = split_corpus(CORPUS)
    prefix = normalise_prefix(args.prefix)
    superseded = sum(chunk.document.superseded for chunk in chunks)
    documents = len({chunk.source_file for chunk in chunks})
    print(f"{len(chunks)} chunks ({superseded} superseded) from {documents} documents")

    if args.dry_run:
        files = plan_upload(chunks, prefix)
        print(f"dry run: would upload {len(files)} files under {prefix}")
        for file in files[:4]:
            print(f"  {file.key}")
        print("  ...")
        return 0

    if not args.bucket:
        parser.error("--bucket is required (or set P3_KB_BUCKET)")

    import boto3  # only needed for a real upload

    client = boto3.client("s3", region_name=args.region)
    report = upload(client, args.bucket, prefix, chunks, delete_stale=args.delete_stale)
    print(f"uploaded {len(report.uploaded)} files under {prefix}")
    if report.stale and not report.deleted:
        print(f"{len(report.stale)} stale files under {prefix} (rerun with --delete-stale):")
        for key in report.stale:
            print(f"  {key}")
    if report.deleted:
        print(f"deleted {len(report.deleted)} stale files")
    print("next: sync the Bedrock data source so it re-indexes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
