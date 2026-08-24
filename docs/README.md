# docs/

| 문서 | 내용 |
|---|---|
| [decisions.md](decisions.md) | 설계 결정 기록 (ADR) — **공통 인프라 + 파트① (`D-`)**.  D-002 임베딩 후보 3종 확정·D-004 청킹 실측 근거·D-001 오케스트레이션(Celery+Beat)·D-008 저장 규약/스키마·D-009 크롤러 배치/소스 계약·D-010 원본 부재 시 재수집·D-011 법령 웹 원문 수집 경로·D-012 소스 도메인 분류/API 키 규칙·D-013 MCP 미채택·D-014 env 배치/의존방향 가드·D-015 pydantic-settings·D-016 법령 API 수집 완료·D-017 data 전체 미추적 확정·D-018 인덱싱 패키지 경계/파서 3층/공통 IR 6종·D-019 parsed 산출물 규약(파일 단위/ID 층/출처 링크)·D-020 별표 괘선표 셀 격자 파싱·D-021 청커 5결정, D-003·D-005~007 논의중 |
| [data-sources.md](data-sources.md) | 제도·문서형 RAG 데이터 소스 **수집 체크리스트** — 파트별 소스 30개 진행 현황, 키 발급·요확인 체크, Phase 전략 |
| [realtime-apis.md](realtime-apis.md) | 실시간 조회(날씨·대기질) API 정리 + GPS 정밀도 결론 + 산책지수 입력 매핑 (2026-08-19) |
| [decisions-realtime.md](decisions-realtime.md) | **파트② 설계 결정 기록 (`RT-`)** — RT-001 실시간 엔진 6결정(①계층 ✅확정: 전송 층 `transport/` 3 · provider 층 `providers/` 7 분리, `realtime`→`crawler.core.config` 참조 허용 + 가드 2건 / ②~⑥ 미논의). **번호를 `D-` 와 나눈 이유는 그 파일 헤더에** |
| [workflow.md](workflow.md) | **작업 방식** — 우선순위 P0~P3 기준 · 스프린트 기간 → 실작업량 산식 · PR 을 작업 전에 올리는 운영 규칙 · 사람/AI 경계. 태스크와 P0/P1 **배정**은 여기가 아니라 **해당 브랜치의 PR 본문**이 단일 소스 (2026-08-24) |

데이터 저장 규칙: [../data/README.md](../data/README.md)
시드 소스 목록: [../data/manifests/seed_sources.yaml](../data/manifests/seed_sources.yaml)
