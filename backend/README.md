# backend

**uv 프로젝트 하나**이고 그 안에 패키지가 다섯으로 나뉜다 (RAG-018 · RAG-027). Python **3.12 고정**(`>=3.12,<3.13`).

| 패키지 | 역할 | CLI |
|---|---|---|
| `crawler/` | 수집 — 소스별 크롤러 (`core/` · `sources/`) | `python -m crawler {list,run}` |
| `rag/` | 인덱싱 — `pipeline.py`(순서의 단일 소스) · `core/`(config·io·ir) · `stages/` | `python -m rag {list,parse,chunk,show,embed,goldenset,evaluate,load,search,generate}` |
| `realtime/` | 실시간 — `transport/` 3 · `providers/` 7 · `collect` · `rules` · `cache` | `python -m realtime {config,geo,walk}` |
| `tasks/` | Celery 워커 · Beat (RAG-001) | `celery -A tasks.celery_app worker --pool=solo` / `... beat` |
| `app/` | 서빙 — `controllers` · `services` · `dto` · `deps` (RAG-027) | `fastapi run app/main.py` |

**의존 방향은 `app` → {`rag`, `realtime`} → `crawler` 한쪽뿐이다.**
`tests/test_import_direction.py`(방향)와 `test_import_direction_packages.py`(범위) 둘이 기계로 막는다.
`rag/` 안은 **순서로 가른다** (RAG-023) — 순서 있는 것은 `stages/`, 없는 것은 `core/`, 순서 자체는 `pipeline.py` 가 소유한다.
파일 이름에 단계 번호를 박지 않는다.

강제 규칙 하나 — **컨트롤러에 로직 0줄** (RAG-027). 조립 순서는 파트마다 주인이 다르다:
파트②는 `services/walk.py`, **파트①은 `rag.stages.generate.ask()`** — `rag` 가 FastAPI 없이 돌아야 해서다 (RAG-028 ③).

## 실행

```bash
uv sync              # 서빙·수집만
uv sync --group ml   # + torch·sentence-transformers (임베딩 단계)

uv run fastapi run app/main.py   # POST /ask · GET /walk
uv run fastapi dev app/main.py   # ⚠️ reload 기본 — 저장할 때마다 모델 로드 5~7초를 다시 문다 (RAG-028 ①)
uv run pytest                    # 365 통과 / 1 deselected, 35초 (2026-08-27, DB 기동 상태)
uv run pytest -m slow            # 임베딩 가중치를 실제로 로드하는 테스트 (기본 제외)
```

- ⚠️ **DB 를 먼저 띄우고 테스트할 것** (`docker compose up -d db redis`). `psycopg.connect` 에 `connect_timeout` 이
  없어(`rag/stages/load.py:122`) DB 가 없으면 `test_load.py` 부근에서 테스트마다 TCP 타임아웃을 물어
  **멈춘 것처럼 보인다** — 같은 날 실측으로 **기동 35초 vs 미기동 15분+ 정지**
- 의존성은 **반드시 `uv add` / `uv remove`** 로. `uv.lock` 은 커밋한다
- `main.py` 는 **2줄 shim** 이다 (실물은 `app/main.py`). 이관 때 정리 대상
- 파이프라인 전체 순서와 새 PC 복원 절차는 [`../docs/handoff-daengs-dev.md` §4](../docs/handoff-daengs-dev.md)

## 설정

`.env` 는 **배포 단위 기준**으로 나뉜다 (RAG-014). 이 폴더의 `.env` 가 백엔드 런타임(FastAPI · Celery · crawler CLI) 용이고,
레포 루트 `.env` 는 compose 인프라 용이다. 읽는 순서는 **실제 환경변수 > `backend/.env` > 루트 `.env`** (pydantic-settings, RAG-015).

키는 `.env.example` 참고 — `LAW_OC` · `DATA_GO_KR_KEY` · `KAKAO_REST_KEY` · `KMA_HUB_KEY` · `GEMINI_API_KEY`.
⚠️ `DATA_GO_KR_KEY` 는 포털이 Encoding/Decoding 두 벌로 준다. **맞는 것은 Decoding 쪽**이다.
읽혔는지 확인은 `uv run python -m realtime config`.
