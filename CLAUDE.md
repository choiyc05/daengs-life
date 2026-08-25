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
- backend: FastAPI + uv (Python), LLM은 Gemini API 예정. **`backend/` 는 uv 프로젝트 하나**이고 그 안에 패키지가 셋으로 나뉜다 (D-018): `crawler/` 수집 · `rag/` 인덱싱 · `app/` 서빙(예정). **`rag/` 안은 순서로 가른다**(D-023) — `pipeline.py`(순서의 단일 소스) · `core/`(config·io·ir) · `stages/`(parse/·chunk·embed·goldenset…). 의존 방향은 **app→rag→crawler** 한쪽뿐이고 `tests/test_import_direction.py` 가 막는다.
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
  **D-021 청커 5결정(입력범위·길이기준·content조립·폴백없음·산출물규약)** /
  **D-022 골든셋 6결정(필수·보강 2층·법제처 라벨 차용·15문항·날짜 뺀 논리 주소)** /
  **D-023 `rag/` 배치(`core/`+`stages/`+`pipeline.py`)** /
  **D-024 3파전 4결정(사전등록·기준선 우선 / 판정 k=5 / 탈락선 Hit@5 2문항 차 · Recall·MRR 은 기록만 / 덤프 미추적·판정은 ADR)**
  / **D-025 7단계 적재 5결정(upsert+한 트랜잭션 · psycopg3+SQL 직접 · 중복은 대표+merged_from · source 를 파서·청커에 실음 · 임베딩 지문을 (chunk_id,content) 로)**
  / **D-026 8단계 검색(부칙 기본 포함·필터는 플래그 / 검색은 `stages/search.py` 하나, CLI·9단계·FastAPI 가 같은 함수)**
    — **판정 완료: 승자 `Qwen/Qwen3-Embedding-0.6B`** (Hit@5 6:4:3, 나머지 둘 탈락). **첫 관통은 `bge-m3` 로**
- 논의중(🔶):
  D-003 하이브리드·리랭커, D-005 실행순서, D-006 EDA 시스템화, D-007 평가 체계
- **다음 목표: 수집한 28건 전부로 RAG 한 세트 관통** (아래 9단계). 소스 추가는 그 뒤로 미룸
- ⚠️ `data/` 는 미추적(D-017)이라 **PC 마다 상태가 다르다.** 새 PC 에서는 `backend/.env` 에 LAW_OC 를 넣고
  4소스(`easylaw-pet`·`law-animal-protection`·`law-livestock-epidemic`·`law-drf-api`)를 재수집 → `rag parse` 하면
  28건/22 parsed 가 복원된다 (2026-08-22 실제로 복원, 요소 수 동일 재현 확인)

### RAG 관통 실행 순서
1. ~~**D-004 확정**~~ ✅ 2026-08-20 — 질문 1~7 정답 위치를 원문에서 확인, 구조 기반 전략 + 판정표 확정
2. ~~**파서**~~ ✅ 2026-08-21 — `backend/rag/` 신설, `processed/parsed/*.jsonl` **22건** (article 629 · para 552 · table 89 · heading 97 · aside 27 · qa 10). 서식 126건·웹 원문 6건 제외
3. ~~**청커**~~ ✅ 2026-08-24 — D-021 ①~⑤ 확정 + `rag/stages/chunk.py` 구현. `processed/chunks/*.jsonl` **1,407청크**
   (article 720 · table 423 · 부칙 192 · easylaw 소제목 40 · aside 22 · qa 10). **검문소① 통과** — 질문 1~7 정답 청크 12개를
   `tests/test_chunk.py` 가 단언한다. 2,000자 초과 3건은 경고만(④ 폴백 없음) · content 중복 5건 경고 →
   `data/processed/chunks/*.jsonl` · **검문소① 질문 1~7의 정답 청크가 하나씩 실재하는지 눈으로 확인**
4. ~~**임베딩 3종**~~ ✅ 2026-08-24 — `embeddings/{key}.parquet` 3종 (각 1407×1024, L2 정규화, fp32, 6.4MB)
   `bge-m3`(기준선) · `kure-v1`(한국어 튜닝, bge-m3 파생) · `qwen3-embedding-0.6b`(계열 다름+영어) — 셋 다 1024 native
   **토큰 가드 통과** — 최대 2,026 / 한계 8,192 (25%). Qwen3 만 질의에 공식 지시문을 붙이는 비대칭이라 `encode_query` 를 나눠 뒀다(6단계가 쓴다)
5. ~~**골든셋 시드**~~ ✅ 2026-08-24 — D-022 ①~⑥ 확정 + `rag/stages/goldenset.yaml` 구현.
   검증질문 7 + easylaw Q/A 8 = **15문항 / 필수 43개 · 보강 15 · 분모 제외 8**.
   `uv run python -m rag goldenset` 이 라벨 실존을 검사하고 `tests/test_goldenset.py` 11개가 고정한다.
   정답은 **필수/보강 2층**, Q/A 절반은 법제처의 `관련 법령` 을 그대로 라벨로 쓴다(사람 판단 0).
   `backend/rag/stages/goldenset.yaml` **git 추적** — `data/` 는 미추적이라 판단 기록이 유실된다.
   라벨은 **수집 날짜를 뺀 논리 주소**(`...-act#제101조③`) — 재수집해도 안 깨진다
6. ~~**3파전 비교**~~ ✅ 2026-08-24 — D-024 ①~④ 확정 + `rag/stages/evaluate.py` 구현.
   **승자 `qwen3-embedding-0.6b`** (Hit@5 **6/15** : kure 4 : bge 3 — 나머지 둘이 2문항 이상 낮아 탈락).
   사전 등록이 일했다 — 논의 때 기각했던 3순위가 이겼다. 대신 **`encode_query` 비대칭이 7·8·9단계와 서빙까지 따라간다**.
   절대값이 낮은 원인 둘(덤프 확인): easylaw `qa` 청크가 모든 질문의 top 을 점령 · `must` 인 법령 조문은 질문과 표면이 안 겹침
   → **D-003(하이브리드·리랭커)이 필요하다는 실측 근거**. 절대 판정은 8단계 검문소③이 한다
   ⚠️ **D-022 ④ 가설이 뒤집혔다** — `제2조` 는 공짜 점수가 아니라 **세 모델 다 top-5 진입 0/6**(중앙 116~442위)인
   닿지 못하는 라벨이다. `nice` 강등 조건은 충족됐고 판정은 그와 무관하게 성립한다(Hit 은 안 바뀐다). Q4 는 제외 대상
7. ~~**DB 적재**~~ ✅ 2026-08-25 — D-025 ①~⑤ 확정 + `rag/stages/load.py` 구현. **`documents` 1,402행**
   (1,407청크 − content 중복 5건, `metadata.merged_from` 에 보존) · `embedding_model = BAAI/bge-m3`.
   ⚠️ **판정 승자는 `qwen3-embedding-0.6b` 지만 첫 관통은 기준선으로 간다** (D-024 `판정 이후`).
   교체는 `--model` 한 번이고 실제로 양방향 확인했다. 적재 벡터 = parquet (오차 0.0)
   **D-025 ⑤ — 임베딩 지문을 `(chunk_id, content)` 로 좁혔다.** 메타 필드를 더해도 재임베딩이 안 걸린다:
   `source`·`source_id` 를 실어 청크 22파일을 다시 썼는데 지문 불변(`c01f5fb6`), 6단계 판정도 그대로 재현
   실행: `uv run python -m rag load [--model <key>] [--dry-run]` · 인덱스는 적재 후 `db/indexes.sql` 수동
8. ~~**검색 CLI (dense만)**~~ ✅ 2026-08-25 — D-026 확정 + `rag/stages/search.py`. **검문소③ 통과** —
   필수가 top-5 에 든 문항 **2/7**(Q5·Q7)이고 6단계 `bge-m3` 결과와 정합(적재가 벡터를 옳게 옮겼다는 독립 확인).
   부칙은 **기본 포함**, `--no-supplementary` 로 끈다 — 검사 도구와 서빙의 기본값은 다르다(D-026 ①). 켜도 결과 동일
   **검문소③이 잡은 것 둘**: ⓐ dense 가 질문의 *의도* 가 아니라 *표면 어휘* 를 따라간다
   (Q1 처벌→'등록' 해설만 · Q3 목줄→가축전염병 과태료 별표 · Q6 광견병→혈청검사 수수료) = **D-003 의 근거**
   ⓑ **골든셋이 Hit 을 과소평가한다** — easylaw 해설이 본문에 조항 번호를 담고 있어 실제로는 답인데 `must` 가 아니다.
   즉 `Hit@5=0.200` 은 "20%만 답한다"가 아니라 "법령 조문에 20%만 닿는다" (D-022 재검토 대기)
   실행: `uv run python -m rag search "질의"` / `--questions` (검증질문 7개 = 검문소③)
9. **LLM 생성**(Gemini) → 이후 FastAPI `/ask` → (선택) Next.js

검증용 질문 10개 (1~7만 소스 확보됨):
1. 강아지 등록 안 하면 어떻게 되나요 / 2. 등록정보 변경 언제까지 신고 / 3. 목줄 안 하면 과태료 얼마 /
4. 로트와일러인데 맹견인가요 / 5. 맹견 사육 허가 필요한가요 / 6. 광견병 접종 의무인가요 /
7. 국립공원에 강아지 가능한가요 / ~~8. KTX~~ ~~9. 서울 지원금~~ ~~10. 펫보험 슬개골~~ (소스 미수집)

준비물: ~~`GEMINI_API_KEY`(9단계)~~ ✅ **`backend/.env` 에 이미 있다**(실측 2026-08-24) · ~~`uv sync --group ml`~~ ✅ ·
  ~~모델 3종 디스크~~ ✅ **실측 ~10GB**(bge-m3 6.5 · KURE 2.2 · Qwen3 1.2). 7단계 이후로는 **승자 Qwen3 1.2GB 만** 필요하다
  - GPU 는 RTX 3050 **6GB** — fp32 모델 3종이 합쳐 ~7GB 라 **한 프로세스에서 연속 로드하면 VRAM 이 누적돼 마지막 모델이 10배 넘게 느려진다.** `rag.embed.release()` 로 모델마다 내린다
- 테스트: `cd backend && uv run pytest` (의존 방향 가드 + 설정 로딩)
- 필요 키(**`backend/.env`**): LAW_OC ✅발급완료·설정완료 / DATA_GO_KR_KEY·KAKAO_REST_KEY 미발급 — 발급처는 docs/data-sources.md §9
  - env 배치는 배포 단위 기준(D-014): 루트 `.env`=인프라(compose), `backend/.env`=백엔드 런타임, `frontend/.env`=프론트
  - 읽는 순서 실제 환경변수 > `backend/.env` > 루트 `.env`. 컨테이너에선 `DAENGS_DATA_DIR` 로 data/ 위치 지정
