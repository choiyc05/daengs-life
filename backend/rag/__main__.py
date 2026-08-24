"""CLI.

  python -m rag list                                  # 원본 목록 + 파서 구현 여부
  python -m rag parse                                 # 바뀐 것만 파싱
  python -m rag parse --source law-drf-api -v
  python -m rag parse --force                         # 원본이 그대로여도 다시
  python -m rag chunk                                 # parsed → chunks (바뀐 것만)
  python -m rag chunk --source easylaw-pet -v
  python -m rag show <chunk_id 조각>                  # 검문소①용 — 청크를 눈으로 본다
  python -m rag goldenset                             # 골든셋 라벨이 실재하는지 검사 (D-022)
  python -m rag goldenset -v                          # 문항별 라벨까지 전부

`embed`·`load`·`search` 서브커맨드가 4~8단계에서 같은 자리에 붙는다.
"""
from __future__ import annotations

import argparse
import collections
import sys
import traceback

from . import chunk as chunker
from . import config, embed, goldenset, io, registry
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


def cmd_chunk(args: argparse.Namespace) -> int:
    """parsed → chunks. 스킵 판단·집계 모양을 `parse` 와 같게 둔다."""
    paths = io.parsed_files()
    n_written = n_same = n_failed = 0
    total: collections.Counter[str] = collections.Counter()
    dropped: collections.Counter[str] = collections.Counter()
    warnings: list[str] = []
    seen: dict[str, str] = {}          # content_hash → 먼저 본 chunk_id
    dups: list[tuple[str, str]] = []

    for path in paths:
        head = io.read_header(path)
        if args.source and (head or {}).get("source_id") != args.source:
            continue
        if io.is_chunk_current(path) and not args.force:
            n_same += 1
            if args.verbose:
                print(f"  {'same':11s} {path.stem}")
            continue
        try:
            header, res = chunker.chunk_file(path)
        except Exception:
            print(f"  {'FAIL':11s} {path.stem}\n{traceback.format_exc()}")
            n_failed += 1
            continue

        total.update(c.element_type for c in res.chunks)
        dropped.update(res.dropped)
        warnings += res.warnings
        for c in res.chunks:
            h = chunker.content_hash(c.content)
            if h in seen:
                dups.append((seen[h], c.chunk_id))
            else:
                seen[h] = c.chunk_id

        n_written += 1
        if args.dry_run:
            print(f"  {'(dry-run)':11s} {path.stem:44s} 청크 {len(res.chunks):4d}")
        else:
            out = io.write_chunks(header, res.chunks)
            print(f"  {'chunked':11s} {path.stem:44s} 청크 {len(res.chunks):4d}")
            if args.verbose:
                print(f"              -> {out}")

    print(f"\n청크 합계: {dict(sorted(total.items()))}  총 {sum(total.values())}")
    if dropped:
        # 무엇을 왜 뺐는지 항상 보여 준다. 조용한 소실이 이 프로젝트에서 두 번 문제가 됐다 (D-021 ①·⑤D)
        print(f"제외:      {dict(dropped)}")
    for w in warnings:
        print(f"  ! {w}")
    if dups:
        # 합쳐지는 것 자체는 옳다(내용이 같다). 조용한 것이 문제다 — 7단계 적재기가 content_hash 로
        # 합칠 행을 미리 드러낸다 (D-021 ⑤D)
        print(f"  ! content 중복 {len(dups)}건 — 적재 시 content_hash 로 합쳐진다")
        for first, later in dups:
            print(f"      {later}  ==  {first}")
    print(f"chunked {n_written}, same {n_same}, failed {n_failed}"
          + ("   (dry-run: 아무것도 쓰지 않음)" if args.dry_run else ""))
    return 1 if n_failed else 0


def cmd_embed(args: argparse.Namespace) -> int:
    """chunks → embeddings/{key}.parquet. 모델 3종을 나란히 만든다 (D-002).

    **가드를 먼저 전부 돌린다.** 토크나이저는 가볍고 가중치 로드는 무거우니, 실패할 것이면
    6.5GB 를 올리기 전에 실패하는 편이 싸다.
    """
    rows = embed.load_chunks()
    if not rows:
        print("chunks 가 비었다 — `python -m rag chunk` 먼저")
        return 1
    keys = [args.model] if args.model else list(embed.MODELS)
    unknown = [k for k in keys if k not in embed.MODELS]
    if unknown:
        print(f"모르는 모델: {unknown}   가능: {list(embed.MODELS)}")
        return 1

    fingerprint = embed.chunks_fingerprint()
    texts = [r["content"] for r in rows]
    print(f"청크 {len(rows)}건  chunks_sha256 {fingerprint[:16]}")

    todo: list[tuple[str, dict[str, int]]] = []
    for key in keys:
        model = embed.MODELS[key]
        if embed.is_current(key, fingerprint) and not args.force:
            print(f"  {'same':11s} {key}")
            continue
        try:
            stats = embed.guard(model, texts)
        except Exception as exc:
            print(f"  {'GUARD FAIL':11s} {key}\n      {exc}")
            return 1
        pct = stats["max"] / model.max_tokens * 100
        print(f"  {'guard ok':11s} {key:22s} 최대 {stats['max']:5d} / 한계 {model.max_tokens} "
              f"({pct:.0f}%)  중앙 {stats['median']}  p95 {stats['p95']}")
        todo.append((key, stats))

    if args.guard_only:
        print("\n(guard-only: 인코딩하지 않음)")
        return 0

    for key, stats in todo:
        model = embed.MODELS[key]
        print(f"  {'encoding':11s} {key} ({model.repo}) …", flush=True)
        st = embed.load_model(model)
        try:
            vectors = embed.encode_docs(model, texts, batch_size=args.batch,
                                        st=st, progress=not args.quiet)
        finally:
            # **모델마다 GPU 에서 내린다.** PyTorch 는 파이썬 객체가 사라져도 empty_cache 전까지
            # VRAM 을 붙들고 있어, 3종을 한 프로세스에서 돌리면 누적된다. 6GB GPU 에서 마지막
            # 모델이 남은 공간에 끼여 10배 넘게 느려지는 것을 실측으로 겪었다
            del st
            embed.release()
        if args.dry_run:
            print(f"  {'(dry-run)':11s} {key:22s} {vectors.shape}")
            continue
        path = embed.write_parquet(model, rows, vectors,
                                   fingerprint=fingerprint, token_stats=stats)
        size = path.stat().st_size / 1e6
        print(f"  {'written':11s} {key:22s} {vectors.shape}  {size:.1f} MB  "
              f"VRAM {embed.vram_used_mb():.0f} MB  -> {path.name}", flush=True)
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    """검문소① 용. chunk_id 조각으로 찾아 청크 본문을 그대로 출력한다."""
    hit = 0
    for path in sorted(config.CHUNK_DIR.glob("*.jsonl")):
        for row in io.read_chunks(path):
            if args.pattern not in row["chunk_id"]:
                continue
            hit += 1
            print(f"--- {row['chunk_id']}  ({row['chars']}자)")
            print(f"    citation: {row.get('citation')}   section: {row.get('section')}")
            if row.get("part"):
                print(f"    part: {row['part']}")
            print(row["content"] if args.full else row["content"][:600])
            print()
            if hit >= args.limit:
                print(f"(상한 {args.limit}건에서 멈춤)")
                return 0
    if not hit:
        print("일치하는 청크가 없다")
        return 1
    return 0


def cmd_goldenset(args: argparse.Namespace) -> int:
    """골든셋 라벨이 실제 청크를 가리키는지 검사한다 (D-022 ⑥).

    없는 주소를 가리키는 must 는 그 문항의 Recall 을 영원히 0 으로 만들고, 증상은 6단계에서
    "이 모델이 유독 못한다" 로만 나타난다. 채점 전에 여기서 먼저 깨뜨린다.
    """
    gs = goldenset.load()
    index = goldenset.corpus_index()
    problems, warnings = goldenset.verify(gs, index)

    origin = collections.Counter(i.origin for i in gs.items)
    print(f"골든셋 {len(gs.items)}문항 (hand {origin['hand']} · easylaw {origin['easylaw']})  "
          f"필수 {gs.must_total}  보강 {sum(len(i.nice) for i in gs.items)}  "
          f"분모 제외 {sum(len(i.unavailable) for i in gs.items)}")
    print(f"코퍼스 {len(index)}청크  ·  라벨 기준 {gs.corpus.collected_on}")

    if args.verbose:
        for item in gs.items:
            print(f"\n  [{item.id}] ({item.origin}) {item.question}")
            for tier, addrs in (("must", item.must), ("nice", item.nice)):
                for a in addrs:
                    print(f"    {tier:4s} {'OK  ' if a in index else '없음 '}{a}")
            for u in item.unavailable:
                print(f"    ----      {u.ref}  ({u.reason})")

    for w in warnings:
        print(f"\n  경고: {w}")
    if problems:
        print(f"\n  라벨 {len(problems)}개가 실재하지 않는 청크를 가리킨다:")
        for p in problems:
            print(f"    {p.item_id:4s} {p.tier:4s} {p.address}")
        return 1
    print("\n  라벨 전부 실재한다")
    return 0


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

    chk = sub.add_parser("chunk", help="processed/parsed → processed/chunks")
    chk.add_argument("--source", help="parsed 헤더의 source_id 로 거르기")
    chk.add_argument("--force", action="store_true", help="parsed 가 그대로여도 다시 청킹")
    chk.add_argument("--dry-run", action="store_true", help="아무것도 쓰지 않고 결과만 출력")
    chk.add_argument("-v", "--verbose", action="store_true")
    chk.set_defaults(fn=cmd_chunk)

    shw = sub.add_parser("show", help="청크를 눈으로 본다 (검문소①)")
    shw.add_argument("pattern", help="chunk_id 의 일부")
    shw.add_argument("--limit", type=int, default=5)
    shw.add_argument("--full", action="store_true", help="본문을 자르지 않고 전부")
    shw.set_defaults(fn=cmd_show)

    emb = sub.add_parser("embed", help="processed/chunks → processed/embeddings (모델 3종)")
    emb.add_argument("--model", help=f"하나만: {list(embed.MODELS)}")
    emb.add_argument("--batch", type=int, default=8)
    emb.add_argument("--force", action="store_true", help="청크가 그대로여도 다시")
    emb.add_argument("--guard-only", action="store_true",
                     help="토큰 가드만 돌리고 인코딩은 하지 않는다 (가중치 로드 없음)")
    emb.add_argument("--dry-run", action="store_true", help="인코딩은 하고 쓰지는 않는다")
    emb.add_argument("--quiet", action="store_true", help="진행 막대를 끈다")
    emb.set_defaults(fn=cmd_embed)

    gld = sub.add_parser("goldenset", help="골든셋 라벨이 실재하는 청크인지 검사 (D-022)")
    gld.add_argument("-v", "--verbose", action="store_true", help="문항별 라벨을 전부 출력")
    gld.set_defaults(fn=cmd_goldenset)

    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
