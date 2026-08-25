# docs/

| 문서 | 내용 |
|---|---|
| [decisions.md](decisions.md) | 설계 결정 기록 (ADR) — D-002 임베딩 후보 3종 확정·D-004 청킹 실측 근거·D-001 오케스트레이션(Celery+Beat)·D-008 저장 규약/스키마·D-009 크롤러 배치/소스 계약·D-010 원본 부재 시 재수집·D-011 법령 웹 원문 수집 경로·D-012 소스 도메인 분류/API 키 규칙·D-013 MCP 미채택·D-014 env 배치/의존방향 가드·D-015 pydantic-settings·D-016 법령 API 수집 완료·D-017 data 전체 미추적 확정·D-018 인덱싱 패키지 경계/파서 3층/공통 IR 6종·D-019 parsed 산출물 규약(파일 단위/ID 층/출처 링크)·D-020 별표 괘선표 셀 격자 파싱·D-021 청커 5결정 확정(입력범위·길이기준·content조립·폴백없음·산출물규약)·**D-022 골든셋 6결정(필수/보강 2층·법제처 `관련 법령` 라벨 차용·15문항/필수 43·코퍼스 밖 분모 제외·수집 날짜를 뺀 논리 주소)**·**D-023 `rag/` 배치(순서 있는 것 `stages/` / 없는 것 `core/` / `pipeline.py` 가 순서의 단일 소스 — 파일 이름에 단계 번호를 박지 않는다)**·**D-024 6단계 3파전 4결정(사전 등록/기준선 우선·판정 k=5·탈락선은 Hit@5 2문항 차·Recall/MRR 은 기록만·덤프 미추적/판정은 ADR 에)**·**D-025 7단계 적재 5결정(upsert+한 트랜잭션·psycopg3/SQL 직접·중복은 대표+merged_from·source 를 파서·청커에 실음·임베딩 지문을 (chunk_id,content) 로)**·**D-026 8단계 검색 CLI(부칙은 기본 포함·필터는 플래그 — 검사 도구와 서빙의 기본값은 다르다 / 검색은 stages/search.py 하나, CLI 는 출력만)**, D-003·D-005~007 논의중 |
| [data-sources.md](data-sources.md) | 제도·문서형 RAG 데이터 소스 **수집 체크리스트** — 파트별 소스 30개 진행 현황, 키 발급·요확인 체크, Phase 전략 |
| [realtime-apis.md](realtime-apis.md) | 실시간 조회(날씨·대기질) API 정리 + GPS 정밀도 결론 + 산책지수 입력 매핑 (2026-08-19) |
| [workflow.md](workflow.md) | **작업 방식** — 우선순위 P0~P3 기준 · 스프린트 기간 → 실작업량 산식 · PR 을 작업 전에 올리는 운영 규칙 · 사람/AI 경계. 태스크와 P0/P1 **배정**은 여기가 아니라 **해당 브랜치의 PR 본문**이 단일 소스 (2026-08-24) |

데이터 저장 규칙: [../data/README.md](../data/README.md)
시드 소스 목록: [../data/manifests/seed_sources.yaml](../data/manifests/seed_sources.yaml)
