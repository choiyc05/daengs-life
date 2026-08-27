# daengs-life — 강아지 생활 비서 AI (개인 파트)

팀 프로젝트 **DAENGS** 중 내가 맡은 두 파트를 따로 개발한 레포.

> ⚠️ **이 레포는 [`SAJOYO/DAENGS_dev`](https://github.com/SAJOYO/DAENGS_dev) 로 이관 예정이다 (2026-08-27).**
> 옮길 때 무엇이 부딪히고 무엇이 안 따라가는지는 **[docs/handoff-daengs-dev.md](docs/handoff-daengs-dev.md)** 에 정리해 뒀다.
> 이후 작업은 그쪽 규칙(`dev` 브랜치 · PR 본문 `## 작업 목록`)을 따른다.

| 파트 | 무엇 | KPI / 한계 | 상태 |
|---|---|---|---|
| ① 제도·문서형 RAG | 동물등록 · 예방접종 · 목줄/입마개(맹견) · 동반이동 · 지자체지원 · 펫보험 | **답변에 출처 링크 + 조항 번호 인용** | 1랩 관통 완료 (`POST /ask`) |
| ② 실시간 조회형 | 산책 적합 날씨 · 미세먼지 (GPS 기반) | 실질 해상도는 **동 단위가 상한** | 완료 (`GET /walk`) |

전부 PDF·공고문이라 청킹·인덱싱 대상이 명확하고, **출처 링크와 조항 번호를 같이 뱉는 것**이 그대로 성능 지표가 된다.

## 지금 돌아가는 것

- **`POST /ask`** — 질문 → 검색 5건 → Gemini 생성 → 답변 + 근거(출처 링크·조항)
- **`GET /walk?lat=&lon=`** — `서초2동 (측정소: 강남대로) 기준` 같은 판정 + T+24h 타임라인 + 권장 산책 구간
- 코퍼스 **28건 수집 → 1,407청크 → `documents` 1,402행** · 테스트 **365 통과** (2026-08-27, DB 기동 상태에서 35초)
- ⚠️ **완성이 아니다.** 시드 30개 중 11개만 수집했고, 남은 19개와 그 파서(특히 **PDF 파서 없음**)가 2랩이다

## 실행

```bash
docker compose up -d            # db(postgres+pgvector) · redis
cd backend
uv sync --group ml              # ml 그룹은 임베딩용. 서빙만이면 uv sync
uv run fastapi run app/main.py  # POST /ask · GET /walk
uv run pytest
```

인덱싱 파이프라인(수집→parse→chunk→embed→load→search→generate)과 새 PC 복원 절차는
**[docs/handoff-daengs-dev.md §4](docs/handoff-daengs-dev.md)** 에 명령까지 그대로 있다.

⚠️ **`data/` 는 통째로 git 미추적**이라 PC 마다 상태가 다르다 (RAG-017). 클론만으로는 코퍼스가 없다.

## 구성

| 경로 | 내용 |
|---|---|
| `backend/crawler/` | 수집 — 소스별 크롤러 |
| `backend/rag/` | 인덱싱 — `pipeline.py`(순서의 단일 소스) · `core/` · `stages/`(parse→chunk→embed→load→search→generate) |
| `backend/realtime/` | 실시간 — `transport/` 3 · `providers/` 7 · `collect` · `rules` · `cache` |
| `backend/tasks/` | Celery 워커 · Beat (RAG-001) |
| `backend/app/` | 서빙 — `controllers` · `services` · `dto` · `deps` (RAG-027, **컨트롤러에 로직 0줄**) |
| `db/init/` | 최초 기동 스키마. `indexes.sql` 은 적재 후 수동 |
| `frontend/` | Next.js — 단순 확인용 |

의존 방향은 **`app` → {`rag`, `realtime`} → `crawler`** 한쪽뿐이고 `tests/test_import_direction*.py` 둘이 기계로 막는다.

## 문서

| 문서 | 내용 |
|---|---|
| [docs/handoff-daengs-dev.md](docs/handoff-daengs-dev.md) | **이관 노트** — 충돌 11개 · 안 따라가는 것 · 복원 절차 · 남은 일 |
| [docs/README.md](docs/README.md) | 문서 인덱스 |
| [docs/decisions-rag.md](docs/decisions-rag.md) | 설계 결정 (`RAG-`) — 공통·파트① |
| [docs/decisions-realtime.md](docs/decisions-realtime.md) | 설계 결정 (`RT-`) — 파트② |
| [docs/data-sources.md](docs/data-sources.md) | 데이터 소스 조사 · 수집 체크리스트 · 키 발급처 |
| [docs/realtime-apis.md](docs/realtime-apis.md) | 실시간 API + GPS 정밀도 결론 (§6 실측이 최신) |
| [docs/workflow.md](docs/workflow.md) | 작업 방식 — 우선순위 · PR 을 작업 **전에** 올리는 규칙 |
| [data/README.md](data/README.md) | 수집 데이터 저장 규칙 (`.meta.json` 필수) |

**ADR 번호는 파트별로 파일이 갈린다** — 공통·파트① = `decisions-rag.md` 의 `RAG-` / 파트② = `decisions-realtime.md` 의 `RT-`.
⚠️ 접두사는 2026-08-27 에 `D-` → `RAG-` 로 바꿨다 — **DAENGS_dev 가 `D-` 를 이미 쓰기 때문**이다 (이관 노트 §3-1). 번호는 그대로다.

## 스택

FastAPI + uv (Python 3.12) · Gemini · postgres + **pgvector 0.8.6**(`vector(1024)`) · Celery + Beat + Redis · Next.js
