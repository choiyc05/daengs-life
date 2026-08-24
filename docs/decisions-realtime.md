# 파트② 실시간 조회형 — 설계 결정 기록 (Decision Log)

> 상태: ✅ 확정 · 🔶 제안(논의중) · ⏸ 보류. 결정이 뒤집히면 지우지 말고 상태 변경 + 사유 추가.
>
> **번호 체계** — 파트②는 `RT-` 접두사를 쓰고 이 파일에만 산다. 공통 인프라와 파트①은
> [decisions.md](decisions.md) 의 `D-` 를 계속 쓴다.
>
> 두 파트를 병렬 브랜치(`feat/rag` · `feat/realtime`)에서 동시에 진행하기 때문이다. 한 파일에 둘이
> append 하면 **같은 번호를 각자 발급**하게 되고, 번호는 decisions.md 133회 · CLAUDE.md 30회 ·
> 코드와 커밋 메시지까지 박히는 **사실상 불변 식별자**라 사후 재배정이 비싸다. 파일이 갈리면
> 번호 충돌과 머지 텍스트 충돌이 함께 사라진다.
>
> 접두사로 `P2-` 를 안 쓴 이유 — `docs/workflow.md` 의 우선순위 등급 P0/P1/P2 와 눈으로 겹친다.

---

## RT-001. 실시간 엔진 — 계층·관측 모델·판정 룰·캐시 — 🔶 진행중 (2026-08-24, ①만 확정)

**배경** — 파트②는 조사(`docs/realtime-apis.md`, 2026-08-19)만 끝나 있고 **코드도 결정도 없다.**
D-018 이 `backend/realtime/` 을 "파트② 엔진 (미착수)"로 자리만 잡아 뒀고, D-012 가 "realtime 도메인은
저장하지 않아 크롤러 소스 모듈이 생기지 않는다", D-001 이 "Redis 를 API 응답 TTL 캐시로 재활용 예정"이라
예고했을 뿐이다. P1(메인 피처)은 **조사한 API 7종 전부 연동**으로 잡았다.

여섯 개를 정해야 하고 이 ADR 하나에 모은다 — 여섯이 한 엔진의 규칙이라 쪼개면 서로를 참조하는 ADR 이
여섯 개 생긴다 (D-021 과 같은 이유).

### 논의 순서와 그 이유

뒤 결정이 앞 결정을 되돌리게 만들지 않는 순서다.

| 순 | 결정 | 상태 | 이 자리인 이유 |
|---|---|---|---|
| ① | **계층** — 층을 어느 축으로 자르나 | ✅ 확정 | 물리적으로 먼저. 코드를 놓을 자리가 정해져야 나머지를 얹는다 |
| ② | **공통 관측 모델** | ⬜ 미논의 | provider 와 판정 룰 사이의 **계약**. 없으면 룰이 7개 API 스키마를 직접 알게 되고 API 하나가 바뀔 때 룰이 깨진다 |
| ③ | **산책 적합도 룰** | ⬜ 미논의 | 본체. ②의 필드가 고정돼야 논의가 닫힌다 |
| ④ | **신선도·캐시** | ⬜ 미논의 | ③이 "무슨 입력이 꼭 필요한가"를 정해야 각 입력의 신선도 요구를 말할 수 있다 |
| ⑤ | **부분 실패·저하 정책** | ⬜ 미논의 | ③④ 위에서만 닫힌다. 공공 API 는 실제로 자주 죽는다 |
| ⑥ | **응답 계약** | ⬜ 미논의 | **일부러 마지막.** 필드는 내용에서 따라 나온다 (D-021 ⑤와 같은 이유) |

### 재논의 비용

| 결정 | 나중에 바꾸면 | 비용 |
|---|---|---|
| ① 계층 | 폴더 이동 + import 경로 | 🟢 |
| ② 관측 모델 | provider 7개 + 룰 전부 수정 | 🔴 |
| ③ 판정 룰 | 룰 파일 하나 + 검증 케이스 재작성 | 🟡 |
| ④ 캐시 | 정책값 | 🟢 |
| ⑤ 저하 정책 | 응답에 필드 추가 | 🟡 |
| ⑥ 응답 계약 | 프론트가 붙기 전이면 무료 | 🟢 |

비싼 것은 ②뿐이라 ① 바로 뒤에 놓았다.

---

### ① 계층 — 전송 층과 provider 층을 나눈다 — ✅ 확정 (2026-08-24)

**"provider 를 기관 축으로 자르나 데이터 축으로 자르나"에서 출발했는데, 실제로 무엇이 다른지 세어 보니
둘 중 하나를 고르는 문제가 아니었다.**

| API | 호스트 | 인증 | 응답 | 에러 |
|---|---|---|---|---|
| 기상청 단기예보 | `apis.data.go.kr` | `serviceKey` 쿼리 | JSON `response.body.items.item[]` | `response.header.resultCode` |
| 기상청 특보 | `apis.data.go.kr` | 〃 | 〃 | 〃 |
| 기상청 생활기상지수 | `apis.data.go.kr` | 〃 | 〃 | 〃 |
| 에어코리아 실시간 | `apis.data.go.kr` | 〃 | 〃 | 〃 |
| 에어코리아 측정소 | `apis.data.go.kr` | 〃 | 〃 | 〃 |
| 카카오 Local | `dapi.kakao.com` | `Authorization: KakaoAK` **헤더** | JSON `documents[]` + `meta` | HTTP status |
| 기상청 API허브 | `apihub.kma.go.kr` | `authKey` 쿼리 | **텍스트/CSV** (`#` 주석 헤더) | 텍스트 |

**관찰 1 — 전송 계약은 기관과 일치하지 않는다.** 기상청이 data.go.kr(3종)과 API허브(1종) 양쪽에
걸쳐 있다. 기관 축으로 자르면 `kma.py` 안에 **인증 방식 2개·응답 포맷 2개**가 들어간다.
경계가 아무것도 막지 못하면 그건 경계가 아니다.

**관찰 2 — 데이터 축으로만 자르면 봉투를 5번 쓴다.** `resultCode` 분기, `items` 언랩, 빈 `items`,
에러 시 JSON 이 아니라 XML 로 돌아오는 폴백 — data.go.kr 계열의 그 처리가 5개 모듈에 복사된다.

**결정 — 두 축을 서로 다른 층에 둔다.** D-018 이 파서에서 푼 것과 같은 형태다.

| | D-018 파서 | 이번 realtime |
|---|---|---|
| 아래 층 | `extract/` **포맷** 층 (pdf·hwpx·html·xml) | `transport/` **전송** 층 (datagokr·kakao·kmahub) |
| 위 층 | `parsers/` **사이트** 층 (소스 1 = 모듈 1) | `providers/` **소스** 층 (API 1 = 모듈 1) |
| 위로 나가는 계약 | 공통 IR 6종 (`ir.py`) | 공통 관측 모델 (②) |

```
backend/realtime/
├── __main__.py       CLI — crawler·rag 와 같은 방식 (D-001 원칙 1)
├── config.py         Settings — DATA_GO_KR_KEY · KAKAO_REST_KEY · KMA_HUB_KEY
├── transport/        ① 전송 층 — 인증·봉투·에러코드·재시도 (3 모듈)
│   ├── datagokr.py     serviceKey + response.header/body.items   ← 5종이 공유
│   ├── kakao.py        KakaoAK 헤더 + documents[]
│   └── kmahub.py       authKey + 텍스트/CSV
├── providers/        ② 소스 층 — API 하나 = 모듈 하나 (7 모듈)
│   ├── kma_vilage_fcst.py · kma_warning.py · kma_life_index.py · kma_apihub.py
│   ├── airkorea_realtime.py · airkorea_stations.py
│   └── kakao_local.py
├── geo.py            좌표 변환 — WGS84 → 격자(nx,ny) · TM
├── observation.py    ★ 공통 관측 모델 = provider 와 룰 사이의 계약 (②)
├── rules.py          산책 적합도 판정 (③)
└── cache.py          신선도·TTL (④)
```

- **provider 는 API *서비스* 하나 = 모듈 하나다. 오퍼레이션 단위가 아니다.** 단기예보 서비스의
  `getUltraSrtNcst`·`getUltraSrtFcst`·`getVilageFcst` 셋은 같은 봉투·같은 격자 입력이라 한 모듈 안의
  함수 셋이다. 그래서 provider 7개가 `docs/data-sources.md` §8 의 연동 체크 7개와 1:1 로 맞는다
- **`geo.py` 를 provider 밖에 둔 이유** — 격자·TM 변환은 어느 API 의 것도 아니다. 카카오 `transcoord`
  로도 되고 자체 계산으로도 되는데 **자체 계산이 기본이고 카카오는 대체재**다. 그래야 `KAKAO_REST_KEY`
  가 없어도 관통되고, 카카오는 "○○동" 표기라는 UX 역할만 남는다
- 크롤러의 `sources/law/_lawgokr.py`(사이트가 같은 두 소스의 공용 베이스)가 부분적 선례지만,
  그것은 **소스 층 안의 공유**였다. 여기서는 전송 계약이 기관을 가로지르므로 층을 하나 더 내려야 한다

**기각 — 기관 축 단독**: 관찰 1. 기상청이 두 전송 계약에 걸쳐 있어 경계가 실제 차이와 어긋난다.
**기각 — 데이터 축 단독**: 관찰 2. 봉투 처리가 5중복되고, 그 5개가 따로 늙는다.

> **정정 (2026-08-24, 실측)** — 위 표는 API허브를 "텍스트/CSV" 한 줄로 적었다. 실제로는 **두 계열**이다:
> `typ01/url/*.php` 는 텍스트/CSV, `typ02/openApi/<서비스>/<오퍼레이션>` 은 data.go.kr 과 **같은
> 서비스명·오퍼레이션명 체계의 JSON** 이다. 실패 봉투는 두 계열 공통으로 `{result:{status,message}}` 라
> data.go.kr(`cmmMsgHeader`)·kakao(`errorType`)와 또 다르다. 그리고 **생활기상지수는 data.go.kr 이 아니라
> 이 typ02 계열에 있다** (`LivingWthrIdxServiceV3`, docs/realtime-apis.md §6.4).
>
> **①의 결정은 그대로 유효하고 근거는 오히려 강해졌다** — 기상청 하나가 이제 전송 계약 **셋**에 걸쳐 있다
> (data.go.kr · apihub typ01 · apihub typ02). 기관 축으로 자르면 `kma.py` 안에 인증 2종·응답 포맷 3종이
> 들어간다. `transport/kmahub.py` 가 두 계열을 다루되, 봉투 처리가 갈리면 파일을 갈라도 된다 —
> 그건 전송 층 **안쪽**의 문제이므로 층 경계를 건드리지 않는다.

### ①-2 `realtime` → `crawler` 참조 — ✅ 허용, 범위는 `crawler.core.config` 하나 (2026-08-24)

**왜 필요한가** — `airkorea-stations` 의 측정소 목록은 이전·증설이 있어 월 1회 갱신하는 정적 메타이고,
`docs/realtime-apis.md` §1 이 이미 `data/reference/` 에 두기로 했다. 그러려면 `DATA_DIR` 이 필요한데
그 탐색은 `crawler/core/config.py` 에만 있다 (D-014 "경로 탐색은 한 곳"). **`rag` 가 D-018 에서 정확히
같은 이유로 같은 예외를 받았다** — 두 번째 사례이므로 이제 일회성 예외가 아니라 **패턴**으로 기록한다.

**왜 좁혀야 하는가** — 넓히면 realtime 이 `Fetcher`·`store`·`seed_sources` 까지 끌어오게 되고,
그 순간 **"실시간은 저장하지 않는다"**(`data/README.md` §5, D-012)가 흐려진다. realtime 은 크롤 대상이
아니고 `.meta.json` 도 만들지 않는다. 캐시하는 것은 측정소 목록 같은 **정적 메타뿐**이다.

**가드를 말에서 기계로 옮긴다** — D-018 의 "`rag` 가 `crawler` 를 참조하는 것은 경로 탐색 하나뿐"은
지금까지 **문서에만 있는 규칙**이었다. `tests/test_import_direction.py` 는 `crawler/` 디렉터리만 훑어서
그 반대 방향을 아예 보지 않는다. 둘을 추가한다:

1. `FORBIDDEN` 에 `realtime` 추가 — `crawler` 가 `realtime` 을 import 하지 못하게 (기존 가드의 확장)
2. **새 테스트** — `rag/` 와 `realtime/` 이 `crawler` 를 import 할 때 **`crawler.core.config` 외의
   경로면 실패**. 지금 `rag` 가 이미 그 규칙을 지키고 있어 추가 즉시 통과한다(회귀 방지용으로 붙는다)

의존 방향은 여전히 한쪽이다: **app → (rag | realtime) → `crawler.core.config`**

### 다음 재개 지점

**② 공통 관측 모델** — 7개 API 응답을 무엇으로 정규화할 것인가. 재논의 비용이 🔴 라 여기서 시간을 쓴다.

**말로 정하지 않는다 — 실측을 먼저 확보했다 (2026-08-24, `docs/realtime-apis.md` §6).** 키 3종을 넣고
17회 호출해 12건을 받았고, ②의 입력이 되는 **응답 모양 5종**(격자 관측 1점 / 격자 예보 시계열 /
자연어 특보 / 측정소 값+등급 / 권역 등급 예보)을 실물로 확인했다. ②를 가리는 기준은 이제
"A~E 를 각 후보 모델로 표현했을 때 룰 코드에 `category`·`pm10Grade1h` 같은 **API 고유 이름이 나오는가**"다.

실측이 이미 ②에 넘긴 제약 셋:
- 값이 전부 **문자열**이고, 기온의 이름이 `T1H`(실황·초단기) ↔ `TMP`(단기예보)로 **개명된다** (§6.3)
- 특보는 값도 상태도 아니라 **자연어 1,610자**다. 특보구역명 매핑표가 `data/reference/` 에 하나 더 필요 (§6.3)
- 대기질 **등급이 두 벌**이다 — `Grade`(24h 평균) vs `Grade1h`(현재). 산책은 `Grade1h` (§6.3)
