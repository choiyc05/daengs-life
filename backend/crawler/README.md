# crawler/

오케스트레이터 무관 순수 파이썬 패키지 + CLI (D-001 원칙 1). `app/`·`tasks/` 를 import 하지 않는다.

```
crawler/
├── __init__.py        패키지 설명 (최상위만 둔다. core/·sources/ 는 빈 __init__ 없이 namespace 서브패키지)
├── __main__.py        CLI: list / run  — `python -m crawler` 의 진입점
├── core/
│   ├── config.py      경로(REPO_ROOT/DATA_DIR), UA, 요청 간격
│   ├── fetch.py       Fetcher — UA·호스트별 1.5s 간격·재시도·robots.txt
│   ├── store.py       raw/ 저장 + .meta.json + crawl_log.jsonl, sha256 변경 감지
│   └── registry.py    seed_sources.yaml 로드, id → sources/ 모듈 매핑
└── sources/
    ├── base.py        Source / Target / Extracted 계약
    └── easylaw_pet.py 소스 모듈 (yaml id 'easylaw-pet' → 모듈명 easylaw_pet)
```

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
2. **모듈** — `sources/{id_with_underscores}.py` 에 `Source` 서브클래스 하나.
   - 클래스 속성: `id domain category subcategory source_type format trust_level license` → `.meta.json` 으로 그대로 흘러감
   - `discover(fetcher) -> list[Target]` : 받을 URL + slug(파일명) 목록
   - `extract(res, target) -> Extracted` : 제목·본문·`published_at`·`cites`.
     html 소스는 이 본문 텍스트가 변경 감지 지문(sha256)이 되므로 조회수 같은 노이즈를 여기서 제거
3. **시험** — `--dry-run --limit 3`. 제목이 비거나 메뉴가 본문으로 잡히면 여기서 잡는다.
4. **수집** — `run --source {id}`. `data/raw/{domain}/` 에 원본 + meta, `crawl_log.jsonl` 에 한 줄씩.
5. **커밋** — `git add data/` 하면 `.gitignore` 가 원본은 막고 `.meta.json` 만 올린다.
   `data/README.md` 값 사전(subcategory 표)에 새 값 추가.

소스 모듈은 site-specific 지식만 가진다. 받기·저장·로그·변경 감지·예절은 전부 `core/` — 고치면 모든 소스에 적용된다.

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
