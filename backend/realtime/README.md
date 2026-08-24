# realtime/

파트② **실시간 조회형** 엔진 — 산책 적합 날씨·미세먼지. 설계 전체는 `docs/decisions-realtime.md`
**RT-001**(하위 18결정 확정)에 있고, 그 근거는 전부 `docs/realtime-apis.md` **§6 실측**이다.

```
GPS ──geo──▶ 조회 키(격자·측정소·행정동) ──providers──▶ 공통 관측 모델 ──rules──▶ 산책 적합도
```

## 이 패키지가 crawler 를 안 닮는 지점

**저장하지 않는다.** 10분 뒤면 틀릴 값을 벡터로 박아두면 계속 오답을 뱉는다
(`data/README.md` §5, D-012). 그래서 크롤러 소스 모듈도 `.meta.json` 도 생기지 않는다.
`data/reference/` 에 두는 것은 측정소 목록 같은 **월 1회 갱신 정적 메타뿐**이다.

## 배치 — 층을 전송/소스로 가른다 (RT-001 ①)

```
realtime/
├── __main__.py       CLI: config · geo  (walk 이 7단계에서 붙는다)
├── config.py         Settings 키 3종 + 경로. 키는 읽는 즉시 정규화
├── transport/        ① 전송 층 — 인증·봉투·에러코드·재시도 (3 모듈)
│   ├── datagokr.py     serviceKey + response.header/body.items   ← 5종이 공유
│   ├── kakao.py        KakaoAK 헤더 + documents[]
│   └── kmahub.py       authKey + typ01 텍스트/CSV · typ02 JSON
├── providers/        ② 소스 층 — API 서비스 하나 = 모듈 하나 (7 모듈)
├── geo.py            ✅ WGS84 → LCC 격자 · 하버사인 최근접 · 같은 격자 판정(⑤-d)
├── observation.py    ★ 공통 관측 모델 = provider 와 룰 사이의 계약 (RT-001 ②)
├── rules.py          산책 적합도 판정 — 축 3개, 최악 우선 (③)
└── cache.py          신선도·TTL·single-flight (④)
```

**왜 기관 축이 아닌가** — 기상청 하나가 전송 계약 **셋**(data.go.kr · apihub typ01 · typ02)에
걸쳐 있다. 기관으로 자르면 `kma.py` 안에 인증 2종·응답 포맷 3종이 들어간다. 경계가 아무것도
막지 못하면 그건 경계가 아니다.

**`core/` 는 두지 않는다** (RT-001 ①-3). `core/` 는 "N 개가 공유하는 것"의 자리인데 여기서
N 은 `providers/` 7개이고 걔들이 공유하는 것은 이미 `transport/` 다. 층이 겹친다.

**provider 는 API *서비스* 하나 = 모듈 하나다. 오퍼레이션 단위가 아니다.** 단기예보의
`getUltraSrtNcst`·`getUltraSrtFcst`·`getVilageFcst` 는 같은 봉투·같은 격자 입력이라 한 모듈 안의
함수 셋이다. 그래서 7개가 `docs/data-sources.md` §8 의 연동 체크 7개와 1:1 로 맞는다.

## 의존 방향

`app → realtime → crawler.core.config` 한쪽뿐이고, **그 하나뿐**이라는 것까지 기계가 막는다
(`tests/test_import_direction_packages.py`, RT-001 ①-2). 넓히면 `Fetcher`·`store` 가 따라 들어오고
그 순간 "실시간은 저장하지 않는다"가 흐려진다.

`rag` 는 허용이 둘(`config` + `textutil`)이라 목록이 패키지별로 갈려 있다.

## 실행

```bash
cd backend
uv run python -m realtime config              # 키·경로가 실제로 읽히는지
uv run python -m realtime geo 37.4979 127.0276   # 위경도 → 격자·대표점
```

⚠️ `DATA_GO_KR_KEY` 는 포털이 **Encoding / Decoding 두 벌**로 준다. 맞는 것은 Decoding 쪽인데
어느 쪽을 넣어도 되게 `config.normalize_key()` 가 `%` 를 보고 1회 디코딩한다 (§6.1 함정 1).
위 CLI 가 `Encoding 키 → 디코딩함 (98자 → 88자)` 로 실제 동작을 보여준다.

## 실측이 이미 넘긴 제약 (§6)

- 값이 전부 **문자열**이고, 기온 이름이 `T1H`(실황) ↔ `TMP`(단기예보)로 **개명된다**
- 특보는 값도 상태도 아니라 **자연어 1,610자**다 — 특보구역명 매핑표가 `data/reference/` 에 하나 더 필요
- 대기질 **등급이 두 벌**이다 — `Grade`(24h 평균) vs `Grade1h`(현재). 산책은 `Grade1h`
- data.go.kr `05` 는 **HTTP 200 안에 숨어 있다.** status code 만 보면 성공으로 오인한다
- ⚠️ **개발계정은 API 당 일 1,000회.** 단기예보가 격자 17개뿐이라 운영계정 전환이 사실상 필수 (④-e)
