"""raw/ 저장 + .meta.json + crawl_log.jsonl. data/README.md 규칙 1~4 의 구현.

변경 감지(D-001 원칙 2):
  같은 slug 의 최신 .meta.json 과 sha256 을 비교한다.
  같으면 아무것도 쓰지 않고 로그에 changed:false 만 남긴다.
  다르면 오늘 날짜로 새 원본 + 새 meta 를 쓴다 (옛 파일은 지우지 않음 — 원본 불변).

sha256 은 '콘텐츠 지문'이다:
  html 은 extract() 가 뽑은 본문 텍스트의 해시 — 조회수·세션값 같은 노이즈로
  매번 changed 가 뜨는 것을 막기 위해 원본 바이트가 아니라 본문을 본다.
  pdf/xml/json 등 바이너리·구조화 응답은 원본 바이트 해시.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from . import config
from .fetch import FetchResult
from ..sources.base import Extracted, Source, Target


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def now_kst() -> datetime:
    return datetime.now(config.KST)


@dataclass
class StoreResult:
    raw_file: str | None          # data/raw 기준 상대경로 (저장 안 했으면 None)
    sha256: str
    changed: bool
    previous_sha256: str | None


class Store:
    def __init__(self, *, dry_run: bool = False, force: bool = False) -> None:
        self.dry_run = dry_run
        self.force = force
        self.run_id = now_kst().strftime("%Y%m%d-%H%M%S")

    # ------------------------------------------------------------ meta lookup
    @staticmethod
    def _latest_meta(domain_dir: Path, slug: str) -> dict[str, Any] | None:
        """같은 slug 의 meta 중 날짜가 가장 최신인 것. 파일명 규칙 {slug}__{YYYYMMDD}.meta.json"""
        cands = sorted(domain_dir.glob(f"{slug}__*.meta.json"))
        if not cands:
            return None
        return json.loads(cands[-1].read_text(encoding="utf-8"))

    # ------------------------------------------------------------ save
    def save(self, src: Source, target: Target, res: FetchResult, ext: Extracted | None) -> StoreResult:
        domain_dir = config.RAW_DIR / src.domain
        fingerprint = sha256_text(ext.text) if (ext and src.format == "html") else sha256_bytes(res.content)

        prev = self._latest_meta(domain_dir, target.slug)
        prev_sha = prev.get("sha256") if prev else None
        changed = self.force or prev_sha != fingerprint

        if not changed or self.dry_run:
            return StoreResult(raw_file=None, sha256=fingerprint, changed=changed, previous_sha256=prev_sha)

        today = now_kst().strftime("%Y%m%d")
        stem = f"{target.slug}__{today}"
        domain_dir.mkdir(parents=True, exist_ok=True)
        raw_path = domain_dir / f"{stem}.{target.ext}"
        meta_path = domain_dir / f"{stem}.meta.json"
        raw_rel = raw_path.relative_to(config.RAW_DIR).as_posix()

        raw_path.write_bytes(res.content)
        meta = {
            # --- data/README.md 규칙 3 필드 (documents 컬럼 대응) ---
            "source_id": src.id,
            "source_url": res.final_url,
            "document_title": (ext.title if ext else None) or target.meta.get("title"),
            "source": src.org,
            "source_type": src.source_type,
            "format": src.format,
            "category": src.category,
            "subcategory": src.subcategory,
            "trust_level": src.trust_level,
            "published_at": (ext.published_at if ext else None) or target.meta.get("published_at"),
            "fetched_at": now_kst().isoformat(timespec="seconds"),
            "sha256": fingerprint,
            "license": src.license,
            "notes": target.meta.get("notes", ""),
            # --- 추적용 ---
            "raw_file": raw_rel,
            "run_id": self.run_id,
            "http_status": res.status,
            "content_type": res.content_type,
            "bytes": len(res.content),
            "cites": ext.cites if ext else [],
            "previous_sha256": prev_sha,
        }
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
        return StoreResult(raw_file=raw_rel, sha256=fingerprint, changed=True, previous_sha256=prev_sha)

    # ------------------------------------------------------------ log
    def log(self, src: Source, target: Target, *, status: int | None, result: StoreResult | None,
            error: str | None = None) -> None:
        """crawl_log.jsonl 한 줄. dry-run 에서는 쓰지 않는다. 실패도 반드시 남긴다 (규칙 4)."""
        if self.dry_run:
            return
        line = {
            "run_id": self.run_id,
            "source_id": src.id,
            "slug": target.slug,
            "url": target.url,
            "raw_file": result.raw_file if result else None,
            "status": status,
            "sha256": result.sha256 if result else None,
            "changed": result.changed if result else None,
            "fetched_at": now_kst().isoformat(timespec="seconds"),
            "error": error,
        }
        config.MANIFEST_DIR.mkdir(parents=True, exist_ok=True)
        with config.CRAWL_LOG.open("a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(line, ensure_ascii=False) + "\n")
