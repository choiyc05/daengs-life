"""CLI.

  python -m realtime config          # 키·경로가 실제로 읽히는지

`geo`·`walk` 서브커맨드가 3·7단계에서 같은 자리에 붙는다 (RT-001 구현 계획).
crawler·rag 와 같은 방식이다 — FastAPI 없이 단독으로 돈다 (D-001 원칙 1).
"""
from __future__ import annotations

import argparse
import sys

from . import config

# 윈도우 콘솔 기본 인코딩(cp949)으로는 한글이 깨지고 일부 기호는 예외를 낸다 (crawler·rag CLI 와 같은 처리).
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")


def cmd_config(args: argparse.Namespace) -> int:
    """키가 읽혔는지만 보여준다. **값은 절대 찍지 않는다** — 터미널이 곧 로그다 (D-012)."""
    print("키")
    for name, value in config.KEYS.items():
        raw = getattr(config.settings, name.lower()).strip()
        if not value:
            print(f"  [ ] {name:16s} 없음 — 발급처는 docs/data-sources.md §9")
            continue
        # 정규화가 실제로 걸렸는지가 이 명령의 존재 이유다. Encoding 키를 넣어 두고
        # "왜 403 이지"로 한나절을 쓰는 것이 §6.1 함정 1 이 실제로 일으킨 일이다.
        note = f"Encoding 키 → 디코딩함 ({len(raw)}자 → {len(value)}자)" if raw != value else "그대로"
        print(f"  [x] {name:16s} {len(value)}자, {note}")

    print("\n경로")
    print(f"  DATA_DIR       {config.DATA_DIR or '못 찾음 — DAENGS_DATA_DIR 로 알려줄 것'}")
    print(f"  REFERENCE_DIR  {config.REFERENCE_DIR or '-'}"
          f"{'' if config.REFERENCE_DIR is None or config.REFERENCE_DIR.exists() else '  (아직 없음)'}")

    print("\n예산")
    print(f"  요청 하나 {config.REQUEST_BUDGET_SEC}s · 개별 호출 {config.REQUEST_TIMEOUT_SEC}s  (RT-001 ⑤-b)")

    missing = [n for n, v in config.KEYS.items() if not v]
    if missing:
        # 없다고 실패로 만들지 않는다 — 키 하나가 비어도 나머지는 돌고,
        # 그 위에서 ⑤ 저하 정책이 UNKNOWN 을 만든다. CLI 가 그 설계를 앞질러 판정하면 안 된다.
        print(f"\n  {len(missing)}개 미설정: {', '.join(missing)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m realtime", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_config = sub.add_parser("config", help="키·경로가 실제로 읽히는지 확인")
    p_config.set_defaults(func=cmd_config)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
