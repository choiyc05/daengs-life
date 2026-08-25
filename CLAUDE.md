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
- 브랜치에서 작업 후 커밋+푸시. 현재 병렬 2개: `feat/rag`(파트① 3단계 청커) · `feat/realtime`(파트② 8단계 완료, 9단계 남음)

## 스택
- backend: FastAPI + uv (Python), LLM은 Gemini API 예정. **`backend/` 는 uv 프로젝트 하나**이고 그 안에 패키지가 다섯으로 나뉜다 (D-018 · D-027): `crawler/` 수집 · `rag/` 인덱싱(parse→chunk→embed→load→search) · `realtime/` 실시간 · `tasks/` Celery 워커·Beat · `app/` 서빙(controllers·services·dto). 의존 방향은 **app→{rag,realtime}→crawler** 한쪽뿐이고 `tests/test_import_direction*.py` 둘이 막는다 (방향 + **범위**).
  실행: `cd backend && uv run python -m crawler run --source <id>` / `uv run python -m rag parse`
- 로컬 인프라: `docker compose up -d` — `db`(postgres+pgvector) · **`redis`**(D-001 브로커·캐시, RT-001 ④ 가 첫 사용처)
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
  **D-018 인덱싱 패키지 경계(`backend/rag/`)·파서 3층·공통 IR 6종** / **D-019 parsed 산출물 규약** / **D-020 별표 표 파싱**
- 논의중(🔶): **D-021 청커 5결정 — ①입력범위 ✅확정 / ②길이기준 B안 잠정 / ③~⑤ 미논의** (진행중, 여기부터 재개) /
  D-003 하이브리드·리랭커, D-005 실행순서, D-006 EDA 시스템화, D-007 평가 체계
- **다음 목표: 수집한 28건 전부로 RAG 한 세트 관통** (아래 9단계). 소스 추가는 그 뒤로 미룸
- ⚠️ `data/` 는 미추적(D-017)이라 **PC 마다 상태가 다르다.** 새 PC 에서는 `backend/.env` 에 LAW_OC 를 넣고
  4소스(`easylaw-pet`·`law-animal-protection`·`law-livestock-epidemic`·`law-drf-api`)를 재수집 → `rag parse` 하면
  28건/22 parsed 가 복원된다 (2026-08-22 실제로 복원, 요소 수 동일 재현 확인)

### RAG 관통 실행 순서
1. ~~**D-004 확정**~~ ✅ 2026-08-20 — 질문 1~7 정답 위치를 원문에서 확인, 구조 기반 전략 + 판정표 확정
2. ~~**파서**~~ ✅ 2026-08-21 — `backend/rag/` 신설, `processed/parsed/*.jsonl` **22건** (article 629 · para 552 · table 89 · heading 97 · aside 27 · qa 10). 서식 126건·웹 원문 6건 제외
3. **청커** ← **지금 여기.** 규칙 논의가 D-021 (①확정 ②잠정 ③~⑤ 미논의) → 확정 후 `rag/chunk.py` 구현 →
   `data/processed/chunks/*.jsonl` · **검문소① 질문 1~7의 정답 청크가 하나씩 실재하는지 눈으로 확인**
4. **임베딩 3종** → `data/processed/embeddings/{model}.parquet` (DB 밖 오프라인, D-002)
   `BAAI/bge-m3`(기준선) · `nlpai-lab/KURE-v1`(한국어 튜닝, bge-m3 파생) · `Qwen/Qwen3-Embedding-0.6B`(계열 다름+영어) — 셋 다 1024 native
5. **골든셋 시드** — 질문 7개 + easylaw Q/A 7개 = 14건
6. **3파전 비교**(Hit@5·MRR) · **검문소② 명백히 나쁜 것만 거름** (14건이라 통계적 판정은 불가)
7. **승자 1종만 DB 적재** (`documents`, `embedding_model` 기록)
8. **검색 CLI (dense만)** · **검문소③ top-5 눈으로 확인** — 하이브리드·리랭커는 D-003으로 미룸
9. **LLM 생성**(Gemini) → 이후 FastAPI `/ask` → (선택) Next.js

검증용 질문 10개 (1~7만 소스 확보됨):
1. 강아지 등록 안 하면 어떻게 되나요 / 2. 등록정보 변경 언제까지 신고 / 3. 목줄 안 하면 과태료 얼마 /
4. 로트와일러인데 맹견인가요 / 5. 맹견 사육 허가 필요한가요 / 6. 광견병 접종 의무인가요 /
7. 국립공원에 강아지 가능한가요 / ~~8. KTX~~ ~~9. 서울 지원금~~ ~~10. 펫보험 슬개골~~ (소스 미수집)

준비물: `GEMINI_API_KEY`(9단계) · `uv sync --group ml`(4단계, torch) · 모델 3종 디스크 ~6GB
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

- 실행: `docker compose up -d redis` → `cd backend && uv run uvicorn main:app` → `GET /walk?lat=&lon=`
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
