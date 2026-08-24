# rag/

제도·문서형 RAG 파트①의 **인덱싱 엔진** (D-018). `crawler` 가 받아 둔 원본을 검색 가능한 형태로 바꾼다.

```
data/raw  ──parse──▶ processed/parsed ──chunk──▶ processed/chunks
          ──embed──▶ processed/embeddings ──load──▶ postgres ──search──▶ app
```

```
rag/
├── __main__.py     CLI: list / parse / chunk / show   ← embed·load·search 가 같은 자리에 붙는다
├── config.py       경로. data/ 탐색은 crawler.core.config 것을 그대로 쓴다
├── ir.py           ★ 공통 중간 표현 6종 + Chunk/ChunkSet — 계층 간 계약
├── io.py           parsed/·chunks/ 입출력, 상류 해시 비교로 재실행 스킵
├── chunk.py        ★ 타입 기반 단일 청커 (D-021) — 소스별 분기가 생기면 안 된다
├── registry.py     meta 의 source_id → 파서 모듈 (스캔하지 않고 경로를 계산)
├── extract/                                     ← ① 포맷 층. 사이트를 모른다
│   └── boxtable.py 괘선 아트 표 파서 (D-020)
└── parsers/                                     ← ② 사이트 층
    ├── base.py     NAME / VERSION / parse() 계약
    └── law/
        ├── law_drf_api.py   법령 API XML — 조문·항·호·목 / 부칙 / 별표
        └── easylaw_pet.py   생활법령 해설 HTML — 소제목 계층 / 100문100답
```

**레이어는 crawler 와 같은 모양이다** (D-018). 소스가 20개가 되어도 새로 쓰는 코드는 ②뿐이어야 한다.

| 층 | 위치 | 아는 것 |
|---|---|---|
| ① 포맷 | `extract/` | PDF·HWPX·괘선표를 어떻게 여나. 소스를 모른다 |
| ② 사이트 | `parsers/{domain}/{source_id}.py` | 그 사이트의 태그·클래스·표 관례 |
| ③ 계약 | `ir.py` | 산출물 모양. 청커·임베더·적재기는 이것만 안다 |

## 왜 파서 개수가 늘어도 괜찮은가

파싱 전략은 소스마다 다르다. 다른 게 정상이고, **폭발을 막는 장치는 파서 개수 통제가 아니라
산출물 모양의 고정**이다. 모든 파서는 IR 6종만 뱉는다.

| type | 뜻 | 현재 | D-004 청킹 규칙 |
|---|---|---:|---|
| `article` | 번호 붙은 조항 | 629 | <2,000자 = 1청크 / 이상 = 항 단위 (목까지 포함) |
| `para` | 문단 | 552 | 부칙은 조 단위 · easylaw 는 소제목 밑에 모임 |
| `table` | 표(header + rows) | 89 | ≤1,000자 통짜 / 초과 시 논리 행 + `헤더: 값` |
| `heading` | 제목(level) | 97 | easylaw 는 청크 경계 + 캡션(h1 포함) · 법령 장·절은 무시 |
| `aside` | 강조 박스·도식 | 27 | easylaw ※박스만 독립 청크(22) · 별표 유래 5건 제외 |
| `qa` | 질문/답 쌍 | 10 | 통짜 1청크 + `관련 법령` 을 본문에 |

7번째 타입은 **청킹 규칙이 기존 6종과 다를 때만** 만든다. 그 외엔 기존 타입 + 속성으로 쓴다.

## 실행

```bash
cd backend
uv run python -m rag list                        # 원본 목록 + 파서 구현 여부
uv run python -m rag parse                       # 바뀐 원본만 파싱
uv run python -m rag parse --source law-drf-api -v
uv run python -m rag parse --force               # 원본이 그대로여도 다시
uv run python -m rag chunk                       # parsed → chunks (바뀐 것만)
uv run python -m rag chunk --dry-run             # 쓰지 않고 집계만
uv run python -m rag show "별표 4-2-라" --full    # 청크를 눈으로 (검문소①)
uv run pytest tests/test_parse.py tests/test_chunk.py tests/test_boxtable.py
```

`list` 의 표시는 셋이다 — `x` 파서 있음 / `(공백)` 파서 없음(할 일) / `-` 인덱싱 대상 아님(결정).
**둘을 섞으면 "아직 안 만든 파서"를 영영 못 알아챈다.** 후자는 `registry.NOT_INDEXED` 에 사유와 함께 적는다.

## parsed/ 산출물 (D-019)

원본 1건 = `processed/parsed/{raw_stem}.jsonl` 1개. **1행 = 문서 헤더**, 2행부터 = 요소(문서 순서 보존).

```jsonl
{"type":"document","doc_id":"…","raw_sha256":"eb24…","citation_url":"https://www.law.go.kr/법령/…","parser":"law_xml","parser_version":1,"counts":{…}}
{"type":"article","id":"…#제15조","section":"제15조","title":"등록대상동물의 등록 등","paragraphs":[…],"chars":812}
```

- **재파싱 스킵** — 헤더의 `raw_sha256` 과 `.meta.json` 의 `sha256` 을 비교한다. 크롤러의 변경 감지와
  같은 축이라 별도 상태 파일이 없다 (D-001 원칙 2 의 연장)
- **`source_url` 과 `citation_url` 은 다르다** — 전자는 원본을 받은 곳(법령 API 는 키가 `***` 로 가려져
  사람이 못 연다), 후자는 답변에 실을 링크. 나누지 않으면 그 `if` 가 청커·적재기·앱 세 층에 복제된다
- **요소 id 는 청크 id 의 근간**이다. 청커가 자른 위치를 덧붙여 `…#제101조제3항` 이 되고,
  그것이 골든셋(5단계)이 가리키는 주소이자 답변에 실릴 인용 문자열이다

## 파서 하나 추가하는 절차

1. **정찰** — `raw/` 원본을 열어 구조를 확인한다. 태그·클래스에 계층이 이미 있으면 그것을 쓴다
2. **모듈** — `parsers/{domain}/{source_id}.py` 에 `NAME` / `VERSION` / `parse(raw, doc) -> Parsed`
   - 도메인 폴더가 없으면 만든다 (`__init__.py` 없이 — namespace 패키지)
   - 요소는 **IR 6종만** 쓴다. 새 타입이 필요하면 먼저 D-018 을 갱신한다
   - 포맷 처리(PDF 열기, 표 격자)는 `extract/` 로 올린다 — 사이트가 달라도 반복되기 때문
3. **시험** — `parse --dry-run --limit 1 -v` 로 요소 수를 눈으로 본다
4. **테스트** — `tests/test_parse.py` 에 그 소스의 요소 수와 **질문 정답이 실제로 잡히는지**를 박는다.
   수치를 박아 두면 원문이 개정될 때 여기서 먼저 깨진다 — 6단계 점수만 조용히 떨어지는 것보다 낫다

## 설계 메모

- **격자를 못 세운 괘선 구간은 버리지 않고 `aside` 로 보존**한다(경고 1건). 구조를 잃는 것보다
  내용이 조용히 사라지는 것이 훨씬 나쁘다. 경고는 표 파서를 고칠 단서다
- **`crawler.core.textutil` 을 재사용한다** — `cites()` 는 허위 인용 19건을 잡아낸 규칙이 들어 있어
  복사하면 그 지식이 갈라진다. D-018 이 정한 `rag → crawler` 의존은 경로 탐색까지였고 여기서
  "한국 법령 문서 공통 텍스트 처리"까지 넓혔다 (방향은 그대로 한쪽)
- `data/` 는 git 미추적이라(D-017) 다른 PC 에는 없다. 테스트는 원본이 없으면 **실패가 아니라 skip** 이다

## chunks/ 산출물 (D-021)

`processed/chunks/{raw_stem}.jsonl` — **1행 = ChunkSet 헤더**(파일 수준 사실만), 2행부터 청크.
**청크 행은 자기완결적이다** — parsed 와 반대 방향이고, 이유는 D-021 ⑤A 에 있다. 하류 세 층
(임베더·평가·적재기)이 전부 파일 경계 없이 읽기 때문에 헤더에 두면 그 세 층이 헤더를 들고 다녀야 한다.

**실측 (2026-08-24, parsed 22건 → 청크 1,407)**

| 종류 | 개수 | 제외된 것 | 건수 |
|---|---:|---|---:|
| article | 720 | 부칙: 타법개정(제목) | 96 |
| table | 423 | 부칙: 단문 시행일 | 71 |
| para (부칙) | 192 | para: 소제목 밖 | 132 |
| heading (easylaw 소제목) | 40 | 표: 헤더 전무(서식) | 9 |
| aside (easylaw ※박스) | 22 | 부칙: 타법개정(조) | 7 |
| qa | 10 | aside: 별표 유래 | 5 |

- **제외는 항상 출력한다.** 조용한 소실이 이 프로젝트에서 두 번 문제가 됐다 (부칙 33건이
  `content_hash` 로 합쳐지던 것, 서식이 표로 들어와 있던 것)
- **2,000자 초과 3건은 막지 않고 경고한다** — ④ 가 폴백을 두지 않기로 했다. 하드 상한은
  7,500자 하나뿐이고 넘으면 실패시킨다(조용히 자르지 않는다)
- **`content` 중복 5건도 경고한다.** 합쳐지는 것 자체는 옳지만(내용이 같다) 조용한 것이 문제다.
  계산은 7단계 적재기 몫이고 청커는 드러내기만 한다

`tests/test_chunk.py` 가 **검문소①이다** — 질문 1~7 의 정답 청크 12개가 실재하는지 단언한다.
눈으로만 보면 다음 개정 때 아무도 다시 안 본다.
