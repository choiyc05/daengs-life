# daengs-life — 강아지 생활 비서 AI (개인 파트 레포)

팀 프로젝트 중 내 파트만 작업하는 레포. 파트 2개:
1. **제도·문서형 RAG** — 동물등록/예방접종/목줄·입마개(맹견)/동반이동/지자체지원/펫보험. **KPI = 답변에 출처 링크 + 조항 번호 인용**
2. **실시간 조회형** — 산책 적합 날씨·미세먼지 (GPS 기반, 실질 해상도는 동 단위가 상한)

## 작업 방식 (중요)
- 파트별 **논의 → 결정 기록(ADR, 아래 번호 규칙) → 구현** 순서. 사용자가 명시하기 전에 구현으로 넘어가지 말 것
- 결정 상태: ✅ 확정 / 🔶 제안(논의중). 논의 결과는 결정 파일에 반영하고 커밋
- **ADR 번호는 파트별로 파일이 갈린다** — 공통·파트① = `docs/decisions.md` 의 `D-` /
  파트②(실시간) = `docs/decisions-realtime.md` 의 `RT-`. 병렬 브랜치가 같은 번호를 각자 발급하는 것을 막는다
- 크롤링 산출물은 `data/` (규칙: `data/README.md` — 원본 불변, `.meta.json` 필수, meta 없으면 인덱싱 금지,
  **`data/` 의 수집 결과물은 전부 git 미추적** — 원본·meta·크롤로그 모두 로컬 상태다 (D-017).
  추적하는 것은 `seed_sources.yaml` 과 `.gitkeep` 뿐)
- 조사·설계 문서는 `docs/` (인덱스: `docs/README.md`)
- 진행 방식(우선순위·스프린트·PR)은 `docs/workflow.md`. **PR 은 작업이 끝난 뒤가 아니라 작업 전에 올린다**
  (앞으로 할 일의 명세). 브랜치 하나 = 기능 하나 = PR 하나
- **태스크·P0/P1 의 단일 소스는 그 PR 본문 체크리스트**이고 md 에는 적지 않는다 —
  세션 시작 시 `gh pr view <브랜치의 PR>` 로 읽을 것. Projects 보드는 PR 이 여러 개가 되면 그때 (workflow.md §3)
- 브랜치에서 작업 후 커밋+푸시. **지금 살아 있는 브랜치는 없다 (2026-08-27).**
  `feat/realtime`(PR #2, 8/25 머지) · `feat/rag`(PR #3, 1랩 `/ask` 까지 — 8/27 머지 후 삭제) 둘 다 `main` 에 들어왔고,
  **`main` 하나에 `crawler/`·`rag/`·`realtime/`·`tasks/`·`app/` 이 전부 있다**
- 다음 작업(2랩)은 **새 브랜치를 파고 PR 을 먼저 여는 것**부터다 — 열린 PR 이 없으니 지금은 읽을 체크리스트도 없다

## 스택
- backend: FastAPI + uv (Python), LLM은 Gemini API 예정. **`backend/` 는 uv 프로젝트 하나**이고 그 안에 패키지가 다섯으로 나뉜다 (D-018 · D-027): `crawler/` 수집 · `rag/` 인덱싱(parse→chunk→embed→load→search) · `realtime/` 실시간 · `tasks/` Celery 워커·Beat · `app/` 서빙(controllers·services·dto). **`rag/` 안은 순서로 가른다**(D-023) — `pipeline.py`(순서의 단일 소스) · `core/`(config·io·ir) · `stages/`. 의존 방향은 **app→{rag,realtime}→crawler** 한쪽뿐이고 `tests/test_import_direction*.py` 둘이 막는다 (방향 + **범위**).
  실행: `cd backend && uv run python -m crawler run --source <id>` / `uv run python -m rag parse`
- 로컬 인프라: `docker compose up -d` — `db`(postgres+pgvector) · **`redis`**(D-001 브로커·캐시, RT-001 ④ 가 첫 사용처)
  compose 프로젝트명은 `compose.yml` 에 `name: daengs-life` 로 **못 박혀 있다** — 안 박으면 워크트리마다
  프로젝트가 갈라져 컨테이너가 두 벌이 된다 (`container_name` 이 같아서 이름만 보면 멀쩡해 보인다)
- DB: postgres + **pgvector 0.8.6** — `documents` 테이블: `embedding vector(1024)`, `content_hash`(중복 방지 자연키), category CHECK(policy/travel/food), source_type CHECK(document/web/api/manual), source_url/document_title/section 컬럼 (조항 인용용) — D-008
- 오케스트레이션: **Celery + Beat + Redis** (D-001 확정 — Airflow 아님)
- frontend: Next.js (단순 확인용)

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
  / **D-027 서빙 계층 배치**(파트②가 발급, **두 파트 공통**) — `app/`={controllers,services,dto,deps}, 강제 규칙은 *컨트롤러에 로직 0줄*
  / **D-028 9단계 서빙**(모델 수명은 호출자 소유·서빙은 CPU 상주 / `/ask` 는 답변+근거 — 1랩 응답은 제품 계약 아닌 관찰 도구 /
  `def` 컨트롤러 / 커넥션은 요청당·`deps.py` 경유 / 답변 덤프는 결정적 축 3개·논리 주소 병기)
  — **③: 배치는 D-027 을 따르되 조립 순서(`검색→생성`)는 `rag.stages.generate.ask()` 가 소유한다.**
  파트②가 `services/walk.py` 에 조립을 둔 것과 갈리는 이유는 **검문소가 사는 층이 달라서**다 —
  파트② 검문소는 전부 API 레벨, 파트① 검문소③④는 CLI 이고 `rag` 는 FastAPI 없이 돌아야 한다(D-001 원칙 1)
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
   ⚠️ **교체 조건은 1랩 완료로 발동했으나 2랩으로 미뤘다** (2026-08-25, 사용자 — D-024 `교체 조건 발동`).
   1랩 덤프가 D-028 ⑥의 비교 축이라 지금 바꾸면 1랩↔2랩 차이의 원인이 코퍼스인지 모델인지 안 갈린다.
   **2랩은 코퍼스와 모델이 같이 바뀌는 랩**이 된다 — 그때 원인을 하나로 특정할 수 없음을 명시할 것
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
9. **LLM 생성**(Gemini) + FastAPI `/ask` → (선택) Next.js  ← ✅ **1랩 완료 2026-08-25. 검문소④ 통과** (PR #3, 8/27 머지)
   **한 랩 = `/ask` 까지**(사용자, 2026-08-25). 그 뒤 **1단계 소스를 최대한 확장해 2랩**을 돈다 —
   그래서 1랩의 목표는 좋은 답이 아니라 **2랩과 비교 가능한 상태**다(D-028 ⑥ 답변 덤프)
   `app/` 배치는 **D-027**(controllers/services/dto/deps)을 따른다. 다만 **조립은 `rag.stages.generate.ask()` 가 소유한다** —
   `rag` 는 `app` 을 import 할 수 없어(D-014) 조립이 `services/ask.py` 에 있으면 **검문소④가 서빙과 다른 코드를 검사**하게 된다(D-026 ② 위반).
   `services/ask.py` 가 담는 것: **서빙 정책 기본값**(k·부칙 — D-026 ①이 비워 둔 자리) · 에러 매핑 · DTO. **생성은 한 줄도 없다**
   ⚠️ **2랩의 비용은 크롤링이 아니라 파서다** — 남은 시드 19개는 소스마다 파서가 필요하고,
   `pdf-entry` 4종(코레일·SRT·서울교통공사·**보험사 약관** = "RAG 핵심 코퍼스")은 **PDF 파서가 아예 없다.**
   `documents.category` CHECK 에 펫보험이 들어갈 값이 없고(policy/travel/food), 골든셋 라벨도
   법제처 차용(D-022 ②)이 안 통해 사람 판단이 든다
   **방침(사용자, 2026-08-25): 먼저 한 세트 붙여서 돌려보고 판단한다.** 설계 논의를 앞세우지 말 것 —
   답이 실제로 어떻게 나오는지 보고 나서 프롬프트·거부 전략을 정한다(D-029 자리)
   만들 것: `rag/stages/generate.py`(`answer` 순수 + `ask`) · `pipeline.py` 한 줄 ·
   `generate` 서브커맨드(`--questions` = **검문소④**) · `app/{controllers,services,dto}/ask.py` +
   `app/main.py` 등록 한 줄(D-027 이 정한 자리) · 테스트 2벌. `backend/main.py` shim 정리는 그다음
   ⚠️ **검문소③이 만든 제약**: 검증질문 7개 중 **5개는 top-5 안에 정답 조항이 없다.** 그대로 LLM 에 주면
   그럴듯한 답을 지어낼 위험이 크고, KPI 가 조항 인용이라 **틀린 조항 번호는 답이 없는 것보다 나쁘다.**
   한 세트 돌려본 뒤 이 문제를 어떻게 막을지(프롬프트 vs 구조적 검사) 결정할 것
   `GEMINI_API_KEY` 는 `backend/.env` 에 **이미 있다**. 검색은 `rag.stages.search.search()` 를 그대로 부른다(D-026 ②)
   실행: `uv run fastapi dev app/main.py` → `POST /ask {"question": "..."}` · 검문소④는 `uv run python -m rag generate --questions`
   ⚠️ **`fastapi dev` 는 reload 가 기본**인데 lifespan 이 임베딩 모델을 올린다(D-028 ①) — 저장할 때마다 로드 5~7초를 다시 문다.
   생성 쪽을 안 만질 때는 `fastapi run`(reload 없음)이나 `--reload-dir` 로 좁힐 것

검증용 질문 10개 (1~7만 소스 확보됨):
1. 강아지 등록 안 하면 어떻게 되나요 / 2. 등록정보 변경 언제까지 신고 / 3. 목줄 안 하면 과태료 얼마 /
4. 로트와일러인데 맹견인가요 / 5. 맹견 사육 허가 필요한가요 / 6. 광견병 접종 의무인가요 /
7. 국립공원에 강아지 가능한가요 / ~~8. KTX~~ ~~9. 서울 지원금~~ ~~10. 펫보험 슬개골~~ (소스 미수집)

준비물: ~~`GEMINI_API_KEY`(9단계)~~ ✅ **`backend/.env` 에 이미 있다**(실측 2026-08-24) · ~~`uv sync --group ml`~~ ✅ ·
  ~~모델 3종 디스크~~ ✅ **실측 ~10GB**(bge-m3 6.5 · KURE 2.2 · Qwen3 1.2). 7단계 이후로는 **승자 Qwen3 1.2GB 만** 필요하다
  - GPU 는 RTX 3050 **6GB** — fp32 모델 3종이 합쳐 ~7GB 라 **한 프로세스에서 연속 로드하면 VRAM 이 누적돼 마지막 모델이 10배 넘게 느려진다.** `rag.embed.release()` 로 모델마다 내린다
- 테스트: `cd backend && uv run pytest` (의존 방향 가드 + 설정 로딩)
- 필요 키(**`backend/.env`**): LAW_OC ✅ / DATA_GO_KR_KEY ✅ / KAKAO_REST_KEY ✅ / KMA_HUB_KEY ✅ (2026-08-24 전부 발급) — 발급처는 docs/data-sources.md §9, 함정은 아래 파트② 절
  - env 배치는 배포 단위 기준(D-014): 루트 `.env`=인프라(compose), `backend/.env`=백엔드 런타임, `frontend/.env`=프론트
  - 읽는 순서 실제 환경변수 > `backend/.env` > 루트 `.env`. 컨테이너에선 `DAENGS_DATA_DIR` 로 data/ 위치 지정

## 파트② 실시간 — 현재 상태 (2026-08-25)

- **설계 완료** — RT-001 하위 18결정 + **RT-002 하위 3결정** 확정 (`docs/decisions-realtime.md`, `RT-` 는 그 파일에만)
- **구현 9단계 전부 완료.** `feat/realtime` · PR #2 · 테스트 **228 통과/14 skip**
  검문소 **A**(격자 4지점) · **B**(픽스처 파싱 36) · **C**(산식 재현 34) · **D**(저하 경로 15+18) 통과
- **`GET /walk` 가 실서버에서 돈다** — `서초2동 (측정소: 강남대로) 기준` · UNSAFE/heat · 타임라인 25 ·
  권장 구간 `08-25T20:00~08-26T11:00 GOOD` · sources 9/9 · 응답 5KB
- **서빙 계층 배치는 D-027** (공통 결정이라 `RT-` 가 아니다) — MVC2 를 이 레포 사실에 맞춘 것.
  `app/`={controllers,services,dto,deps} · M 은 `realtime/`·`rag/` 그대로 · **`models/` 는 없다**(근거는 D-027)
  강제 규칙은 하나 — **컨트롤러에 로직 0줄**, `test_import_direction_packages.py` 가 기계로 막는다
- **태스크 단일 소스는 PR #2 본문** (`gh pr view 2`). 단계별 근거는 그 ADR 끝의 구현 계획 9단계

```
backend/realtime/
├── config.py geo.py observation.py rules.py thresholds.yaml   ✅
├── transport/  base·datagokr·kakao·kmahub                     ✅
├── providers/  7모듈 (+ stn_inf 해금 → AWS 지점표)             ✅
├── collect.py  조립 — provider 들을 Observations 하나로        ✅ (8)
├── cache.py cache.yaml  ④ 전체 + ⑤-c stale · Redis 없어도 돔  ✅ (8)
backend/tasks/  celery_app · realtime — Beat 프리페치           ✅ (8)
backend/app/    controllers · services · dto · deps  GET /walk  ✅ (9)
backend/main.py 2줄 shim → app.main:app (완전 이동은 병합 뒤)  ✅ (9)
```

- 실행: `docker compose up -d redis` → `cd backend && uv run fastapi run app/main.py` → `GET /walk?lat=&lon=`
  (`fastapi[standard]` 가 주는 CLI 다. `uv run uvicorn app.main:app` 도 같은 것 — `backend/main.py` 는 2줄 shim 이라 `main.py` 로도 뜬다)
  CLI 로도 같은 것: `uv run python -m realtime walk 37.4979 127.0276`
  (`--no-cache` 면 Redis 없이 프로세스 메모리로 — ④-c "없어도 돈다"를 눈으로 보는 자리)
  워커·Beat: `uv run celery -A tasks.celery_app worker --pool=solo` / `... beat`

- ⚠️ **`docs/realtime-apis.md` §6(8/24)보다 코드 주석과 `backend/tests/fixtures/realtime/README.md`(8/25)가 최신이다.**
  8/25 프로브가 §6 을 넷 뒤집었다 — 포맷 파라미터가 계열마다 다름(`dataType` vs `returnType`) ·
  `numOfRows` 상한도 계열마다 다름(기상청 1000 정상 / 에어코리아 504) · apihub typ02 는 실패를
  data.go.kr 봉투로 냄 · 최근접 측정소가 `강남대로`(우리 격자 안, §6.5 의 `강남구`는 밖)
- **사용자 결정 (2026-08-25) — 다시 제안하지 말 것**
  · **data.go.kr 운영계정 전환 안 함. 일 1,000회로 계속 간다** → ④-e 절감 대응 중 **1번(AWS 로 실황 대체)이
    유일한 큰 절감**이고 `stn_inf.php` 에 달려 있다. ④-f 의 `N`=10 은 **운영 상수**
  · **`getUVIdxV3` 는 축에 안 넣는다** (③-b). 신청은 안 했는데 8/25 현재 200 이다 —
    "미신청이라 못 쓴다"는 근거만 사라졌고 **결정은 그대로**다 (§6.9)
- ✅ **블로커 해제 (2026-08-25)** — apihub `stn_inf.php` 활용신청 승인. AWS 745 지점 좌표 확보 →
  역삼 격자 (61,125) 안에 지점 1개(401 서초) 실재 → **⑤-d 1순위·④-e 1번 둘 다 발동 확인** (§6.9)
- ✅ **apihub 생활기상지수 — 신청할 것이 없다.** 남은 403 은 `getAirDiffusionIdxV3` 하나인데
  `kma_life_index` 가 그걸 안 부른다. `getSenTaIdxV3`·`getUVIdxV3` 는 둘 다 200 (§6.9)
- 🟡 **남은 대기 하나: 특보구역명↔행정구역 매핑표.** 없으면 `kma_warning` 이 시도 단축명(`서울`)으로만
  찾아 **구 단위 특보를 놓친다**. `stn_inf` 의 `FCT_ID` 는 동네예보구역이라 대체 불가
- 키 3종 발급 완료. 함정: data.go.kr 은 **Decoding 키**(`config.normalize_key` 가 `%` 보고 1회 디코딩) ·
  카카오는 `제품 설정 > 카카오맵` **활성화** · apihub 활용신청은 **오퍼레이션 단위**
