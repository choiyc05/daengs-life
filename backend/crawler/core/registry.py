"""seed_sources.yaml 로드 + id → Source 클래스 매핑.

규약: yaml id 'easylaw-pet' → 모듈 crawler.sources.easylaw_pet → 그 안의 Source 서브클래스 하나.
모듈이 없으면 '아직 구현 안 된 소스'다 (list 명령에서 표시).
"""
from __future__ import annotations

import importlib
import inspect
from typing import Any

import yaml

from . import config
from ..sources.base import Source


def load_seeds() -> dict[str, dict[str, Any]]:
    with config.SEED_FILE.open(encoding="utf-8") as f:
        items = yaml.safe_load(f)
    return {it["id"]: it for it in items}


def resolve(source_id: str) -> type[Source] | None:
    modname = f"crawler.sources.{source_id.replace('-', '_')}"
    try:
        mod = importlib.import_module(modname)
    except ModuleNotFoundError as e:
        if e.name == modname:
            return None
        raise                                 # 모듈 내부 import 오류는 숨기지 않는다
    for _, obj in inspect.getmembers(mod, inspect.isclass):
        if issubclass(obj, Source) and obj is not Source and obj.__module__ == modname:
            return obj
    return None


def build(source_id: str) -> Source:
    seeds = load_seeds()
    if source_id not in seeds:
        raise KeyError(f"unknown source id: {source_id} (seed_sources.yaml 에 없음)")
    cls = resolve(source_id)
    if cls is None:
        raise KeyError(f"source '{source_id}' 는 yaml 에 있지만 crawler/sources/ 에 모듈이 없음")
    return cls(seeds[source_id])
