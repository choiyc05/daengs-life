"""기상청 API허브 AWS 매분자료 — ⑤-d 의 1순위 (§6.8 ②).

**가장 신선하고 가장 대표성이 약한 출처다.** 분 단위 실황이지만 관측소 *지점* 값이라 내 위치를
대표한다는 보장이 없다. ⑤-d 가 "가까우면 AWS" 가 아니라 **"같은 격자면 AWS"** 를 고른 이유이고,
그 판정을 이 모듈이 진다 — **같은 격자가 아닌 지점은 애초에 `Measurement` 를 만들지 않는다.**
그래서 `observation` 의 우선순위표는 임계 없이 성립한다.

**data.go.kr 한도를 안 쓴다.** apihub 소속이고 `stn=0` 로 전국을 1회 호출로 받으므로, 지점이
있는 격자는 초단기실황(24회/일)을 생략할 수 있다 — ④-e 가 "가장 큰 절감"이라고 한 대응이다.

⚠️ **지점 좌표가 응답에 없다.** `STN` 번호뿐이라 격자 판정을 하려면 지점 목록이 따로 필요한데,
`stn_inf.php` 는 **오퍼레이션 단위 활용신청이 또 필요하다** (2026-08-25 확인, 403). 그래서
좌표표를 **인자로 받는다** — 비어 있으면 이 provider 는 아무것도 못 내고 ⑤-d 는 2순위(격자
실황)로 내려간다. 그것이 "1순위는 실제로 도시 일부에서만 발동한다"는 ⑤-d 의 한계 그대로다.
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime

from ..config import KST
from ..geo import Grid, LatLon, to_grid
from ..observation import Measurement, Q, Source
from ..transport import kmahub
from ..transport.base import Budget

PATH = "/api/typ01/cgi-bin/url/nph-aws2_min"

# `# YYMMDDHHMI STN WD1 WS1 WDS WSS WD10 WS10 TA RE RN-15m RN-60m RN-12H RN-DAY HM PA PS TD`
# 열의 의미는 **이 오퍼레이션의 지식**이라 전송 층이 아니라 여기 있다 (kmahub.rows 주석).
TM, STN = 0, 1
COLUMNS: dict[int, Q] = {
    2: Q.WIND_DIR,      # WD1  1분 평균 풍향
    3: Q.WIND,          # WS1  1분 평균 풍속
    8: Q.TEMP,          # TA   1분 평균 기온
    14: Q.HUMIDITY,     # HM   1분 평균 상대습도
}


def parse_aws(text: str, coords: Mapping[int, LatLon], grid: Grid) -> list[Measurement]:
    """전국 분 단위 관측에서 **내 격자 안 지점만** 뽑는다.

    `coords` 는 `STN` → 좌표. 모르는 지점은 격자를 판정할 수 없으므로 건너뛴다 —
    "아마 여기일 것"으로 넘기면 ⑤-d 의 대표성 근거가 그 자리에서 무너진다.
    """
    out: list[Measurement] = []
    for row in kmahub.rows(text):
        if len(row) <= max(COLUMNS):
            continue
        try:
            stn = int(row[STN])
        except ValueError:
            continue
        point = coords.get(stn)
        if point is None or to_grid(point) != grid:
            continue
        when = _stamp(row[TM])
        if when is None:
            continue
        for index, q in COLUMNS.items():
            value = kmahub.value(row[index])
            if value is None:
                continue                 # 결측 `-99.9`. 0 으로 두면 영하도 무풍도 사실이 된다
            out.append(Measurement(
                quantity=q, value=value,
                valid_at=when, issued_at=when,      # 관측이라 시각이 하나다 (②-c)
                source=Source.AWS_MIN, spatial_ref=f"AWS {stn}"))
    return out


def _stamp(raw: str) -> datetime | None:
    try:
        return datetime.strptime(raw.strip(), "%Y%m%d%H%M").replace(tzinfo=KST)
    except (TypeError, ValueError):
        return None


def fetch(coords: Mapping[int, LatLon], grid: Grid, now: datetime,
          *, budget: Budget | None = None) -> list[Measurement]:
    """`stn=0` — 전국을 한 번에. 격자별로 부르는 것보다 싸고, 그것이 ④-e 대응 1의 전제다."""
    if not coords:
        return []                        # 좌표표가 없으면 부를 이유가 없다. 예산을 아낀다
    text = kmahub.get_text(PATH, {"tm": now.strftime("%Y%m%d%H%M"), "stn": 0, "disp": 0, "help": 0},
                           budget=budget)
    return parse_aws(text, coords, grid)
