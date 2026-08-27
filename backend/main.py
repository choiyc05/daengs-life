"""ASGI 진입점 shim — 실물은 `app/main.py` 에 있다 (RAG-027).

이 파일을 남겨 두는 이유는 둘이다. `fastapi dev main.py` 같은 기존 실행 명령이 안 깨지고,
`feat/rag` 가 병렬로 살아 있는 동안 rename-vs-modify 충돌을 만들지 않는다.
두 브랜치가 합쳐지면 RAG-009 대로 정리한다.
"""
from app.main import app

__all__ = ["app"]
