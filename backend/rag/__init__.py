"""rag — 제도·문서형 RAG 파트①의 인덱싱 엔진 (D-018).

  data/raw  ──parse──▶  processed/parsed  ──chunk──▶  processed/chunks
            ──embed──▶  processed/embeddings  ──load──▶  postgres  ──search──▶  app

`crawler` 는 수집만 한다. 이 패키지는 그 산출물을 검색 가능한 형태로 바꾼다.
의존 방향은 `app → rag → crawler` 한쪽뿐이고 `tests/test_import_direction.py` 가 지킨다.
"""
