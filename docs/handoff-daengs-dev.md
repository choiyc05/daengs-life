# DAENGS_dev 이관 노트

이 레포(`choiyc05/daengs-life`)를 팀 레포 **`SAJOYO/DAENGS_dev`** 로 옮길 때 쓰는 문서.
독자는 **DAENGS_dev 에서 새 세션을 켠 나**다. 목적은 하나 — 저쪽에서 처음부터 다시 조사하지 않게 하는 것.

작성 2026-08-27. 읽는 순서: **이 문서 → `../CLAUDE.md`(레포 규약) → `decisions.md`(왜 그렇게 했나)**

---

## 1. 지금 어디까지 됐나

| 파트 | 상태 | 눈으로 확인한 것 |
|---|---|---|
| ① 제도·문서형 RAG | **1랩 관통 완료** — parse→chunk→embed→load→search→generate | `POST /ask` 가 답변+근거를 낸다. 검문소 ①③④ 통과 |
| ② 실시간 산책 | **완료** | `GET /walk` 실서버 응답 5KB. 검문소 A~D 통과 |

- 테스트: `cd backend && uv run pytest` → **304 통과 / 3 skip** (2026-08-27 실측).
  `slow`(임베딩 가중치 로드) 마커는 `addopts = "-m 'not slow'"` 로 기본 제외된다 — 저쪽에서 숫자가 다르면 이것부터 의심할 것
- 코퍼스: 수집 **28건** → parsed 22 → 청크 **1,407** → `documents` **1,402행**(content 중복 5건 병합)
- ⚠️ **끝난 게 아니다.** 시드 30개 중 **11개만 수집**했다. 남은 19개와 그 파서가 2랩이고, 그게 이관하는 이유다 (§5)

---

## 2. 무엇이 따라가고, 무엇이 안 따라가나

**git 이 들고 가는 것** — `backend/`(패키지 5개 + `tests/` 36파일) · `docs/` 6문서 ·
`data/README.md` · `data/manifests/seed_sources.yaml` · `db/{init/,indexes.sql}` · `compose.yml` · `backend/rag/stages/goldenset.yaml`

**git 이 안 들고 가는 것** — `data/` 는 통째로 미추적이다 (D-017). 옮기기 전에 아래를 판단할 것:

| 무엇 | 크기 | 다시 만들 수 있나 |
|---|---|---|
| `data/raw/**` 원본 28건 + `.meta.json` | 8.8MB | ⚠️ 재수집하면 **ID 가 바뀐다** — 아래 |
| `data/processed/{parsed,chunks}` 22+22 | 4.3MB | ⚠️ 위와 같이 딸려 바뀐다 |
| `data/processed/embeddings/*.parquet` 3종 | 6.4MB×3 | ⚠️ 위와 같이 **무효가 된다** |
| `data/processed/eval/*.jsonl` 3종 | 26KB×3 | ✅ 재현. **판정 결과 자체는 D-024 에 적혀 있어** 덤프가 없어도 결론은 안 잃는다 |
| **`data/processed/answers/lap1.jsonl`** | **16KB** | ❌ **못 만든다** |
| `backend/.env` 키 6종 | — | 재발급 (발급처 `data-sources.md` §9) |
| 모델 가중치 | ~10GB | 재다운로드. **7단계 이후로는 승자 Qwen3 1.2GB 하나면 된다** |

> ⚠️⚠️ **`data/` 는 재수집하지 말고 통째로 복사할 것.** `chunk_id` 에 **수집 날짜가 박혀 있다**
> (`crawler/core/store.py:99`, 예: `easylaw-pet-1-1-1__20260819#note-1`). 오늘 다시 받으면 `__20260827` 이 되어
> **모든 ID 가 바뀌고, `chunk_id` 로 묶인 parquet 3종과 `documents` 1,402행이 통째로 무효가 된다** (D-025 ⑤ 지문이 `(chunk_id, content)`).
> 재수집은 "원본만 복구"가 아니라 **embed 부터 다시 도는 것**(GPU 수십 분)이다.
> **가장 위험한 것은 복사와 재수집을 섞는 것** — 옛 parquet 에 새 chunk_id 를 맞추려다 조용히 어긋난다.
> 골든셋 라벨만은 안전하다. **수집 날짜를 뺀 논리 주소**로 잡아 뒀다 (D-022 ⑥).
> `data/` 전체는 **32MB** 다. USB 하나면 끝나는 것을 GPU 수십 분과 바꾸지 말 것.

> ⚠️ **`lap1.jsonl` 을 먼저 백업할 것.** LLM 출력이라 같은 입력으로 다시 돌려도 같은 글이 안 나온다.
> 이건 D-028 ⑥ 이 정한 **1랩↔2랩 비교 축**이고, 잃으면 2랩이 나아졌는지 판단할 기준선이 사라진다.
> `data/` 가 미추적인 것은 원본·중간산출물을 두고 한 결정이지(D-017), 이 파일까지 버리자는 뜻이 아니었다.

---

## 3. 옮기면 깨지는 것 ⚠️

여기가 이 문서의 본론이다. **두 레포는 규약이 정면으로 다르다.** 저쪽 규약은 `DAENGS_dev/CLAUDE.md` 와 그 `docs/decisions.md` 에 있다.

| # | 축 | 이 레포 | DAENGS_dev | 부딪히면 |
|---|---|---|---|---|
| 1 | **ADR 번호** | `D-001`~`D-028` (`docs/decisions.md`) | `D-001`~`D-017` (`docs/decisions.md`) | **정면 충돌.** 파일 이름도 번호도 같은데 내용이 남남이다 — 저쪽 D-011 = SQLAlchemy·MVC2, 여기 D-011 = 법령 웹 원문 수집 경로. 저쪽 D-001 = Python 3.12 고정, 여기 D-001 = Celery. **합치기 전에 접두사부터 정할 것** (§6) |
| 2 | **패키지 레이아웃** | `backend/` 밑 플랫 5개 — `crawler` `rag` `realtime` `tasks` `app` | uv **src 레이아웃** `backend/src/daengs_backend/` | 모든 import 가 깨진다 (`from rag.stages...` → `from daengs_backend...`). 저쪽 CLAUDE.md 가 **"`src/` 밑에 패키지를 더 둘지(`daengs_rag` 등)는 아직 정하지 않았다"** 고 명시 — 즉 **저쪽도 안 정한 자리**다 |
| 3 | **서빙 계층** | `app/`={controllers,services,dto,deps}, **`models/` 는 일부러 없다** (D-027) | `routers`=C / `services`=S / `repositories`=DAO / `models`+`schemas`=M (저쪽 D-011) | 이름이 다른 같은 MVC2 다. `controllers`→`routers`, `dto`→`schemas` 로 접으면 맞지만 **`repositories` 가 없다** — 여기는 SQL 을 `rag/stages/load.py`·`search.py` 가 직접 쥔다 |
| 4 | **DB 접근** | psycopg3 + **SQL 직접** (D-025) | **SQLAlchemy 2.0 async + asyncpg**, 세션은 `core.database.get_session` (저쪽 D-011) | 가장 손이 많이 갈 곳. 벡터 검색 SQL 을 ORM 으로 옮길지, `rag` 만 예외로 둘지 결정해야 한다 |
| 5 | **DB 인스턴스** | 로컬 compose `db`(pgvector) | **팀에 하나뿐**이고 서버 PC 에 있다. 개발 PC 는 붙기만 한다 | `documents` 테이블을 팀 DB 에 만들어야 한다. 저쪽은 **`db/init/` 이 볼륨 최초 1회만** 실행되므로 이미 도는 DB 에는 안 먹는다 → **`db/migrations/` 에 SQL 파일로** 남기고 손으로 적용하는 게 저쪽 규칙 |
| 6 | **`documents.category`** | CHECK(policy/travel/food) | — | 2랩의 **펫보험**이 들어갈 값이 없다. 마이그레이션에 같이 실을 것 |
| 7 | **Redis** | compose 에 `redis` 있음 (D-001 Celery 브로커) | compose 에 **없다** (nginx·backend·pgvector·pgadmin) | Celery·Beat 를 옮기려면 저쪽 compose 에 서비스 추가가 필요하다 |
| 8 | **env 이름** | 접두사 없음 (`LAW_OC`, `DATA_GO_KR_KEY`, …) | **`DAENGS_*`** 접두사 | `pydantic-settings` 설정을 맞추거나 이름을 바꿔야 한다 |
| 9 | **브랜치** | `main` 하나 | **`dev` 가 기본**, `main` 은 릴리즈 스냅샷 | PR 은 `dev` 로. 작업 단위는 **PR 본문 `## 작업 목록`** (저쪽 `docs/collaboration.md`, `.github/PULL_REQUEST_TEMPLATE.md`) |
| 10 | **배포** | 없음 | **`dev` 에 push·merge 하면 self-hosted 러너가 자동 배포** | ⚠️ 넣는 순간 서버에 뜬다. 아래 주의 |
| 11 | **torch** | `[dependency-groups] ml` + `pytorch-cu126` 인덱스(win32) | 없음 | 저쪽 backend 는 컨테이너로 돈다. `uv sync` 기본에 ml 이 안 붙게 **그룹 분리를 반드시 유지**할 것 |

- Python 은 **양쪽 다 `>=3.12,<3.13`** 이다. 여기만은 안 부딪힌다
- ⚠️ **10번이 조용한 지뢰다.** 서빙이 lifespan 에서 임베딩 모델을 CPU 로 상주시킨다(D-028 ①).
  자동 배포되는 서버에 그대로 올리면 **기존 API 프로세스가 모델 로드분(수 초 + 메모리)을 같이 문다.**
  `rag` 를 같은 프로세스에 넣을지, 워커·별도 서비스로 뺄지는 **넣기 전에** 정해야 한다

---

## 4. 새 PC 에서 상태 복원하기

**1순위는 `data/` 통째 복사다** (32MB, §2 의 경고). 아래는 **복사본이 없어 처음부터 다시 만들 때**의 절차다.
내용은 그대로 복원되지만(2026-08-22 실제로 복원, 요소 수 동일 재현 확인) **ID 가 새 날짜로 바뀌므로 embed 부터 전부 다시 돈다.**

```bash
# 0) backend/.env 에 키를 넣는다 (최소 LAW_OC, 9단계까지 가려면 GEMINI_API_KEY)
cd backend
uv sync --group ml

# 1) 수집 — 4소스
uv run python -m crawler run --source easylaw-pet
uv run python -m crawler run --source law-animal-protection
uv run python -m crawler run --source law-livestock-epidemic
uv run python -m crawler run --source law-drf-api

# 2~8) 인덱싱
uv run python -m rag parse       # → processed/parsed  22건
uv run python -m rag chunk       # → processed/chunks  1,407청크
uv run python -m rag embed       # GPU 권장. 2랩부터는 승자 하나만: --model qwen3-embedding-0.6b
uv run python -m rag goldenset   # 라벨 실존 검사
uv run python -m rag load        # → documents 1,402행. 인덱스는 적재 후 db/indexes.sql 수동
uv run python -m rag search --questions    # 검문소③

# 9) 서빙
uv run python -m rag generate --questions  # 검문소④
uv run fastapi run app/main.py             # POST /ask · GET /walk
```

- `fastapi dev` 는 reload 가 기본이라 저장할 때마다 모델 로드 5~7초를 다시 문다. 생성 쪽을 안 만지면 `fastapi run`
- GPU 는 RTX 3050 **6GB** — 모델 3종을 한 프로세스에서 연속 로드하면 VRAM 이 누적된다. `rag.embed.release()` 로 모델마다 내릴 것

---

## 5. 남은 일 (2랩)

**⚠️ 2랩의 비용은 크롤링이 아니라 파서다.**

- **소스 19개** — 시드 30개 중 11개만 수집됐다. 소스마다 파서가 필요하다
- **PDF 파서가 아예 없다** — `pdf-entry` 4종(코레일·SRT·서울교통공사·**보험사 약관** = "RAG 핵심 코퍼스")
- **골든셋 라벨에 사람 판단이 든다** — 법제처 `관련 법령` 차용(D-022 ②)이 펫보험엔 안 통한다
- **D-024 모델 교체가 발동해 있다** — 승자 `Qwen/Qwen3-Embedding-0.6B` 로 바꾸는 것은 `--model` 한 번.
  ⚠️ **2랩은 코퍼스와 모델이 같이 바뀌는 랩**이라 1랩과의 차이 원인을 하나로 특정할 수 없다. 그 점을 명시하고 갈 것
- **D-003(하이브리드·리랭커)** — 검문소③이 근거를 만들어 뒀다: dense 가 질문의 *의도* 가 아니라 *표면 어휘* 를 따라간다
- **D-029 자리** — 검증질문 7개 중 **5개는 top-5 안에 정답 조항이 없다.** KPI 가 조항 인용이라 **틀린 조항 번호는 답이 없는 것보다 나쁘다.**
  방침(사용자, 2026-08-25): **먼저 한 세트 돌려보고 판단한다.** 설계 논의를 앞세우지 말 것
- `backend/main.py` 는 2줄 shim 이다. 이관하면서 정리 대상

---

## 6. 저쪽에서 첫 세션이 할 일

1. **`lap1.jsonl` 백업 확인** (§2). 이게 먼저다
2. **§3 의 11개 중 무엇을 지금 맞출지 고른다.** 전부 한 번에 맞추면 PR 이 리뷰 불가능한 크기가 된다
3. **ADR 접두사를 정한다** — 후보 셋:
   - ⓐ 여기 `D-` 를 **`RAG-`/`LIFE-` 로 바꾼다** — 저쪽 번호가 원본으로 남는다. 이 레포 문서·코드 주석의 참조를 전부 고쳐야 한다 (`decisions.md` 224KB)
   - ⓑ **파일을 나눠 둔다** (`docs/decisions-rag.md`) + 헤더에 "이 파일의 `D-` 는 다른 계보" 명시 — 손은 제일 적지만 `D-011` 이 두 뜻을 갖는 상태가 남는다
   - ⓒ 저쪽 뒤에 **이어서 재발급** (D-018~) — 번호가 하나가 되지만 **여기 문서 전체의 번호가 밀린다**. 비추천
   - `RT-` 는 저쪽에 없으니 그대로 가도 된다
4. **`dev` 에서 브랜치를 파고 PR 을 먼저 연다** — 저쪽도 여기와 같은 규칙이다(작업 전에 PR). 작업 단위는 PR 본문 `## 작업 목록`
5. 옮긴 뒤 **`uv run pytest` 가 304/3 을 재현하는지** 확인한다. 의존 방향 가드 2개(`test_import_direction*.py`)가 레이아웃 변경을 제일 먼저 잡아 줄 것이다
