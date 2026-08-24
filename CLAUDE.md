# daengs-life — 강아지 생활 비서 AI (개인 파트 레포)

팀 프로젝트 중 내 파트만 작업하는 레포. 파트 2개:
1. **제도·문서형 RAG** — 동물등록/예방접종/목줄·입마개(맹견)/동반이동/지자체지원/펫보험. **KPI = 답변에 출처 링크 + 조항 번호 인용**
2. **실시간 조회형** — 산책 적합 날씨·미세먼지 (GPS 기반, 실질 해상도는 동 단위가 상한)

## 작업 방식 (중요)
- 파트별 **논의 → `docs/decisions.md`에 결정 기록(ADR) → 구현** 순서. 사용자가 명시하기 전에 구현으로 넘어가지 말 것
- 결정 상태: ✅ 확정 / 🔶 제안(논의중). 논의 결과는 decisions.md에 반영하고 커밋
- 크롤링 산출물은 `data/` (규칙: `data/README.md` — 원본 불변, `.meta.json` 필수, meta 없으면 인덱싱 금지,
  **`data/` 의 수집 결과물은 전부 git 미추적** — 원본·meta·크롤로그 모두 로컬 상태다 (D-017).
  추적하는 것은 `seed_sources.yaml` 과 `.gitkeep` 뿐)
- 조사·설계 문서는 `docs/` (인덱스: `docs/README.md`)
- 진행 방식(우선순위·스프린트·PR)은 `docs/workflow.md`. **PR 은 작업이 끝난 뒤가 아니라 작업 전에 올린다**
  (앞으로 할 일의 명세). 브랜치 하나 = 기능 하나 = PR 하나
- **태스크·P0/P1 의 단일 소스는 그 PR 본문 체크리스트**이고 md 에는 적지 않는다 —
  세션 시작 시 `gh pr view <브랜치의 PR>` 로 읽을 것. Projects 보드는 PR 이 여러 개가 되면 그때 (workflow.md §3)
- 브랜치에서 작업 후 커밋+푸시. 현재 병렬 2개: `feat/rag`(파트① 3단계 청커) · `feat/realtime`(파트② 착수)

## 스택
- backend: FastAPI + uv (Python), LLM은 Gemini API 예정. **`backend/` 는 uv 프로젝트 하나**이고 그 안에 패키지가 셋으로 나뉜다 (D-018): `crawler/` 수집 · `rag/` 인덱싱(parse→chunk→embed→load→search) · `app/` 서빙(예정). 의존 방향은 **app→rag→crawler** 한쪽뿐이고 `tests/test_import_direction.py` 가 막는다.
  실행: `cd backend && uv run python -m crawler run --source <id>` / `uv run python -m rag parse`
- DB: postgres + **pgvector 0.8.6** — `documents` 테이블: `embedding vector(1024)`, `content_hash`(중복 방지 자연키), category CHECK(policy/travel/food), source_type CHECK(document/web/api/manual), source_url/document_title/section 컬럼 (조항 인용용) — D-008
- 오케스트레이션: **Celery + Beat + Redis** (D-001 확정 — Airflow 아님)
- frontend: Next.js (단순 확인용)
- 로컬: `docker compose up -d` (컨테이너 `daengs_life_db`, DB명 `lifedb`, init은 `db/init/`)

## 현재 상태 (2026-08-22 기준)
- 완료: 데이터 소스 조사(`docs/data-sources.md` — 파트별 체크리스트), 실시간 API 조사+GPS 결론(`docs/realtime-apis.md`), DB 기동·스키마 검증
- **수집 28건 — §1 공통·법령 파트 전체 완료**
  - `easylaw-pet` 14 (해설 + 100문100답 → D-007 골든셋 재료)
  - `law-animal-protection` 3 · `law-livestock-epidemic` 3 (웹 원문 = 사람이 여는 출처 링크)
  - `law-drf-api` 8 (조문 단위 XML + **별표 본문** — 청킹용). `law_serial` ↔ 웹의 `lsiSeq` 로 짝지음
- 확정: D-001 오케스트레이션 / D-008 저장 규약·스키마 / D-009 크롤러 배치·소스 계약 / D-010 원본 부재 재수집 /
  D-011 법령 웹 원문 경로 / D-012 소스 도메인 분류·API 키 규칙 / D-013 MCP 미채택 / D-014 env 배치·의존방향 가드 /
  D-015 pydantic-settings / D-016 법령 API 수집 완료 / **D-004 청킹 전략(구조 기반)** /
  **D-018 인덱싱 패키지 경계(`backend/rag/`)·파서 3층·공통 IR 6종** / **D-019 parsed 산출물 규약** / **D-020 별표 표 파싱** /
  **D-021 청커 5결정(입력범위·길이기준·content조립·폴백없음·산출물규약)**
- 논의중(🔶):
  D-003 하이브리드·리랭커, D-005 실행순서, D-006 EDA 시스템화, D-007 평가 체계
- **다음 목표: 수집한 28건 전부로 RAG 한 세트 관통** (아래 9단계). 소스 추가는 그 뒤로 미룸
- ⚠️ `data/` 는 미추적(D-017)이라 **PC 마다 상태가 다르다.** 새 PC 에서는 `backend/.env` 에 LAW_OC 를 넣고
  4소스(`easylaw-pet`·`law-animal-protection`·`law-livestock-epidemic`·`law-drf-api`)를 재수집 → `rag parse` 하면
  28건/22 parsed 가 복원된다 (2026-08-22 실제로 복원, 요소 수 동일 재현 확인)

### RAG 관통 실행 순서
1. ~~**D-004 확정**~~ ✅ 2026-08-20 — 질문 1~7 정답 위치를 원문에서 확인, 구조 기반 전략 + 판정표 확정
2. ~~**파서**~~ ✅ 2026-08-21 — `backend/rag/` 신설, `processed/parsed/*.jsonl` **22건** (article 629 · para 552 · table 89 · heading 97 · aside 27 · qa 10). 서식 126건·웹 원문 6건 제외
3. ~~**청커**~~ ✅ 2026-08-24 — D-021 ①~⑤ 확정 + `rag/chunk.py` 구현. `processed/chunks/*.jsonl` **1,407청크**
   (article 720 · table 423 · 부칙 192 · easylaw 소제목 40 · aside 22 · qa 10). **검문소① 통과** — 질문 1~7 정답 청크 12개를
   `tests/test_chunk.py` 가 단언한다. 2,000자 초과 3건은 경고만(④ 폴백 없음) · content 중복 5건 경고 →
   `data/processed/chunks/*.jsonl` · **검문소① 질문 1~7의 정답 청크가 하나씩 실재하는지 눈으로 확인**
4. ~~**임베딩 3종**~~ ✅ 2026-08-24 — `embeddings/{key}.parquet` 3종 (각 1407×1024, L2 정규화, fp32, 6.4MB)
   `bge-m3`(기준선) · `kure-v1`(한국어 튜닝, bge-m3 파생) · `qwen3-embedding-0.6b`(계열 다름+영어) — 셋 다 1024 native
   **토큰 가드 통과** — 최대 2,026 / 한계 8,192 (25%). Qwen3 만 질의에 공식 지시문을 붙이는 비대칭이라 `encode_query` 를 나눠 뒀다(6단계가 쓴다)
5. **골든셋 시드** — 질문 7개 + easylaw Q/A 7개 = 14건
6. **3파전 비교**(Hit@5·MRR) · **검문소② 명백히 나쁜 것만 거름** (14건이라 통계적 판정은 불가)
7. **승자 1종만 DB 적재** (`documents`, `embedding_model` 기록)
8. **검색 CLI (dense만)** · **검문소③ top-5 눈으로 확인** — 하이브리드·리랭커는 D-003으로 미룸
9. **LLM 생성**(Gemini) → 이후 FastAPI `/ask` → (선택) Next.js

검증용 질문 10개 (1~7만 소스 확보됨):
1. 강아지 등록 안 하면 어떻게 되나요 / 2. 등록정보 변경 언제까지 신고 / 3. 목줄 안 하면 과태료 얼마 /
4. 로트와일러인데 맹견인가요 / 5. 맹견 사육 허가 필요한가요 / 6. 광견병 접종 의무인가요 /
7. 국립공원에 강아지 가능한가요 / ~~8. KTX~~ ~~9. 서울 지원금~~ ~~10. 펫보험 슬개골~~ (소스 미수집)

준비물: `GEMINI_API_KEY`(9단계) · ~~`uv sync --group ml`~~ ✅ · ~~모델 3종 디스크~~ ✅ **실측 ~10GB**(bge-m3 6.5 · KURE 2.2 · Qwen3 1.2)
  - GPU 는 RTX 3050 **6GB** — fp32 모델 3종이 합쳐 ~7GB 라 **한 프로세스에서 연속 로드하면 VRAM 이 누적돼 마지막 모델이 10배 넘게 느려진다.** `rag.embed.release()` 로 모델마다 내린다
- 테스트: `cd backend && uv run pytest` (의존 방향 가드 + 설정 로딩)
- 필요 키(**`backend/.env`**): LAW_OC ✅발급완료·설정완료 / DATA_GO_KR_KEY·KAKAO_REST_KEY 미발급 — 발급처는 docs/data-sources.md §9
  - env 배치는 배포 단위 기준(D-014): 루트 `.env`=인프라(compose), `backend/.env`=백엔드 런타임, `frontend/.env`=프론트
  - 읽는 순서 실제 환경변수 > `backend/.env` > 루트 `.env`. 컨테이너에선 `DAENGS_DATA_DIR` 로 data/ 위치 지정
