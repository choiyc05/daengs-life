# data/

크롤링 원본과 가공 산출물 저장 폴더. **원본은 불변**, 가공물은 언제든 재생성 가능해야 한다.

## 구조

```
data/
├── manifests/        # 시드 소스 목록(seed_sources.yaml), 크롤 로그
├── raw/              # 크롤링 원본 (PDF/HTML/XML/JSON) — 도메인별 하위 폴더
│   ├── law/          # 법령 원문 (동물보호법, 가축전염병예방법 …)
│   ├── registration/ # 동물등록
│   ├── vaccination/  # 예방접종 (의무 + 스케줄)
│   ├── leash-muzzle/ # 목줄·입마개·맹견
│   ├── transport/    # 대중교통·항공 동반 이동
│   ├── subsidy/      # 지자체 지원사업 (공고문·조례·보조금24)
│   └── insurance/    # 펫보험 약관
├── processed/        # 정제·청킹 결과 (jsonl) — DB 적재 입력
└── reference/        # 정적 참조 데이터 (에어코리아 측정소 목록, 기상청 격자 변환표 등)
```

## 규칙

1. **원본 불변** — `raw/` 파일은 수정 금지. 재크롤 시 날짜가 다른 새 파일로 저장.
2. **파일명**: `{slug}__{YYYYMMDD}.{ext}` (예: `animal-protection-act__20260819.xml`)
3. **출처 메타 필수** — 원본 1개당 같은 이름의 `.meta.json` 1개. 스키마는 `documents` 테이블 컬럼에 맞춘다:

   ```json
   {
     "source_url": "https://www.law.go.kr/법령/동물보호법",
     "document_title": "동물보호법",
     "source": "법제처 국가법령정보센터",
     "source_type": "api",
     "category": "policy",
     "subcategory": "leash-muzzle",
     "fetched_at": "2026-08-19T13:00:00+09:00",
     "license": "공공누리 제1유형",
     "trust_level": "law",
     "notes": ""
   }
   ```

   - `source_type`: `pdf | web | api | manual` (DB CHECK 제약과 동일)
   - `trust_level`: `law`(법령) > `official`(공공기관 안내) > `guideline`(협회·수의학 가이드) — 접종 스케줄처럼 법정 근거가 없는 문서 구분용
   - **meta 없는 파일은 인덱싱 금지.** "출처 링크 + 조항 번호를 함께 응답"이 성능 지표라 출처 없는 문서는 가치가 없음.
4. **대용량 금지** — 파일당 100MB 초과 금지(GitHub 하드리밋). 약관 PDF 수준(수 MB)은 커밋 OK. 무거워지면 Git LFS/외부 스토리지 전환.
5. **realtime(날씨·대기질)은 저장하지 않는다** — API 직조회 대상. 단, 측정소 목록·격자 변환표 같은 정적 메타는 `reference/`에 캐시 (월 1회 갱신 권장).

## DB category 매핑 (documents.category CHECK 제약 기준)

| RAG 도메인 | category | subcategory 제안 |
|---|---|---|
| 동물등록 | `policy` | `registration` |
| 예방접종 — 법정 의무(광견병) | `policy` | `vaccination` |
| 예방접종 — 스케줄·케어 | `care` | `vaccination-schedule` |
| 목줄·입마개·맹견 | `policy` | `leash-muzzle` |
| 동반 이동 (철도/지하철/버스/항공/검역) | `travel` | `transport-rail` 등 |
| 지자체 지원사업 | `policy` | `subsidy` |
| 펫보험 | `policy` | `insurance` |

시드 소스 목록: [manifests/seed_sources.yaml](manifests/seed_sources.yaml)
소스 조사 문서: [../docs/data-sources.md](../docs/data-sources.md)
