# daengs-life — 강아지 생활 비서 AI (개인 파트 레포)

팀 프로젝트 중 내 파트만 작업하는 레포. 파트 2개:
1. **제도·문서형 RAG** — 동물등록/예방접종/목줄·입마개(맹견)/동반이동/지자체지원/펫보험. **KPI = 답변에 출처 링크 + 조항 번호 인용**
2. **실시간 조회형** — 산책 적합 날씨·미세먼지 (GPS 기반, 실질 해상도는 동 단위가 상한)

## 작업 방식 (중요)
- 파트별 **논의 → `docs/decisions.md`에 결정 기록(ADR) → 구현** 순서. 사용자가 명시하기 전에 구현으로 넘어가지 말 것
- 결정 상태: ✅ 확정 / 🔶 제안(논의중). 논의 결과는 decisions.md에 반영하고 커밋
- 크롤링 산출물은 `data/` (규칙: `data/README.md` — 원본 불변, `.meta.json` 필수, meta 없으면 인덱싱 금지)
- 조사·설계 문서는 `docs/` (인덱스: `docs/README.md`)
- 브랜치에서 작업 후 커밋+푸시 (현재: `feat/data-sources`)

## 스택
- backend: FastAPI + uv (Python), LLM은 Gemini API 예정
- DB: postgres + **pgvector 0.8.6** — `documents` 테이블: `embedding vector(1024)`, category CHECK(policy/food/care/travel/emergency), source_url/document_title/section 컬럼 (조항 인용용)
- 오케스트레이션: **Celery + Beat + Redis** (D-001 확정 — Airflow 아님)
- frontend: Next.js (단순 확인용)
- 로컬: `docker compose up -d` (컨테이너 `daengs_life_db`, DB명 `lifedb`, init은 `db/init/`)

## 현재 상태 (2026-08-19 기준)
- 완료: 데이터 소스 조사(`docs/data-sources.md`, 시드 30개 `data/manifests/seed_sources.yaml`), 실시간 API 조사+GPS 결론(`docs/realtime-apis.md`), D-001 오케스트레이션 확정, DB 기동·스키마 검증
- 논의중(🔶): D-002 임베딩(gemini@1024 기본값→골든셋 3파전 베이크오프), D-003 하이브리드·리랭커, D-004 청킹(조문 단위), D-005 실행순서, D-006 EDA 시스템화, D-007 평가 체계(Hit@5·MRR·LLM judge)
- 다음 후보: 남은 결정 확정 → Phase 1 크롤러(키 불필요 소스: easylaw·animal.go.kr 등) + Celery 뼈대(crawler 패키지 분리 원칙은 D-001 참고)
- 필요 키(.env, 미발급): DATA_GO_KR_KEY, LAW_OC, KAKAO_REST_KEY — 발급처는 docs/data-sources.md §5
