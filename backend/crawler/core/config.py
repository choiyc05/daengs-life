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


# backend/ — 이 패키지가 속한 uv 프로젝트의 루트. crawler/core/config.py 에서 세 단계 위다.
# 레포를 통째로 두든 backend/ 만 이미지에 넣든 **항상 존재하는** 유일한 기준점이라
# .env 를 찾는 출발점으로 쓴다.
PACKAGE_ROOT = Path(__file__).resolve().parents[2]


def _find_repo_root(start: Path) -> Path | None:
    """data/manifests/seed_sources.yaml 이 보이는 곳까지 위로 올라간다. 없으면 None.

    없다고 예외를 내면 안 된다 — 백엔드 이미지에는 data/ 가 없고, app 이 crawler 를 import 하므로
    (D-009) import 시점에 터지면 컨테이너가 아예 뜨지 않는다. 데이터가 정말 필요한 시점에
    require_data_dir() 이 안내와 함께 실패한다.
    """
    for p in [start, *start.parents]:
        if (p / "data" / "manifests" / "seed_sources.yaml").exists():
            return p
    return None


_repo_root_env = os.environ.get("DAENGS_REPO_ROOT")
REPO_ROOT: Path | None = Path(_repo_root_env) if _repo_root_env else _find_repo_root(PACKAGE_ROOT)


def _load_dotenv(path: Path) -> None:
    """KEY=VALUE 를 환경변수로 올린다. **이미 있는 값은 덮지 않는다.**

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


# 우선순위: 실제 환경변수 > backend/.env > 레포 루트 .env  (setdefault 라 먼저 읽은 쪽이 이긴다)
#   backend/.env  — 이 배포 단위가 쓰는 값 (API 키). D-014
#   루트 .env      — compose 가 읽는 인프라 값. 백엔드에도 필요한 값이 여기 있으면 받아 쓴다
# 배포에서는 오케스트레이터가 넣은 환경변수가 항상 이기므로 두 파일 다 없어도 그대로 동작한다.
_load_dotenv(PACKAGE_ROOT / ".env")
if REPO_ROOT is not None:
    _load_dotenv(REPO_ROOT / ".env")

_data_dir_env = os.environ.get("DAENGS_DATA_DIR")
DATA_DIR: Path | None = (
    Path(_data_dir_env) if _data_dir_env
    else (REPO_ROOT / "data" if REPO_ROOT is not None else None)
)
RAW_DIR = DATA_DIR / "raw" if DATA_DIR else None
MANIFEST_DIR = DATA_DIR / "manifests" if DATA_DIR else None
SEED_FILE = MANIFEST_DIR / "seed_sources.yaml" if MANIFEST_DIR else None
CRAWL_LOG = MANIFEST_DIR / "crawl_log.jsonl" if MANIFEST_DIR else None


def require_data_dir() -> Path:
    """data/ 가 필요한 작업의 진입점에서 부른다. 없으면 무엇을 해야 하는지 알려주며 실패한다."""
    if DATA_DIR is None:
        raise RuntimeError(
            "데이터 경로를 찾지 못했다 (data/manifests/seed_sources.yaml 기준으로 탐색).\n"
            "  레포 밖에서 실행 중이면 DAENGS_DATA_DIR 로 data/ 위치를 알려줄 것.\n"
            "  예) 컨테이너: DAENGS_DATA_DIR=/data + 볼륨 마운트\n"
            f"  탐색 시작점: {PACKAGE_ROOT}"
        )
    return DATA_DIR

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
