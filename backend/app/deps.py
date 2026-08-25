"""의존성 주입 (D-027).

**이 파일이 있는 이유는 둘이다.**

1. `Cache` 는 Redis 커넥션 풀을 들고 있다 — 요청마다 만들면 풀이 요청 수만큼 생긴다.
   프로세스에 하나만 두고 돌려 쓴다.
2. **테스트가 여기를 갈아끼운다.** 검문소 D 를 API 레벨에서 다시 돌리려면 죽은 provider 를
   가진 캐시를 넣을 수 있어야 하고, 그 자리가 FastAPI 의 `dependency_overrides` 다.
   전역 싱글턴을 모듈 상수로 두면 그게 불가능해진다.
"""
from __future__ import annotations

from datetime import datetime
from functools import lru_cache

from realtime.cache import Cache
from realtime.config import KST


@lru_cache(maxsize=1)
def get_cache() -> Cache:
    """프로세스당 하나. `Cache()` 가 Redis 연결을 시도하고, 실패하면 메모리로 떨어진다 (④-c)."""
    return Cache()


def get_now() -> datetime:
    """지금. **주입하는 이유는 테스트다** — 컨트롤러가 `datetime.now()` 를 직접 부르면
    API 테스트가 그날의 실제 시각(과 픽스처의 예보 구간)에 묶여, 내일 이유 없이 깨진다.
    판정이 시각의 함수라는 ③-a 가 여기서도 그대로 값어치를 한다.
    """
    return datetime.now(KST)


__all__ = ["get_cache", "get_now"]
