"""경로·공통 상수. 환경변수로만 덮어쓴다 (pydantic-settings는 app 쪽 관심사라 여기선 안 씀)."""
from __future__ import annotations

import os
import re
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


def _load_dotenv(path: Path) -> None:
    """REPO_ROOT/.env 의 KEY=VALUE 를 환경변수로 올린다. 이미 있는 값은 덮지 않는다.

    python-dotenv 를 넣지 않은 이유 — 필요한 건 이 10줄뿐이고, crawler 는 의존성을 얇게 유지한다
    (D-009). docs 가 "키는 .env 에" 라고 안내하므로 CLI 를 그냥 실행해도 읽혀야 한다.
    """
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


_load_dotenv(REPO_ROOT / ".env")

# 발급받은 API 키. 미발급이면 빈 문자열이고, 그 소스는 discover() 에서 안내 메시지와 함께 멈춘다.
# 이름은 docs/data-sources.md §9 발급 체크리스트와 같다.
_SECRET_ENV = ["LAW_OC", "DATA_GO_KR_KEY", "KAKAO_REST_KEY", "SEOUL_OPEN_DATA_KEY", "KMA_HUB_KEY"]
SECRETS = {name: os.environ.get(name, "").strip() for name in _SECRET_ENV}

LAW_OC = SECRETS["LAW_OC"]


# 키가 담기는 쿼리 파라미터 이름. 값 대신 이름으로 지우는 게 정확하다 —
# LAW_OC 는 이메일 앞부분이라 짧을 수 있고, 짧은 값을 문자열 치환하면 URL 의 멀쩡한 부분까지 망가진다.
_RE_SECRET_PARAM = re.compile(
    r"([?&](?:OC|serviceKey|authKey|apiKey|appKey|KEY)=)[^&#]*", re.IGNORECASE)


def redact(url: str | None) -> str | None:
    """URL 에 박힌 API 키를 *** 로 가린다.

    API 소스는 키를 쿼리스트링에 넣는데, 그 URL 이 `.meta.json` 의 source_url 로 들어가고
    meta 는 git 에 커밋된다(D-008). 저장·로그·화면 출력 직전에 반드시 통과시킨다.

    파라미터 이름으로 한 번, 발급받은 값 자체로 한 번 — 두 겹으로 지운다.
    이름을 모르는 새 API 가 와도 값 매칭이 받아내고, 값이 짧아 값 매칭을 못 쓰면 이름이 받아낸다.
    """
    if not url:
        return url
    url = _RE_SECRET_PARAM.sub(r"\1***", url)
    for value in SECRETS.values():
        if len(value) >= 8:                   # 짧은 값은 URL 의 정상 문자열을 오탐하므로 이름 규칙에 맡긴다
            url = url.replace(value, "***")
    return url
