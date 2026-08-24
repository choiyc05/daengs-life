"""data.go.kr — 기상청 단기예보·특보 · 에어코리아 2종이 공유하는 전송 (RT-001 ①).

다섯 provider 가 이 한 파일을 쓴다. RT-001 ①의 "관찰 2" 가 정확히 이 봉투 처리를 두고 한 말이다 —
데이터 축으로만 자르면 `resultCode` 분기와 `items` 언랩이 다섯 군데로 복사되고 따로 늙는다.

전송 계약 (§6.1 실측)
  인증   `serviceKey` 쿼리 — **Decoding 키** (정규화는 config.normalize_key)
  성공   `response.header.resultCode == "00"` + `response.body.items.item[]`
  실패   HTTP 4xx + `OpenAPI_ServiceResponse.cmmMsgHeader.returnReasonCode`
         **또는 HTTP 200 + resultCode** ← 이쪽이 함정이다
"""
from __future__ import annotations

from typing import Any

import httpx

from .. import config
from .base import Budget, NoData, Rejected, TransportError, Unavailable, http_status_failure, request

# §6.1 함정 3 — 에어코리아에 `numOfRows=1000` 을 주면 `05` 가 잘 난다. 100 으로 낮추고
# `05` 에만 재시도하니 2/2 복구됐다. 상한을 전송 층에 두는 이유는 다섯 provider 가 같은
# 게이트웨이를 공유해서, 한 곳이 큰 값을 쓰면 그 영향이 그 provider 안에 머물지 않기 때문이다.
MAX_ROWS = 100

# §6.1 함정 2 — 대조 실험(실존+미신청 / 실존+신청됨 / 없는 경로)으로 확정한 표.
# `05` 만 재시도 가치가 있고, 나머지는 몇 번을 해도 같다.
_RESULT_CODES: dict[str, tuple[type[TransportError], str]] = {
    "05": (Unavailable, "SERVICETIMEOUT — 게이트웨이가 백엔드 연결 실패"),
    "03": (NoData, "NO_DATA — 그 조건의 값이 없다"),
    "11": (Rejected, "필수 파라미터 누락 — 우리 코드가 틀렸다"),
    "12": (Rejected, "NO_OPENAPI_SERVICE — 경로가 없다"),
    "30": (Rejected, "SERVICE_KEY_IS_NOT_REGISTERED — 활용신청을 안 했다"),
}


def _classify(response: httpx.Response) -> TransportError | None:
    """HTTP 를 보고, 그다음 봉투 안을 본다. **순서가 뒤바뀌면 `05` 를 성공으로 읽는다.**"""
    failure = http_status_failure(response)
    if failure is not None:
        return failure

    try:
        header = response.json()["response"]["header"]
    except (ValueError, KeyError, TypeError):
        # 실패 시 JSON 이 아니라 XML(`OpenAPI_ServiceResponse`)로 돌아오는 폴백이 있다.
        # 코드까지 파고들지 않는 이유 — 여기 오는 것은 이미 비정상이고, 본문을 hint 로
        # 남기면 사람이 읽어서 판정한다. 추측으로 분기하면 틀린 분기가 조용히 굳는다.
        body = response.text[:200]
        if "SERVICE_KEY" in body or "SERVICE KEY" in body:
            return Rejected("서비스키 거부", hint=body)
        return Unavailable("봉투를 읽지 못했다", hint=body)

    code = str(header.get("resultCode", "")).strip()
    if code == "00":
        return None
    kind, why = _RESULT_CODES.get(code, (Rejected, header.get("resultMsg", "")))
    return kind(f"resultCode {code or '없음'}", hint=why)


def get(path: str, params: dict[str, Any], *, budget: Budget | None = None) -> Any:
    """조회하고 **`response.body` 를 그대로** 돌려준다.

    `items.item[]` 까지 파고들지 않는 이유 — provider 마다 그 아래 모양이 다르다. 단기예보는
    `items.item[]` 이고 특보는 단건이며, `totalCount`·`numOfRows` 는 페이지 판단에 필요하다.
    전송이 여기서 한 겹 더 벗기면 provider 가 못 보는 정보가 생긴다.
    """
    if not config.DATA_GO_KR_KEY:
        raise Rejected("DATA_GO_KR_KEY 없음",
                       hint="발급·활용신청은 docs/data-sources.md §9. **Decoding 키**를 쓴다")

    query = {
        "serviceKey": config.DATA_GO_KR_KEY,
        "dataType": "JSON",
        "pageNo": 1,
        "numOfRows": MAX_ROWS,
        **params,
    }
    # 호출부가 큰 값을 줘도 상한을 넘지 않는다 — 부탁이 아니라 규칙이라야 §6.1 함정 3 이 안 돌아온다.
    query["numOfRows"] = min(int(query["numOfRows"]), MAX_ROWS)

    response = request(f"https://apis.data.go.kr{path}", params=query,
                       classify=_classify, budget=budget)
    return response.json()["response"]["body"]
