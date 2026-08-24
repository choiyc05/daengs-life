"""rag 의 경로·상수.

**경로 탐색은 `crawler.core.config` 것을 그대로 쓴다** — "data/ 는 어디인가"의 답이 둘이 되면
컨테이너에서 크롤러와 파서가 서로 다른 곳을 보게 된다 (D-014). 그 외의 설정(DATABASE_URL,
GEMINI_API_KEY, 임베딩 모델명)은 rag 가 자기 Settings 로 갖는다 — 필요해지는 4·7·9단계에 추가한다.
"""
from __future__ import annotations

from pathlib import Path

from crawler.core.config import DATA_DIR, KST, RAW_DIR, require_data_dir  # noqa: F401

PROCESSED_DIR: Path | None = DATA_DIR / "processed" if DATA_DIR else None
PARSED_DIR: Path | None = PROCESSED_DIR / "parsed" if PROCESSED_DIR else None
CHUNK_DIR: Path | None = PROCESSED_DIR / "chunks" if PROCESSED_DIR else None
EMBED_DIR: Path | None = PROCESSED_DIR / "embeddings" if PROCESSED_DIR else None
# 6단계 3파전 덤프. **미추적이다** — 기계 산출물이고 chunk_id 의 수집 날짜에 묶여 재수집하면
# 통째로 낡는다. 판단이 남는 자리는 `docs/decisions.md` 의 D-024 다 (D-024 ④).
EVAL_DIR: Path | None = PROCESSED_DIR / "eval" if PROCESSED_DIR else None
