"""CLI.

  python -m rag list                                  # 원본 목록 + 파서 구현 여부
  python -m rag parse                                 # 바뀐 것만 파싱
  python -m rag parse --source law-drf-api -v
  python -m rag parse --force                         # 원본이 그대로여도 다시

`chunk`·`embed`·`load`·`search` 서브커맨드가 3~8단계에서 같은 자리에 붙는다.
"""
from __future__ import annotations

import argparse
import collections
import sys
import traceback

from . import io, registry
from .ir import Document

# 윈도우 콘솔 기본 인코딩(cp949)으로는 한글이 깨지고 일부 기호는 예외를 낸다 (crawler CLI 와 같은 처리).
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")


def _status(doc: io.RawDoc) -> tuple[str, str]:
    """(라벨, 사유). '인덱싱 안 함'(결정)과 '파서 없음'(할 일)을 섞지 않는다 — D-018."""
    if doc.source_id in registry.NOT_INDEXED:
        return "NOT-INDEXED", registry.NOT_INDEXED[doc.source_id]
    if registry.resolve(doc.domain, doc.source_id) is None:
        return "TODO", f"파서 없음: {registry.module_name(doc.domain, doc.source_id)}.py"
    return "OK", ""


def cmd_list(args: argparse.Namespace) -> int:
    for doc in io.raw_docs(args.source):
        label, reason = _status(doc)
        mark = {"OK": "x", "TODO": " ", "NOT-INDEXED": "-"}[label]
        print(f"[{mark}] {doc.doc_id:44s} {doc.source_id:24s} {reason}")
    print("\n  x=파서 있음   (공백)=파서 없음   -=인덱싱 대상 아님(결정)")
    return 0


def cmd_parse(args: argparse.Namespace) -> int:
    docs = io.raw_docs(args.source)
    if args.limit:
        docs = docs[: args.limit]

    n_parsed = n_same = n_skipped = n_failed = 0
    total: collections.Counter[str] = collections.Counter()

    for doc in docs:
        label, reason = _status(doc)
        if label != "OK":
            print(f"  {label:11s} {doc.doc_id:44s} {reason}")
            n_skipped += 1
            continue
        if io.is_current(doc) and not args.force:
            n_same += 1
            if args.verbose:
                print(f"  {'same':11s} {doc.doc_id}")
            continue

        mod = registry.resolve(doc.domain, doc.source_id)
        try:
            parsed = mod.parse(doc.path.read_bytes(), doc)
        except Exception:
            print(f"  {'FAIL':11s} {doc.doc_id}\n{traceback.format_exc()}")
            n_failed += 1
            continue

        counts = collections.Counter(e.type for e in parsed.elements)
        total += counts
        meta = doc.meta
        header = Document(
            doc_id=doc.doc_id,
            source_id=doc.source_id,
            domain=doc.domain,
            category=meta["category"],
            subcategory=meta.get("subcategory") or "",
            trust_level=meta.get("trust_level") or "",
            source_type=meta.get("source_type") or "",
            format=meta.get("format") or "",
            license=meta.get("license") or "",
            document_title=parsed.document_title or meta.get("document_title") or "",
            published_at=parsed.published_at or meta.get("published_at"),
            source_url=meta.get("source_url"),
            # 파서가 풀어 준 값이 없으면 원본을 받은 곳을 그대로 쓴다 (easylaw 처럼 둘이 같은 경우)
            citation_url=parsed.citation_url or meta.get("source_url"),
            raw_file=meta["raw_file"],
            raw_sha256=meta["sha256"],
            parser=mod.NAME,
            parser_version=mod.VERSION,
            parsed_at=io.now_kst(),
            counts={**counts, **parsed.counts},
            warnings=parsed.warnings,
            extra=parsed.extra,
        )
        n_parsed += 1
        if args.dry_run:
            print(f"  {'(dry-run)':11s} {doc.doc_id:44s} {dict(counts)}")
        else:
            path = io.write(header, parsed.elements)
            print(f"  {'parsed':11s} {doc.doc_id:44s} {dict(counts)}")
            if args.verbose:
                print(f"              -> {path}")
        for w in parsed.warnings:
            print(f"              ! {w}")

    print(f"\n요소 합계: {dict(sorted(total.items()))}")
    print(f"parsed {n_parsed}, same {n_same}, skipped {n_skipped}, failed {n_failed}"
          + ("   (dry-run: 아무것도 쓰지 않음)" if args.dry_run else ""))
    return 1 if n_failed else 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m rag")
    sub = p.add_subparsers(dest="cmd", required=True)

    lst = sub.add_parser("list", help="원본 목록과 파서 구현 여부")
    lst.add_argument("--source", help="meta 의 source_id 로 거르기")
    lst.set_defaults(fn=cmd_list)

    par = sub.add_parser("parse", help="raw/ → processed/parsed/")
    par.add_argument("--source", help="meta 의 source_id 로 거르기")
    par.add_argument("--limit", type=int, default=0, help="앞에서 N개만")
    par.add_argument("--force", action="store_true", help="원본이 그대로여도 다시 파싱")
    par.add_argument("--dry-run", action="store_true", help="아무것도 쓰지 않고 결과만 출력")
    par.add_argument("-v", "--verbose", action="store_true")
    par.set_defaults(fn=cmd_parse)

    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
