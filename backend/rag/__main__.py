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
  python -m rag evaluate                              # 6단계 3파전 — 채점하고 승자를 고른다 (D-024)
  python -m rag evaluate --model bge-m3 -v            # 하나만 (판정은 셋이 다 있어야 한다)
  python -m rag load                                  # 7단계 documents 적재 (D-025)
  python -m rag load --dry-run                        # DB 를 안 건드리고 만들 행만 확인
  python -m rag load --model qwen3-embedding-0.6b     # 모델 교체 = 같은 명령 재실행

`search`·`generate` 서브커맨드가 8~9단계에서 같은 자리에 붙는다.
"""
from __future__ import annotations

import argparse
import collections
import sys
import traceback

from .core import config, io
from .stages import chunk as chunker
from .stages import embed, evaluate, goldenset, parse
from .stages import load as loader

# 윈도우 콘솔 기본 인코딩(cp949)으로는 한글이 깨지고 일부 기호는 예외를 낸다 (crawler CLI 와 같은 처리).
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")


def cmd_list(args: argparse.Namespace) -> int:
    for doc in io.raw_docs(args.source):
        label, reason = parse.status(doc)
        mark = {"OK": "x", "TODO": " ", "NOT-INDEXED": "-"}[label]
        print(f"[{mark}] {doc.doc_id:44s} {doc.source_id:24s} {reason}")
    print("\n  x=파서 있음   (공백)=파서 없음   -=인덱싱 대상 아님(결정)")
    return 0


def cmd_parse(args: argparse.Namespace) -> int:
    """raw → parsed. **파싱 자체는 `stages.parse` 가 하고 여기는 출력만 한다** (D-023).

    다른 단계는 전부 자기 모듈에 로직이 있는데 parse 만 CLI 안에 있었다.
    """
    docs = io.raw_docs(args.source)
    if args.limit:
        docs = docs[: args.limit]

    n_parsed = n_same = n_skipped = n_failed = 0
    total: collections.Counter[str] = collections.Counter()

    for doc in docs:
        label, reason = parse.status(doc)
        if label != "OK":
            print(f"  {label:11s} {doc.doc_id:44s} {reason}")
            n_skipped += 1
            continue
        if io.is_current(doc) and not args.force:
            n_same += 1
            if args.verbose:
                print(f"  {'same':11s} {doc.doc_id}")
            continue

        try:
            header, elements, counts = parse.parse_doc(doc)
        except Exception:
            print(f"  {'FAIL':11s} {doc.doc_id}\n{traceback.format_exc()}")
            n_failed += 1
            continue

        total += collections.Counter(counts)
        n_parsed += 1
        if args.dry_run:
            print(f"  {'(dry-run)':11s} {doc.doc_id:44s} {counts}")
        else:
            path = io.write(header, elements)
            print(f"  {'parsed':11s} {doc.doc_id:44s} {counts}")
            if args.verbose:
                print(f"              -> {path}")
        for w in header.warnings:
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

    if args.restamp:
        # D-025 ⑤ 의 일회성 대가 — 지문 *정의*가 바뀌어 기존 parquet 의 값이 옛 방식이다.
        # 벡터는 손대지 않고 메타만 갱신하되, 행이 실제로 일치할 때만 찍는다
        bad = 0
        for key in keys:
            ok, why = embed.restamp(key, fingerprint, rows)
            print(f"  {'restamped' if ok else 'REFUSED':11s} {key:22s} {why}")
            bad += not ok
        return 1 if bad else 0

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


def cmd_evaluate(args: argparse.Namespace) -> int:
    """6단계 3파전 — 채점하고 승자를 고른다 (D-024).

    **골든셋 검증을 먼저 통과해야 채점을 시작한다.** 없는 주소를 가리키는 must 는 그 문항의
    점수를 영원히 0 으로 만들고, 증상은 "이 모델이 유독 못한다" 로만 나타난다 (D-022 ⑥).
    같은 이유로 **낡은 parquet 으로는 채점하지 않는다** — 다른 코퍼스를 잰 값이기 때문이다.
    """
    gs = goldenset.load()
    index = goldenset.corpus_index()
    problems, warnings = goldenset.verify(gs, index)
    if problems:
        print(f"골든셋 라벨 {len(problems)}개가 실재하지 않는 청크를 가리킨다 — "
              "`python -m rag goldenset` 으로 먼저 고칠 것")
        return 1
    for w in warnings:
        print(f"  경고: {w}")

    keys = [args.model] if args.model else list(embed.MODELS)
    unknown = [k for k in keys if k not in embed.MODELS]
    if unknown:
        print(f"모르는 모델: {unknown}   가능: {list(embed.MODELS)}")
        return 1

    fingerprint = embed.chunks_fingerprint()
    print(f"골든셋 {len(gs.items)}문항 / 필수 {gs.must_total}  ·  코퍼스 {len(index)}청크  ·  "
          f"chunks_sha256 {fingerprint[:16]}")
    print(f"판정 k={evaluate.JUDGE_K}  ·  탈락선 Hit@{evaluate.JUDGE_K} {evaluate.CUT_GAP}문항 차  ·  "
          f"동률이면 사전 순위 {list(evaluate.PREFERENCE)} (D-024 ①③)")

    summaries: dict[str, dict] = {}
    for key in keys:
        if not embed.is_current(key, fingerprint) and not args.force:
            print(f"  {'STALE':11s} {key} — parquet 이 지금 청크와 다른 코퍼스를 잰 것이다. "
                  "`python -m rag embed` 먼저 (또는 --force)")
            return 1
        print(f"  {'scoring':11s} {key} …", flush=True)
        res = evaluate.score_model(key, gs, index)
        if res is None:
            print(f"  {'MISSING':11s} {key}.parquet 이 없다 — `python -m rag embed` 먼저")
            return 1
        items, summary = res
        summaries[key] = summary
        if not args.dry_run:
            path = evaluate.write_dump(key, items, gs, fingerprint)
            print(f"  {'dumped':11s} {key:22s} -> {path.name}  (미추적, D-024 ④)")
        if args.verbose:
            k = evaluate.JUDGE_K
            for it in items:
                ranks = ", ".join(str(m["rank"]) for m in it.must)
                print(f"      [{it.item_id:4s}] hit@{k}={int(it.hit[k])} "
                      f"recall@{k}={it.recall[k]:.2f}  필수 순위 [{ranks}]  {it.question}")

    if len(summaries) < len(embed.MODELS):
        print("\n(모델 3종이 다 있어야 판정한다 — 지금은 점수만 냈다)")
        return 0

    verdict = evaluate.judge({k: s["hit_count"] for k, s in summaries.items()})
    print()
    print(evaluate.markdown(summaries, verdict, gs, fingerprint, len(index)))
    print()
    print("  ^ 위 markdown 을 docs/decisions.md 의 D-024 에 `### 판정 결과` 로 붙인다 (D-024 ④).")
    print("    덤프는 미추적이라 이것이 뒤에 남는 전부다.")
    return 0


def cmd_load(args: argparse.Namespace) -> int:
    """chunks + embeddings → documents (D-008, D-025).

    **행을 먼저 다 만들고 나서 DB 를 연다.** 벡터 정렬이나 중복 처리에서 실패할 것이면
    연결하기 전에 실패하는 편이 싸고, `--dry-run` 이 같은 경로를 그대로 탄다.
    """
    key = args.model or config.settings.embedding_model_key
    if key not in embed.MODELS:
        print(f"모르는 모델: {key}   가능: {list(embed.MODELS)}")
        return 1

    try:
        prepared = loader.prepare(key)
    except (FileNotFoundError, ValueError) as exc:
        print(f"  {'FAIL':11s} {exc}")
        return 1

    print(f"모델 {key} ({prepared.model_repo})")
    print(f"청크 {len(prepared.rows) + prepared.merged}건 → 행 {len(prepared.rows)}개"
          f"  (content 중복 {prepared.merged}건 합침 — metadata.merged_from 에 남는다)")
    if key != "qwen3-embedding-0.6b":
        # 판정 승자가 아닌 것으로 적재하는 것은 결정이지 사고가 아니다. 다만 조용하면 안 된다
        print("  * 판정 승자는 qwen3-embedding-0.6b 다 — 첫 관통을 기준선으로 가는 중"
              " (D-024 `판정 이후`)")

    if args.dry_run:
        for row in prepared.rows[:args.show]:
            print(f"    {row['metadata']['chunk_id']:60s} {row['content_hash'][:12]} "
                  f"{row['category']}/{row['subcategory']}")
        merged = [r for r in prepared.rows if r["metadata"]["merged_from"]]
        for row in merged:
            print(f"    합침: {row['metadata']['chunk_id']}"
                  f"  <- {row['metadata']['merged_from']}")
        print("\n(dry-run: DB 를 열지 않았다)")
        return 0

    with loader.connect() as conn:
        before = loader.existing_models(conn)
        for name, n in before:
            mark = "  " if name == prepared.model_repo else "! "
            print(f"  {mark}기존 {n:5d}행  {name}")
        if any(name not in (prepared.model_repo, "(없음)") for name, _ in before):
            print("  ! 다른 모델의 행이 있다 — upsert 가 같은 content_hash 를 덮어쓴다 (D-025 ①)")

        loader.upsert(conn, prepared.rows)
        total = loader.count(conn)
        print(f"  {'upserted':11s} {len(prepared.rows)}행  ·  documents 총 {total}행")
        for name, n in loader.existing_models(conn):
            print(f"    {n:5d}행  {name}")

    print("\n인덱스는 적재 후에 수동으로 만든다 (db/indexes.sql):")
    print("  docker compose exec -T db psql -U $POSTGRES_USER -d $POSTGRES_DB < db/indexes.sql")
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
    emb.add_argument("--restamp", action="store_true",
                     help="벡터는 두고 지문만 다시 찍는다 (D-025 ⑤ 일회성. 행이 일치할 때만)")
    emb.set_defaults(fn=cmd_embed)

    gld = sub.add_parser("goldenset", help="골든셋 라벨이 실재하는 청크인지 검사 (D-022)")
    gld.add_argument("-v", "--verbose", action="store_true", help="문항별 라벨을 전부 출력")
    gld.set_defaults(fn=cmd_goldenset)

    ev = sub.add_parser("evaluate", help="6단계 3파전 — 채점하고 승자를 고른다 (D-024)")
    ev.add_argument("--model", help=f"하나만: {list(embed.MODELS)} (판정은 셋이 다 있어야 한다)")
    ev.add_argument("--force", action="store_true",
                    help="parquet 이 지금 청크와 어긋나도 채점한다")
    ev.add_argument("--dry-run", action="store_true", help="덤프를 쓰지 않는다")
    ev.add_argument("-v", "--verbose", action="store_true", help="문항별 결과를 전부 출력")
    ev.set_defaults(fn=cmd_evaluate)

    ld = sub.add_parser("load", help="7단계 — chunks+embeddings → documents (D-025)")
    ld.add_argument("--model", help=f"기본 {list(embed.MODELS)[0]} (D-024 판정 이후). 교체는 이 인자 하나")
    ld.add_argument("--dry-run", action="store_true", help="DB 를 열지 않고 만들 행만 확인")
    ld.add_argument("--show", type=int, default=5, help="dry-run 에서 보여 줄 행 수")
    ld.set_defaults(fn=cmd_load)

    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
