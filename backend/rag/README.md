# rag/

제도·문서형 RAG 파트①의 **인덱싱 엔진** (D-018). `crawler` 가 받아 둔 원본을 검색 가능한 형태로 바꾼다.

```
data/raw  ──parse──▶ processed/parsed ──chunk──▶ processed/chunks
          ──embed──▶ processed/embeddings ──load──▶ postgres ──search──▶ app
```

```
rag/
├── __main__.py     CLI: list / parse            ← chunk·embed·load·search 가 같은 자리에 붙는다
├── config.py       경로. data/ 탐색은 crawler.core.config 것을 그대로 쓴다
├── ir.py           ★ 공통 중간 표현 6종 — 모든 파서가 지켜야 할 계약
├── io.py           parsed/ 입출력, raw_sha256 비교로 재파싱 스킵
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
| `article` | 번호 붙은 조항 | 629 | <2,000자 = 1청크 / 이상 = 항 단위 |
| `para` | 문단 | 552 | heading 밑에 모임 |
| `table` | 표(header + rows) | 89 | 논리 행 + 헤더 3종 복제 |
| `heading` | 제목(level) | 97 | 경계로만 사용 |
| `aside` | 강조 박스·도식 | 27 | 독립 청크 후보 |
| `qa` | 질문/답 쌍 | 10 | 통짜 1청크 |

7번째 타입은 **청킹 규칙이 기존 6종과 다를 때만** 만든다. 그 외엔 기존 타입 + 속성으로 쓴다.

## 실행

```bash
cd backend
uv run python -m rag list                        # 원본 목록 + 파서 구현 여부
uv run python -m rag parse                       # 바뀐 원본만 파싱
uv run python -m rag parse --source law-drf-api -v
uv run python -m rag parse --force               # 원본이 그대로여도 다시
uv run pytest tests/test_parse.py tests/test_boxtable.py
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
