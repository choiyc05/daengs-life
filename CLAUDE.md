# daengs-life — 강아지 생활 비서 AI (개인 파트 레포)

팀 프로젝트 중 내 파트만 작업하는 레포. 파트 2개:
1. **제도·문서형 RAG** — 동물등록/예방접종/목줄·입마개(맹견)/동반이동/지자체지원/펫보험. **KPI = 답변에 출처 링크 + 조항 번호 인용**
2. **실시간 조회형** — 산책 적합 날씨·미세먼지 (GPS 기반, 실질 해상도는 동 단위가 상한)

## 작업 방식 (중요)
- 파트별 **논의 → `docs/decisions.md`에 결정 기록(ADR) → 구현** 순서. 사용자가 명시하기 전에 구현으로 넘어가지 말 것
- 결정 상태: ✅ 확정 / 🔶 제안(논의중). 논의 결과는 decisions.md에 반영하고 커밋
- 크롤링 산출물은 `data/` (규칙: `data/README.md` — 원본 불변, `.meta.json` 필수, meta 없으면 인덱싱 금지, **원본은 git 미추적**)
- 조사·설계 문서는 `docs/` (인덱스: `docs/README.md`)
- 브랜치에서 작업 후 커밋+푸시 (현재: `feat/data-sources`)

## 스택
- backend: FastAPI + uv (Python), LLM은 Gemini API 예정. `backend/` 는 uv 프로젝트 하나이고 그 안에 `crawler/`(순수 패키지+CLI, D-001 원칙1) 가 있다. 의존 방향은 app→crawler 한쪽뿐. 실행: `cd backend && uv run python -m crawler run --source <id> [--dry-run --limit N]`
- DB: postgres + **pgvector 0.8.6** — `documents` 테이블: `embedding vector(1024)`, `content_hash`(중복 방지 자연키), category CHECK(policy/travel/food), source_type CHECK(document/web/api/manual), source_url/document_title/section 컬럼 (조항 인용용) — D-008
- 오케스트레이션: **Celery + Beat + Redis** (D-001 확정 — Airflow 아님)
- frontend: Next.js (단순 확인용)
- 로컬: `docker compose up -d` (컨테이너 `daengs_life_db`, DB명 `lifedb`, init은 `db/init/`)

## 현재 상태 (2026-08-19 기준)
- 완료: 데이터 소스 조사(`docs/data-sources.md`, 시드 30개 `data/manifests/seed_sources.yaml`), 실시간 API 조사+GPS 결론(`docs/realtime-apis.md`), D-001 오케스트레이션 확정, D-008 저장 규약·스키마 정정 확정, DB 기동·스키마 검증, **크롤러 뼈대(`backend/crawler/`) + 첫 소스 `easylaw-pet` 14건 수집 (본문 7 + 100문100답 7, 조항 인용 추출)**
- 논의중(🔶): D-002 임베딩(gemini@1024 기본값→골든셋 3파전 베이크오프), D-003 하이브리드·리랭커, D-004 청킹(조문 단위), D-005 실행순서, D-006 EDA 시스템화, D-007 평가 체계(Hit@5·MRR·LLM judge)
- 다음 후보: Phase 1 나머지 소스(animal.go.kr → 정부24 → nias → 법령 웹 원문) 를 `crawler/sources/` 에 추가 — 절차는 `backend/crawler/README.md`. 그 다음 파싱/청킹(D-004) 으로 첫 RAG 관통
- 필요 키(**`backend/.env`**, 미발급): DATA_GO_KR_KEY, LAW_OC, KAKAO_REST_KEY — 발급처는 docs/data-sources.md §9
  - env 배치는 배포 단위 기준(D-014): 루트 `.env`=인프라(compose), `backend/.env`=백엔드 런타임, `frontend/.env`=프론트
  - 읽는 순서 실제 환경변수 > `backend/.env` > 루트 `.env`. 컨테이너에선 `DAENGS_DATA_DIR` 로 data/ 위치 지정
