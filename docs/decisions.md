# 설계 결정 기록 (Decision Log)

> 상태: ✅ 확정 · 🔶 제안(논의중) · ⏸ 보류. 결정이 뒤집히면 지우지 말고 상태 변경 + 사유 추가.

---

## D-001. 크롤링 오케스트레이션: Celery + Beat (+ Redis) — ✅ 확정 (2026-08-19)

**배경** — 크롤링 시스템화 요구사항 3개: ① 주기 실행 ② 관리자페이지 수동 트리거 ③ 원하는 소스만 선택 실행. 팀 초기 안은 Airflow.

**결정** — Celery(작업 큐) + Celery Beat(스케줄러) + Redis(브로커·결과 백엔드). FastAPI 백엔드와 같은 코드베이스/이미지 사용.

**근거**
- 요구사항의 실체는 "작업 큐 + 스케줄러 + 실행 이력"이지 워크플로 엔진이 아님 — 태스크 의존성 그래프가 없고, cadence는 cron 표현식 몇 개 수준
- Airflow는 고정비(상주 RAM 1~2GB, logical date/catchup 등 개념 학습, 느린 개발 루프)가 규모(소스 30개, 하루 몇 회) 대비 과함
- 성능은 두 안이 갈리지 않음 — 병목은 크롤링 자체(요청 간격 1~2초의 네트워크 I/O, PDF 파싱, 임베딩)
- Redis는 실시간 조회형 파트에서 API 응답 TTL 캐시로 재활용 예정 (컨테이너 하나, 두 역할)
- Kafka는 브로커로 부적합: 오프셋 기반 스트림 로그 모델 vs 태스크별 ack/재큐잉 의미론 불일치, Celery 공식 미지원

**대안 요약**

| | APScheduler | Celery+Beat (채택) | Airflow |
|---|---|---|---|
| 추가 인프라 | 0 | Redis + worker + beat | 스케줄러+웹서버+메타DB |
| 재시도/이력 UI | 직접 구현 / ❌ | 데코레이터 / △(Flower) | ✅ / ✅ |
| 리스크 | 백엔드 재시작 시 작업 소실 | 이력 직접 기록 필요 | 무게·학습 곡선 |

**구현 시 준수할 아키텍처 원칙**
1. `crawler/`는 오케스트레이터 무관 순수 파이썬 패키지 + CLI(`python -m crawler run --source X`). Celery 태스크는 호출만 — 갈아타기 비용 ≈ 0
2. fetch(원본 수집)와 index(청킹→임베딩→적재) 태스크 분리. 콘텐츠 sha256으로 변경 감지 → 무변경 문서는 재임베딩 스킵
3. 실행 이력은 Postgres `crawl_runs` 테이블(source_id, status, docs_fetched, docs_changed, error, started_at, finished_at). 관리자페이지는 이 테이블을 읽음(Flower는 운영 보조)
4. 소스별 cadence는 seed_sources.yaml에 스케줄 힌트로: 공고 daily / 안내페이지 weekly / 약관 quarterly / 법령 manual. Beat는 "due 소스 선별" 태스크 하나만 주기 등록, 수동 트리거는 `source_ids` 인자로 같은 경로를 override
5. 소스당 독립 태스크 — 한 소스 실패가 전체를 막지 않음. `autoretry_for` + 지수 백오프(max_retries=3)
6. 관리자 트리거 흐름: Next.js → FastAPI `POST /admin/crawl {source_ids}` → 태스크 `.delay()` → 상태는 crawl_runs 폴링

**compose 토폴로지** — `redis` / `backend`(FastAPI) / `worker` / `beat`. worker·beat는 backend와 동일 이미지, command만 상이. broker=`redis://redis:6379/0`, result_backend=`redis://redis:6379/1`

**트레이드오프 수용** — 실행 이력 UI 부재 → crawl_runs 자체 구현(관리자페이지용으로 어차피 필요). Celery 워커의 Windows 네이티브 미지원 → 도커 실행(기존 방침과 동일)

---

## D-002. 임베딩 모델 — 🔶 제안 (논의중 · 8/19 심화 논의 반영)

제안: 개발 기본값 = **gemini-embedding-001**(`output_dimensionality=1024`) → **골든셋(D-007) 완성 시 3파전 베이크오프로 확정**: gemini@1024 vs KURE-v1(로컬, 1024 네이티브, 한국어 파인튜닝) vs BGE-M3. 리더보드(MTEB-ko)는 참고만 — 법령·행정 문체는 니치 도메인이라 자체 골든셋 측정이 유일한 진실이고, 규모가 작아 전 코퍼스 재임베딩이 저비용이므로 실측 비교가 합리적. 베이크오프는 프로드 테이블 밖 오프라인 스크립트로 (Hit@5/MRR 비교).

구현 주의사항:
- gemini: 1024 축소 시 정규화가 풀림 → **저장 전 L2 정규화 필수** / `task_type`을 문서=`RETRIEVAL_DOCUMENT`, 질의=`RETRIEVAL_QUERY`로 구분 지정(구어 질문 ↔ 법령체 문서 비대칭 대응) / 최대 입력 2,048토큰
- multilingual-e5-large는 최대 512토큰 — 청크(300~800tk)와 충돌 가능 → EDA(D-006) 길이 분포로 생사 판정, 사실상 후보 제외 유력
- 어떤 모델이든 `metadata.embedding_model` 기록 — 한 컬럼에 모델 혼입 금지

## D-003. 검색 구성 (하이브리드·리랭커) — 🔶 제안 (논의중)

제안: v1 = 하이브리드 — pgvector dense + **Kiwi(kiwipiepy) 형태소 토큰화 → tsvector('simple') + GIN** lexical, **RRF(k=60)** 융합, 메타데이터 사전 필터(category·지역·시행일). 근거: 법률·행정 질의는 정확 용어("입마개", "제15조")가 승부처 — PG 기본 FTS는 한국어에 약해 형태소 토큰화 우회 필요. 리랭커는 `retrieve → (rerank) → generate`의 옵셔널 스테이지로 설계만 해두고 평가셋 recall@5 측정 후 도입 결정(후보: bge-reranker-v2-m3 로컬 / Cohere Rerank 3.5 API).

## D-004. 청킹 — 🔶 제안 (논의중)

제안: 구조 우선. 법령·약관 = 조문 단위(1청크=1조문, 긴 조는 항 분할, `section`="제16조제2항"), HTML = 헤딩 단위, 공고 = 문서 통짜. 모든 청크에 컨텍스트 헤더 부착(`[동물보호법 제16조(…) | 시행 2024-04-27]`). 300~800토큰, 오버랩은 비구조 텍스트만 10~15%. 조문 경계를 넘는 고정 크기 분할 금지(조항 인용 KPI 훼손).

## D-005. 실행 순서 — 🔶 제안 (논의중)

제안: Phase 1 크롤러(키 불필요 소스) → 평가셋 40문항(도메인당 6~8, 질문↔정답 조문) → 청킹·임베딩·적재 → 하이브리드 검색 → 평가 → (headroom 시) 리랭커. 모든 모델·파라미터 선택은 평가셋 지표(Recall@5, MRR, 인용 정확도)로 판단.

---

## D-006. 코퍼스 EDA 시스템화 — 🔶 제안 (2026-08-19 논의)

일회성 노트북이 아니라 **`crawler stats` 서브커맨드**로 만들어 재적재 때마다 마크다운 "코퍼스 카드" 리포트가 자동 갱신되게 한다. 각 항목은 특정 결정의 입력:

| 항목 | 먹여줄 결정 |
|---|---|
| 문서 인벤토리 (도메인×포맷×건수) | 커버리지 확인, 수집 우선순위 |
| 조문/청크 토큰 길이 분포 p50/p95/max (실사용 모델 토크나이저로 측정) | 청크 크기, 항 분할 임계, e5(512)·gemini(2048) 입력 한도 판정 |
| 구조 파싱 성공률·표 빈도 | PDF 파서 선택, Gemini 폴백 예산, 문제 문서 리스트 |
| **스캔 PDF 비율 (텍스트 레이어 유무)** | **최대 복병 후보** — 지자체 공고 스캔본 → OCR(Gemini vision) 적용 범위 |
| 중복·개정판 탐지 (해시+유사도) | 중복 제거·버저닝 정책 |
| 용어 갭 정성 샘플 (구어 vs 법령체) | 하이브리드 가중치, 질의 재작성 필요성 |
| (임베딩 후) 도메인 클러스터 정합성, cos>0.95 쌍 | 이상 청크 탐지 |

타이밍: Phase 1 크롤 직후 1차 실행. 리포트 스키마는 크롤러 구현 시 함께 확정.

## D-007. 품질 평가 체계 및 자동화 — 🔶 제안 (2026-08-19 논의)

**원칙: 검색 평가(결정적·저비용)와 생성 평가(LLM judge·고비용)를 분리하고 검색부터 조인다.** RAG 실패 대부분은 검색 실패.

**골든셋** (`data/eval/golden_v1.jsonl`, git 관리)
- 정답 단위 = **(문서 ID + 조항번호 section)**. 청크 ID로 잡으면 청킹 변경 시 전량 무효 — 평가 시점에 청크로 매핑해 청킹 실험에도 골든셋 불변
- 도메인당 6~10개, 총 40~60(v1). 질문 유형 배분: ① 사실 단답 ② 구어 패러프레이즈(dense 테스트) ③ 정확 용어·조문(lexical 테스트) ④ 조건 복합(메타필터 테스트) ⑤ 멀티 문서 ⑥ **무답 질문**(abstention 테스트)
- LLM 보조 생성 시 표면 중복 편향 주의("문서 어휘 쓰지 말 것" 지시) + 사람 검수 필수

**검색 지표** — 주력 **Hit Rate@5**(k는 생성 투입 개수와 일치) + **MRR**(순위 민감 → 리랭커 효과 판정기, D-003 도입 여부를 이 지표로 결정). nDCG는 이진 라벨이라 v1 스킵. **보고는 전체 평균 + 도메인×질문유형 슬라이스 필수** (평균에 숨는 실패 검출)

**LLM-as-a-judge** (루브릭 4종, rationale→verdict 순서의 JSON, temperature 0)
1. Faithfulness — 답의 주장 분해 후 컨텍스트 근거 확인 (환각 검출)
2. **인용 정확도(1번 KPI) — 3단 반자동**: 정규식으로 인용 추출 → DB 실존 검증(rule, judge 불필요) → 해당 조항이 주장을 지지하는지만 judge
3. 답변 정확성 (참조 답안 대비)  4. Abstention (무답 질문에 정직한 "규정 없음")
- judge 위생: 생성·judge 모델 급 분리(예: flash 생성 → pro judge) / **사람 라벨 30개와 일치율로 judge 캘리브레이션 후 신뢰** / judge 프롬프트·모델 버전 고정, 변경 시 재캘리브레이션

**자동화**
- `python -m eval run --config exp.yaml` → `results/{run_id}.json` + report.md (git 커밋). 기록 = git sha + 코퍼스 스냅샷 + config + 전 지표 (재현성 삼각형)
- 회귀 게이트 2단: **smoke**(고정 미니 코퍼스, 검색 지표만, CI/PR마다 수 분) + **full**(전체 코퍼스 + judge, 수동·야간)
- 운영 연동: 재적재 완료 → Celery chain으로 검색 eval 자동 실행 → baseline 대비 Hit@5 3%p 하락 시 알림, 관리자페이지에 지표 트렌드
- 도구: ragas/deepeval 참고만 하고 자체 구현 (지표 특수성 — 인용 정확도 — 및 투명성)

---

## D-008. 데이터 저장 규약 및 documents 스키마 정정 — ✅ 확정 (2026-08-19)

**배경** — `data/README.md`(저장 규칙)와 `db/init/01_schema.sql`(스키마)을 대조하니 어긋난 지점이 여럿이었다.
main에서 별도로 진행된 스키마 검토 결과를 이 브랜치 규약과 합치면서 아래 9건을 확정한다.
데이터 적재 전이므로 스키마는 `DROP TABLE documents CASCADE;` 후 `01` → `02` 재실행으로 반영한다.

### 1) 원본은 git에 커밋하지 않는다 — 기존 방침 변경

`raw/`의 원본(pdf/html/xml/json)과 `processed/` 전체를 gitignore하고, **`.meta.json`만 커밋**한다.

- 이 레포는 public이다. 정부 자료는 공공누리로 재배포되지만 **펫보험 약관은 보험사 저작물**이라 리스크가 있다 (시드에 insurance 3건)
- D-007이 요구하는 "코퍼스 스냅샷"은 `.meta.json`의 `source_url`+`sha256`+`fetched_at`으로 충족된다. 원본 바이트 자체가 필요한 게 아니다
- 기존의 "파일당 100MB 금지" 규칙은 원본 커밋을 전제한 것이라 함께 폐기

**수용하는 트레이드오프** — 공고문이 내려가면 원본 재취득이 불가능하다. 로컬 `raw/`를 보존 대상으로 취급한다.

### 2) `.meta.json`과 크롤 로그는 역할이 다르다 — 둘 다 유지

`.meta.json` = 문서의 **출처 정보**(인덱싱 게이트) / `manifests/crawl_log.jsonl` = **실행 이력**(재실행 판단).
사이드카만으로는 404·타임아웃을 기록할 곳이 없다(파일이 안 생기므로 meta도 없음) → 죽은 URL을 매번 재시도하게 된다.
JSONL인 이유는 배열과 달리 크롤 중단 시 파일이 깨지지 않아서다.

층위 구분: `crawl_log.jsonl`은 **문서 단위**, D-001 원칙3의 `crawl_runs` 테이블은 **실행 단위**(관리자페이지용).

### 3) `category`에서 `care`·`emergency` 제외

`CHECK (category IN ('policy','travel','food'))`.
진단 성격이 강해 별도 에이전트로 분리한다. `emergency`(응급처치·중독)도 `care`보다 의료적이라 같이 뺐다.
이 레포의 파트는 제도·문서형이다. 필요해지면 제약만 교체하면 되고, 에이전트가 달라도 테이블을 나눌 필요는 없다(category 필터로 격리).

**"예방접종 스케줄 → care" 매핑은 폐기.** `policy` + `trust_level: guideline`으로 대체한다 —
`guideline`은 원래 "접종 스케줄처럼 법정 근거가 없는 문서" 구분용으로 만든 등급이라 역할이 겹쳤다.

### 4) 신뢰 등급은 `trust_level` 유지 (`law` > `official` > `guideline`)

main 검토안의 `authority`(official/expert/community)보다 이 도메인에 정확하다.
**법령 원문과 기관 안내페이지를 구분**하는 것이 조항 인용 KPI에 직결되는데 3단계 안은 둘을 뭉갠다.
블로그·유튜브 도입 시 `community`를 추가한다.

### 5) `source_type`은 매체 축으로 통일 — `pdf` → `document`

`CHECK (source_type IN ('document','web','api','manual'))`.
기존 값은 포맷 축(`pdf`)과 수집 채널 축(`web`,`api`)이 섞여 "웹에서 받은 PDF"의 답이 없었고,
지금 타깃인 정부 공고문이 정확히 그 케이스다. 세부 포맷은 `metadata.format`(`pdf|hwp|hwpx|html|xml|json`)이 담당한다.

`video`/`audio`는 넣지 않는다 — 현재 시드 30개에 영상·음성 소스가 없다. 실제 수집 시 추가.
포맷을 CHECK가 아니라 metadata에 둔 이유: 포맷은 계속 늘어나(xlsx, pptx…) 그때마다 ALTER가 필요해진다.
`WHERE metadata @> '{"format":"hwp"}'` 는 기존 GIN 인덱스로 처리된다.

### 6) `documents.content_hash` 컬럼 신설

`content_hash CHAR(64) NOT NULL UNIQUE` — 청크 텍스트의 SHA-256. `ON CONFLICT (content_hash) DO NOTHING`으로 멱등 적재.
기존 스키마에는 중복을 막을 키가 없어 로더를 두 번 돌리면 행이 2배가 됐다.
NOT NULL이 필수인 이유: SQL에서 NULL끼리는 중복으로 취급되지 않아 해시가 비면 방어가 조용히 뚫린다.
metadata에 넣지 않은 이유: JSONB는 NOT NULL·타입을 강제할 수 없고 `\d documents`에도 안 보인다.

**D-001 원칙2의 해시와 층위가 다르다** — 원본 문서 해시(`.meta.json`)는 재파싱·재임베딩 스킵 판단,
청크 해시(이 컬럼)는 중복 적재 방지. 둘 다 필요하다.

### 7) `subcategory` 표기는 kebab-case, 값은 수집하면서 늘린다

CHECK 제약 없음. `raw/` 하위 폴더명과 표기를 맞춘다(`leash-muzzle`).
값 사전은 "확정 목록"이 아니라 **"지금까지 쓴 값의 기록"** 으로 운용한다 —
실제 문서를 보기 전에 짠 분류는 대개 어긋나고, 재분류는 `UPDATE` 한 줄이며 `content`가 안 바뀌므로 **임베딩 재계산이 불필요**하다.

### 8) 가공 산출물은 단계별로 분리

`processed/` 를 `parsed/`(텍스트 추출) → `chunks/`(청킹) → `embeddings/`(벡터)로 나눈다.
파서를 교체하면 `parsed/`부터, 청크 크기를 바꾸면 `chunks/`부터만 다시 돌리면 되고 크롤링은 재실행하지 않는다.
**D-006의 "구조 파싱 성공률"·"스캔 PDF 비율"은 `parsed/` 산출물이 따로 남아야 측정 가능하다.**
포맷은 jsonl(디버깅·diff 용이), 1024차원 벡터만 parquet.

### 9) 대량 문서 소스의 파일명 보완

기본은 기존 규칙 `{slug}__{YYYYMMDD}.{ext}`.
지자체 공고처럼 한 소스에서 문서가 수십 개 쏟아져 slug를 개별 부여할 수 없는 경우
`{source_id}__{YYYYMMDD}__{urlhash8}.{ext}` (`urlhash8` = `sha256(url)[:8]`)를 쓴다.
원래 파일명을 못 쓰는 이유: 공공기관 첨부는 `공고문.pdf`·`붙임1.pdf` 처럼 겹쳐 덮어쓰고,
URL에 한글·쿼리스트링이 섞여 Windows 경로로 부적합하다.

**미결 (이 결정에 포함하지 않음)** — PDF 파서 선택(pypdf/pdfplumber/PyMuPDF)은 후보와 판단 재료만
`data/README.md`에 정리해두고 파싱 단계 착수 시 결정한다. PyMuPDF의 AGPL-3.0이 변수.
