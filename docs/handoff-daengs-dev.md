# DAENGS_dev 이관 노트

이 레포(`choiyc05/daengs-life`)를 팀 레포 **`SAJOYO/DAENGS_dev`** 로 옮길 때 쓰는 문서.
독자는 **DAENGS_dev 에서 새 세션을 켠 나**다. 목적은 하나 — 저쪽에서 처음부터 다시 조사하지 않게 하는 것.

작성 2026-08-27. 읽는 순서: **이 문서 → `../CLAUDE.md`(레포 규약) → `decisions-rag.md`(왜 그렇게 했나)**

---

## 1. 지금 어디까지 됐나

| 파트 | 상태 | 눈으로 확인한 것 |
|---|---|---|
| ① 제도·문서형 RAG | **1랩 관통 완료** — parse→chunk→embed→load→search→generate | `POST /ask` 가 답변+근거를 낸다. 검문소 ①③④ 통과 |
| ② 실시간 산책 | **완료** | `GET /walk` 실서버 응답 5KB. 검문소 A~D 통과 |

- 테스트: `cd backend && uv run pytest` → **365 통과 / 1 deselected, 35초** (2026-08-27 실측, `RAG-` 개명 후·DB 기동).
  `slow`(임베딩 가중치 로드) 1개가 `addopts = "-m 'not slow'"` 로 빠진 것이 deselected 다 — 저쪽에서 숫자가 다르면 이것부터 의심할 것
  > ⚠️ **DB 를 먼저 띄울 것. 안 띄우면 멈춘 것처럼 보인다.** `psycopg.connect` 에 `connect_timeout` 이 없어
  > (`rag/stages/load.py:122`) DB 테스트마다 TCP 타임아웃을 통째로 문다 — `_conn_or_skip()` 은 **실패한 뒤에야** skip 한다.
  > 같은 날 같은 PC 에서 **DB 기동 시 35초 / 미기동 시 `test_load.py` 부근(48%) 사실상 정지**(15분 타임아웃 3회)였다.
  > **저쪽은 DB 가 원격이라 더 자주 겪는다.** `dsn` 에 `connect_timeout=3` 을 넣는 것이 한 줄 처방이다
- 코퍼스: 수집 **28건** → parsed 22 → 청크 **1,407** → `documents` **1,402행**(content 중복 5건 병합)
- ⚠️ **끝난 게 아니다.** 시드 30개 중 **11개만 수집**했다. 남은 19개와 그 파서가 2랩이고, 그게 이관하는 이유다 (§5)

---

## 2. 무엇이 따라가고, 무엇이 안 따라가나

**git 이 들고 가는 것** — `backend/`(패키지 5개 + `tests/` 36파일) · `docs/` 6문서 ·
`data/README.md` · `data/manifests/seed_sources.yaml` · `db/{init/,indexes.sql}` · `compose.yml` · `backend/rag/stages/goldenset.yaml`

**git 이 안 들고 가는 것** — `data/` 는 통째로 미추적이다 (RAG-017). 옮기기 전에 아래를 판단할 것:

| 무엇 | 크기 | 다시 만들 수 있나 |
|---|---|---|
| `data/raw/**` 원본 28건 + `.meta.json` | 8.8MB | ✅ 재수집한다 (§4). 단 **ID 가 새 날짜로 바뀐다** — 아래 |
| `data/processed/{parsed,chunks}` 22+22 | 4.3MB | ✅ 재수집에 딸려 다시 만들어진다 |
| `data/processed/embeddings/*.parquet` 3종 | 6.4MB×3 | ✅ 다시 돌린다 (GPU 수십 분). 옛 parquet 은 **버린다** |
| `data/processed/eval/*.jsonl` 3종 | 26KB×3 | ✅ 재현. **판정 결과 자체는 RAG-024 에 적혀 있어** 덤프가 없어도 결론은 안 잃는다 |
| ~~`data/processed/answers/lap1.jsonl`~~ | 16KB | ✅ **git 이 들고 간다 (2026-08-27부터)** — 아래 |
| `backend/.env` 키 6종 | — | 재발급 (발급처 `data-sources.md` §9) |
| 모델 가중치 | ~10GB | 재다운로드. **7단계 이후로는 승자 Qwen3 1.2GB 하나면 된다** |

> **방침(사용자, 2026-08-27): `data/` 는 저쪽에서 새로 크롤링한다.** 2랩이 어차피 소스를 늘리고 모델도 바꾸는 랩이라 옛 산출물을 들고 갈 이유가 적다.
> 다만 **재수집은 "원본 복구"가 아니라 `embed` 부터 전부 다시 도는 것**임을 알고 갈 것 — `chunk_id` 에 **수집 날짜가 박혀 있어서**다
> (`crawler/core/store.py:99` — `easylaw-pet-1-1-1__20260819#note-1`). 오늘 받으면 `__20260827` 이 되어 **모든 ID 가 바뀌고**,
> `chunk_id` 로 묶인 parquet 3종과 `documents` 1,402행이 함께 무효가 된다 (RAG-025 ⑤ 지문이 `(chunk_id, content)`).
> ⚠️ **가장 위험한 것은 복사와 재수집을 섞는 것** — 옛 parquet 에 새 `chunk_id` 를 맞추려다 조용히 어긋난다. **둘 중 하나만 할 것.**
> 골든셋 라벨은 안전하다. **수집 날짜를 뺀 논리 주소**로 잡아 뒀다 (RAG-022 ⑥).

> ✅ **`lap1.jsonl` 은 이제 추적한다** (2026-08-27, RAG-017 '예외' 절). LLM 출력이라 같은 입력으로 다시 돌려도
> 같은 글이 안 나오는데, RAG-028 ⑥ 이 정한 **1랩↔2랩 비교 축**이라 잃으면 2랩이 나아졌는지 볼 기준선이 사라진다.
> `.gitignore` 에 `!data/processed/answers/*.jsonl` 한 줄이고 **2랩 덤프도 같은 줄에 자동으로 걸린다.**
> `data/` 미추적(RAG-017)은 **재현 가능한** 수집·가공물을 두고 한 결정이었다 — 이 파일은 거기 해당하지 않는다.

---

## 3. 옮기면 깨지는 것 ⚠️

여기가 이 문서의 본론이다. **두 레포는 규약이 정면으로 다르다.** 저쪽 규약은 `DAENGS_dev/CLAUDE.md` 와 그 `docs/decisions-rag.md` 에 있다.

| # | 축 | 이 레포 | DAENGS_dev | 부딪히면 |
|---|---|---|---|---|
| 1 | **ADR 번호** | **`RAG-001`~`RAG-028`** (`docs/decisions-rag.md`) | `D-001`~`D-017` (`docs/decisions.md`) | ✅ **해결됨 (2026-08-27).** 원래 여기도 `D-` 에 `docs/decisions.md` 라 파일명·번호가 같은데 뜻이 남남이었다(저쪽 `D-011`=SQLAlchemy·MVC2 / 여기 `D-011`=법령 웹 원문 경로). **접두사를 `RAG-` 로, 파일을 `decisions-rag.md` 로 바꿨다** — 번호는 그대로(`D-027`=`RAG-027`). `RT-` 는 저쪽에 없어 유지 |
| 2 | **패키지 레이아웃** | `backend/` 밑 플랫 5개 — `crawler` `rag` `realtime` `tasks` `app` | uv **src 레이아웃** `backend/src/daengs_backend/` | 모든 import 가 깨진다 (`from rag.stages...` → `from daengs_backend...`). 저쪽 CLAUDE.md 가 **"`src/` 밑에 패키지를 더 둘지(`daengs_rag` 등)는 아직 정하지 않았다"** 고 명시 — 즉 **저쪽도 안 정한 자리**다 |
| 3 | **서빙 계층** | `app/`={controllers,services,dto,deps}, **`models/` 는 일부러 없다** (RAG-027) | `routers`=C / `services`=S / `repositories`=DAO / `models`+`schemas`=M (저쪽 `D-011`) | 이름이 다른 같은 MVC2 다. `controllers`→`routers`, `dto`→`schemas` 로 접으면 맞지만 **`repositories` 가 없다** — 여기는 SQL 을 `rag/stages/load.py`·`search.py` 가 직접 쥔다 |
| 4 | **DB 접근** | psycopg3 + **SQL 직접** (RAG-025) | **SQLAlchemy 2.0 async + asyncpg**, 세션은 `core.database.get_session` (저쪽 `D-011`) | 가장 손이 많이 갈 곳. 벡터 검색 SQL 을 ORM 으로 옮길지, `rag` 만 예외로 둘지 결정해야 한다 |
| 5 | **DB 인스턴스** | 로컬 compose `db`(pgvector) | **팀에 하나뿐**이고 서버 PC 에 있다. 개발 PC 는 붙기만 한다 | 🟢 **생각보다 작다.** 저쪽 `db/init/01_schema.sql` 에 **`documents` 가 이미 있고 DDL 이 여기와 같다**(2026-08-27 diff — 다른 것은 `D-` 참조를 뺀 주석 4줄뿐). 남은 건 **서버 DB 에 실제로 반영돼 있는지 확인**뿐이다. 저쪽 `db/init/` 은 볼륨 최초 1회만 도니 없으면 **`db/migrations/` 에 SQL 로** 남겨 손으로 적용하는 게 저쪽 규칙 |
| 6 | **`documents.category`** | CHECK(policy/travel/food) | **같은 CHECK** (policy/travel/food) | 레포 차이가 아니라 **양쪽 공통의 구멍**이다 — 2랩의 **펫보험**이 들어갈 값이 없다. 제약 교체 SQL 을 `db/migrations/` 에 |
| 7 | **Redis** | compose 에 `redis` 있음 (RAG-001 Celery 브로커) | compose 에 **없다** (nginx·backend·pgvector·pgadmin) | Celery·Beat 를 옮기려면 저쪽 compose 에 서비스 추가가 필요하다 |
| 8 | **env 이름** | 접두사 없음 (`LAW_OC`, `DATA_GO_KR_KEY`, …) | **`DAENGS_*`** 접두사 | `pydantic-settings` 설정을 맞추거나 이름을 바꿔야 한다 |
| 9 | **브랜치** | `main` 하나 | **`dev` 가 기본**, `main` 은 릴리즈 스냅샷 | PR 은 `dev` 로. 작업 단위는 **PR 본문 `## 작업 목록`** (저쪽 `docs/collaboration.md`, `.github/PULL_REQUEST_TEMPLATE.md`) |
| 10 | **배포** | 없음 | **`dev` 에 push·merge 하면 self-hosted 러너가 자동 배포** | ⚠️ 넣는 순간 서버에 뜬다. 아래 주의 |
| 11 | **torch** | `[dependency-groups] ml` + `pytorch-cu126` 인덱스(win32) | 없음 | 저쪽 backend 는 컨테이너로 돈다. `uv sync` 기본에 ml 이 안 붙게 **그룹 분리를 반드시 유지**할 것 |

- Python 은 **양쪽 다 `>=3.12,<3.13`** 이다. 여기만은 안 부딪힌다
- ⚠️ **10번이 조용한 지뢰다.** 서빙이 lifespan 에서 임베딩 모델을 CPU 로 상주시킨다(RAG-028 ①).
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
- **골든셋 라벨에 사람 판단이 든다** — 법제처 `관련 법령` 차용(RAG-022 ②)이 펫보험엔 안 통한다
- **RAG-024 모델 교체가 발동해 있다** — 승자 `Qwen/Qwen3-Embedding-0.6B` 로 바꾸는 것은 `--model` 한 번.
  ⚠️ **2랩은 코퍼스와 모델이 같이 바뀌는 랩**이라 1랩과의 차이 원인을 하나로 특정할 수 없다. 그 점을 명시하고 갈 것
- **RAG-003(하이브리드·리랭커)** — 검문소③이 근거를 만들어 뒀다: dense 가 질문의 *의도* 가 아니라 *표면 어휘* 를 따라간다
- **RAG-029 자리** — 검증질문 7개 중 **5개는 top-5 안에 정답 조항이 없다.** KPI 가 조항 인용이라 **틀린 조항 번호는 답이 없는 것보다 나쁘다.**
  방침(사용자, 2026-08-25): **먼저 한 세트 돌려보고 판단한다.** 설계 논의를 앞세우지 말 것
- `backend/main.py` 는 2줄 shim 이다. 이관하면서 정리 대상

---

## 6. 저쪽에서 첫 세션이 할 일

1. ~~`lap1.jsonl` 백업~~ ✅ **필요 없다** — 2026-08-27 부터 git 이 들고 간다 (§2, RAG-017 예외)
2. **§3 의 11개 중 무엇을 지금 맞출지 고른다.** 전부 한 번에 맞추면 PR 이 리뷰 불가능한 크기가 된다
3. ~~ADR 접두사를 정한다~~ ✅ **끝났다 (2026-08-27)** — `D-` → **`RAG-`**, 파일도 `docs/decisions.md` → `docs/decisions-rag.md`.
   추적 파일 84개에서 992곳을 바꿨고 **번호는 유지**했다(`D-027`=`RAG-027`). `RT-` 는 저쪽에 없어 그대로 둔다.
   ⚠️ **이 날짜 이전의 커밋 메시지와 PR #2·#3 본문은 옛 `D-` 표기**다 — 읽을 때 같은 번호의 `RAG-` 로 옮겨 읽을 것
4. **`dev` 에서 브랜치를 파고 PR 을 먼저 연다** — 저쪽도 여기와 같은 규칙이다(작업 전에 PR). 작업 단위는 PR 본문 `## 작업 목록`
5. 옮긴 뒤 **`uv run pytest` 가 365개를 통과하는지** 확인한다(DB 를 먼저 띄울 것 — §1 의 경고). 의존 방향 가드 2개(`test_import_direction*.py`)가 레이아웃 변경을 제일 먼저 잡아 줄 것이다
