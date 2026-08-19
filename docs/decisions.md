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

## D-002. 임베딩 모델 — 🔶 제안 (논의중)

제안: v1 = **gemini-embedding-001** (`output_dimensionality=1024`, 축소 시 정규화가 풀리므로 **저장 전 L2 정규화 필수**) → 평가셋 확보 후 KURE-v1(로컬, 1024 네이티브, 한국어 특화)과 A/B. 스키마가 `vector(1024)` 고정이므로 후보는 1024 호환만: gemini(축소)/KURE-v1/BGE-M3/multilingual-e5-large. 어떤 모델이든 `metadata.embedding_model` 기록 — 한 컬럼에 모델 혼입 금지.

## D-003. 검색 구성 (하이브리드·리랭커) — 🔶 제안 (논의중)

제안: v1 = 하이브리드 — pgvector dense + **Kiwi(kiwipiepy) 형태소 토큰화 → tsvector('simple') + GIN** lexical, **RRF(k=60)** 융합, 메타데이터 사전 필터(category·지역·시행일). 근거: 법률·행정 질의는 정확 용어("입마개", "제15조")가 승부처 — PG 기본 FTS는 한국어에 약해 형태소 토큰화 우회 필요. 리랭커는 `retrieve → (rerank) → generate`의 옵셔널 스테이지로 설계만 해두고 평가셋 recall@5 측정 후 도입 결정(후보: bge-reranker-v2-m3 로컬 / Cohere Rerank 3.5 API).

## D-004. 청킹 — 🔶 제안 (논의중)

제안: 구조 우선. 법령·약관 = 조문 단위(1청크=1조문, 긴 조는 항 분할, `section`="제16조제2항"), HTML = 헤딩 단위, 공고 = 문서 통짜. 모든 청크에 컨텍스트 헤더 부착(`[동물보호법 제16조(…) | 시행 2024-04-27]`). 300~800토큰, 오버랩은 비구조 텍스트만 10~15%. 조문 경계를 넘는 고정 크기 분할 금지(조항 인용 KPI 훼손).

## D-005. 실행 순서 — 🔶 제안 (논의중)

제안: Phase 1 크롤러(키 불필요 소스) → 평가셋 40문항(도메인당 6~8, 질문↔정답 조문) → 청킹·임베딩·적재 → 하이브리드 검색 → 평가 → (headroom 시) 리랭커. 모든 모델·파라미터 선택은 평가셋 지표(Recall@5, MRR, 인용 정확도)로 판단.
