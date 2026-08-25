"""기상청 생활기상지수 (apihub typ02) — 체감온도 대조용 · 자외선지수.

**우리 산식을 검산할 수단이다.** ③-c 는 체감온도를 자체 계산하기로 했고(행정구역·발표시각
단위라 시각별 판정에 안 맞는다), 이 API 는 같은 값의 **공식 계산**을 준다. 값이 잡히면
우리 산식과 대조할 수 있다 — §6.8 이 "근거가 바뀐다"고 적은 자리다.

싣는 것은 **`Q.UV` 뿐이다.** 체감온도는 `Q` 에 없다 (②-d-3 결정 2) — 파생량이라 `source` 가
"우리"가 되고, 그러면 "이 값이 어디서 왔나"가 흐려진다. 여기서 받은 공식 체감온도는 관측이
아니라 **대조값**이므로 `Measurement` 가 아니라 그대로 돌려준다.

⚠️ 현재 상태 (2026-08-25 실측)
  `getSenTaIdxV3` 활용신청 ✅ 통과(403 이 아니다) — 그런데 **`03 NO_DATA`** 다.
                 유효한 발표시각·지역 조합을 아직 못 찾았다 (§6.8 ③)
  `getUVIdxV3`   **오퍼레이션 단위 활용신청 대기.** 같은 서비스 아래인데도 따로 신청해야 한다
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from ..config import KST
from ..observation import Measurement, Q, Source
from ..transport import kmahub
from ..transport.base import Budget

PATH = "/api/typ02/openApi/LivingWthrIdxServiceV3"

# 응답이 `h1`~`h78` 처럼 **발표시각으로부터 몇 시간 뒤인지**를 필드 이름에 담는다.
_OFFSET_PREFIX = "h"


def _items(payload: Any) -> list[dict]:
    body = ((payload or {}).get("response") or {}).get("body") or {}
    items = body.get("items")
    if isinstance(items, dict):
        items = items.get("item")
    if isinstance(items, dict):
        return [items]
    return items or []


def parse_uv(payload: Any, area: str) -> list[Measurement]:
    """자외선지수 — `hN` 필드가 발표시각 +N시간의 값이다.

    ⚠️ **응답을 실물로 본 적이 없다** (403). 필드 규약은 문서 기준이므로, 값이 잡히면 여기가
    먼저 틀릴 자리다. 모르는 모양이면 조용히 비우지 않고 빈 목록을 낸다 — 그 자체가
    "UV 축을 못 켰다"는 신호이고, ③-b 가 UV 를 축에서 뺐으므로 판정은 그대로 돈다.
    """
    out: list[Measurement] = []
    for item in _items(payload):
        issued = _stamp(item.get("date"))
        if issued is None:
            continue
        for key, raw in item.items():
            offset = _hours(key)
            if offset is None:
                continue
            value = _number(raw)
            if value is None:
                continue
            out.append(Measurement(
                quantity=Q.UV, value=value,
                valid_at=issued + timedelta(hours=offset), issued_at=issued,
                source=Source.LIFE_INDEX, spatial_ref=f"행정구역 {area}",
                # 자외선지수는 5단계(낮음~위험)이고 대기질은 4단계다. 척도가 다르므로
                # 등급을 룰이 비교하면 안 된다는 ②-d-2 근거 2 가 여기서 실물이 된다.
                grade=None))
    return out


def parse_senta(payload: Any) -> dict[datetime, float]:
    """공식 체감온도 — `Measurement` 가 아니라 **대조표**로 돌려준다.

    `Q` 에 넣지 않는 이유는 ②-d-3 결정 2 그대로다. 이 값의 쓰임은 판정이 아니라 ③-c 산식의
    검산이므로, 관측 목록에 섞으면 룰이 "출처가 우리인 값"과 "기상청 값"을 구분 못 하게 된다.
    """
    table: dict[datetime, float] = {}
    for item in _items(payload):
        issued = _stamp(item.get("date"))
        if issued is None:
            continue
        for key, raw in item.items():
            offset = _hours(key)
            value = _number(raw)
            if offset is not None and value is not None:
                table[issued + timedelta(hours=offset)] = value
    return table


def _hours(key: str) -> int | None:
    if not key.startswith(_OFFSET_PREFIX) or not key[1:].isdigit():
        return None
    return int(key[1:])


def _number(raw: Any) -> float | None:
    try:
        return float(str(raw).strip())
    except (TypeError, ValueError):
        return None


def _stamp(raw: Any) -> datetime | None:
    """`'2026082510'` — 시각까지."""
    try:
        return datetime.strptime(str(raw).strip(), "%Y%m%d%H").replace(tzinfo=KST)
    except (TypeError, ValueError):
        return None


def fetch_uv(area_no: str, now: datetime, *, budget: Budget | None = None) -> list[Measurement]:
    return parse_uv(kmahub.get_json(f"{PATH}/getUVIdxV3", _params(area_no, now), budget=budget), area_no)


def fetch_senta(area_no: str, now: datetime, *, budget: Budget | None = None) -> dict[datetime, float]:
    return parse_senta(kmahub.get_json(f"{PATH}/getSenTaIdxV3", _params(area_no, now), budget=budget))


def _params(area_no: str, now: datetime) -> dict[str, Any]:
    # `requestCode` 가 필수다 — `areaNo`·`time` 만 주면 `11 NO_MANDATORY_REQUEST_PARAMETERS` 다 (§6.8 ③)
    return {"areaNo": area_no, "time": now.strftime("%Y%m%d%H"),
            "requestCode": "A01", "dataType": "JSON"}
