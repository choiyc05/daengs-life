# crawler/

오케스트레이터 무관 순수 파이썬 패키지 + CLI (D-001 원칙 1). `app/`·`tasks/` 를 import 하지 않는다.

```
crawler/
├── __init__.py        패키지 설명 (최상위만 둔다. core/·sources/ 는 빈 __init__ 없이 namespace 서브패키지)
├── __main__.py        CLI: list / run  — `python -m crawler` 의 진입점
├── core/                                  ← 모든 소스가 공유. 고치면 전부에 적용된다
│   ├── config.py      경로(REPO_ROOT/DATA_DIR), UA, 요청 간격
│   ├── fetch.py       Fetcher — UA·호스트별 1.5s 간격·재시도·robots.txt
│   ├── store.py       raw/ 저장 + .meta.json + crawl_log.jsonl, sha256 변경 감지
│   ├── textutil.py    블록 단위 본문 추출 + 「법령」 조항 인용 파싱 (한국 법령 문서 공통)
│   └── registry.py    seed_sources.yaml 로드, id → sources/ 모듈 매핑
└── sources/                               ← 사이트 고유 지식만. 폴더 = yaml 의 domain
    ├── base.py        Source / Target / Extracted 계약
    └── law/
        ├── _lawgokr.py               law.go.kr 웹 원문 공통 베이스 (앞의 _ = 소스가 아니라 베이스)
        ├── easylaw_pet.py            생활법령 해설
        ├── law_animal_protection.py  동물보호법 3종       ┐ _lawgokr 상속.
        ├── law_livestock_epidemic.py 가축전염병예방법 3종  ┘ 법령 목록만 선언한다
        └── law_drf_api.py            법령 Open API (조문 단위 XML) — LAW_OC 필요
```

`registration/` `vaccination/` `leash-muzzle/` `transport/` `subsidy/` `insurance/` 도 같은 방식으로 생긴다.
(`realtime` 은 저장하지 않고 API 직조회라 소스 모듈이 없다.)

**레이어는 셋이다.**

| 층 | 위치 | 아는 것 |
|---|---|---|
| ① 공통 | `core/` | 받기·저장·변경감지·텍스트 정리·키 마스킹. 사이트를 모른다 |
| ② 사이트 | `sources/{domain}/_*.py` | 사이트 하나의 구조 (URL 패턴, 셀렉터) |
| ③ 대상 | `sources/{domain}/{id}.py` | 그 사이트에서 무엇을 받을지 |

소스가 23개가 되어도 새로 쓰는 코드는 ③뿐이어야 한다. 같은 사이트를 두 번째로 건드리면 ②를 만들고,
사이트가 달라도 반복되면 ①로 올린다 (`textutil` 이 그렇게 올라왔다).

**모듈 위치는 계산한다** — yaml 의 `domain` + `id` → `sources/{domain}/{id}.py` (`-` → `_`).
폴더를 스캔하지 않으므로 소스가 늘어도 조회 비용이 그대로다. `domain` 은 `data/raw/{domain}/` 저장
위치와 같은 축이라 새 규약이 늘지 않는다.

registry 는 모듈 안에서 `__module__` 이 그 모듈인 `Source` 하위 클래스를 찾는다 —
`_lawgokr.py` 에서 import 해 온 베이스 클래스는 자동으로 걸러지므로 상속해도 충돌하지 않는다.

## API 키

`.env` (레포 루트)에 넣으면 `core/config.py` 가 읽는다. 이름은 `docs/data-sources.md` §9 와 같다.
**키가 URL 에 들어가는 소스는 저장·로그·출력 전에 `config.redact()` 를 통과한다** — `.meta.json` 은
git 에 커밋되므로(D-008) 가리지 않으면 키가 그대로 올라간다. 새 API 소스를 만들 때 확인할 것.

## 실행

```bash
cd backend
uv run python -m crawler list                                   # 소스 목록 + 구현 여부
uv run python -m crawler run --source easylaw-pet --dry-run --limit 3   # 아무것도 안 쓰고 추출 결과만
uv run python -m crawler run --source easylaw-pet               # 수집 (원본 없는 것은 자동 재수집)
uv run python -m crawler run --source easylaw-pet --force       # sha256 같고 원본 있어도 새 파일로
```

## 소스 하나 추가하는 절차

1. **정찰** — `curl -A "daengs-life-crawler/0.1"` 로 URL 살아있는지, 본문 셀렉터, 페이징, 인코딩, robots 확인.
   yaml의 `status: verified` 를 믿지 말 것 (easylaw-pet 시드 URL도 깨져 있었다). 깨졌으면 yaml 수정.
2. **모듈** — `sources/{domain}/{id_with_underscores}.py` 에 `Source` 서브클래스 하나.
   도메인 폴더가 없으면 만든다 (`__init__.py` 없이 — namespace 패키지).
   - 클래스 속성: `id domain category subcategory source_type format trust_level license` → `.meta.json` 으로 그대로 흘러감
   - `discover(fetcher) -> list[Target]` : 받을 URL + slug(파일명) 목록
   - `extract(res, target) -> Extracted` : 제목·본문·`published_at`·`cites`.
     html 소스는 이 본문 텍스트가 변경 감지 지문(sha256)이 되므로 조회수 같은 노이즈를 여기서 제거
   - 문서마다 분류가 다르면 `Target.meta["subcategory"]` 로 덮어쓴다 (한 소스가 여러 법령을 받는 경우)
   - 키가 필요하면 `config.SECRETS` 에 이름을 추가하고, 미설정일 때 **발급처를 알려주며** 멈춘다
3. **시험** — `--dry-run --limit 3`. 제목이 비거나 메뉴가 본문으로 잡히면 여기서 잡는다.
   API 소스는 여기서 `.meta.json` 의 `source_url` 에 키가 가려졌는지 반드시 눈으로 확인.
4. **수집** — `run --source {id}`. `data/raw/{domain}/` 에 원본 + meta, `crawl_log.jsonl` 에 한 줄씩.
5. **커밋** — `git add data/` 하면 `.gitignore` 가 원본은 막고 `.meta.json` 만 올린다.
   `data/README.md` 값 사전(subcategory 표)에 새 값 추가.

소스 모듈은 site-specific 지식만 가진다. 받기·저장·로그·변경 감지·예절은 전부 `core/` — 고치면 모든 소스에 적용된다.

> `.meta.json` 은 원본이 **바뀔 때만** 다시 쓰인다. 그래서 meta 를 만드는 로직(예: `cites` 정규식)을
> 고쳐도 기존 meta 는 옛 값 그대로다. 같은 날이면 `--force` 가 파일명이 같아 제자리 갱신이 된다.

## 설계 메모

- `sha256` 은 html 이면 `extract().text` 해시, 그 외는 원본 바이트 해시. `store.py` 주석 참고.
- 같은 slug 의 최신 `.meta.json` 과 지문이 같으면 아무것도 안 쓰고 로그만 `changed:false`.
  다르면 오늘 날짜로 새 파일 (옛 파일 보존 — 원본 불변).
- **지문이 같아도 meta 의 `raw_file` 이 디스크에 없으면 다시 받는다** (D-010, 출력 라벨 `RAW-MISSING`).
  원본은 git 미추적이라 다른 PC 에서 clone 하면 meta 만 있고 원본이 없다 — 그대로 두면 전부 `same` 으로
  스킵돼 파싱 단계가 빈손이 된다. `--force` 없이 그냥 `run` 하면 없는 것만 채워진다.
- 왜 받았는지는 `crawl_log.jsonl` 의 `reason`: `new`/`changed`/`raw-missing`/`forced`/`same`.
- `Fetcher` 는 4xx 는 즉시 반환(재시도 무의미), 5xx·네트워크 오류만 지수 백오프 3회.
- 시간대는 `Asia/Seoul` 고정. Windows 에는 tz DB 가 없어 `tzdata` 패키지가 의존성에 들어 있다.
