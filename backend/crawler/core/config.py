"""경로·공통 상수. 환경변수로만 덮어쓴다 (pydantic-settings는 app 쪽 관심사라 여기선 안 씀)."""
from __future__ import annotations

import os
from pathlib import Path
from zoneinfo import ZoneInfo

KST = ZoneInfo("Asia/Seoul")

USER_AGENT = "daengs-life-crawler/0.1 (+mailto:choiyc05@gmail.com)"
REQUEST_DELAY_SEC = 1.5        # 같은 호스트 연속 요청 간격 (docs/data-sources.md §4)
REQUEST_TIMEOUT_SEC = 30
MAX_RETRIES = 3


def _find_repo_root(start: Path) -> Path:
    """data/manifests/seed_sources.yaml 이 보이는 곳까지 위로 올라간다."""
    for p in [start, *start.parents]:
        if (p / "data" / "manifests" / "seed_sources.yaml").exists():
            return p
    raise RuntimeError("repo root not found (data/manifests/seed_sources.yaml 기준)")


REPO_ROOT = Path(os.environ.get("DAENGS_REPO_ROOT") or _find_repo_root(Path(__file__).resolve()))
DATA_DIR = Path(os.environ.get("DAENGS_DATA_DIR") or REPO_ROOT / "data")
RAW_DIR = DATA_DIR / "raw"
MANIFEST_DIR = DATA_DIR / "manifests"
SEED_FILE = MANIFEST_DIR / "seed_sources.yaml"
CRAWL_LOG = MANIFEST_DIR / "crawl_log.jsonl"
