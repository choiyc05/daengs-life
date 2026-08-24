"""반대 방향 가드 — `rag`·`realtime` 이 `crawler` 를 **어디까지** 참조하는가 (RT-001 ①-2).

`test_import_direction.py` 는 `crawler/` 만 훑어서 "crawler 가 위를 부르지 않는다"만 본다.
방향은 그것으로 지켜지지만 **범위**는 아무도 안 본다. D-018 의 "`rag` 가 `crawler` 를 참조하는
것은 경로 탐색 하나뿐"은 지금까지 문서에만 있는 규칙이었다.

범위가 왜 방향만큼 중요한가 — realtime 이 `Fetcher`·`store`·`seed_sources` 를 끌어오는 순간
**"실시간은 저장하지 않는다"**(`data/README.md` §5, D-012)가 흐려진다. realtime 은 크롤 대상이
아니고 `.meta.json` 도 만들지 않는다. 캐시하는 것은 측정소 목록 같은 정적 메타뿐이다.

**허용 목록은 패키지마다 다르다.** 하나로 뭉뚱그려 넓히면 realtime 을 좁힌 이유가 같이 사라진다.

파일을 나눈 이유 — `feat/rag` 와 `feat/realtime` 이 병렬이라 `test_import_direction.py` 를
양쪽이 고치면 충돌한다. 저기서는 `FORBIDDEN` 한 줄만 늘리고 새 검사는 여기로 뺐다.

검사는 `rglob` 로 훑으므로 **패키지 내부 배치와 무관하다** — D-023 이 `rag/` 를
`core/`+`stages/` 로 재배치해도 여기는 안 고친다.
"""
from __future__ import annotations

import ast
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]

# 패키지 → `crawler` 안에서 import 해도 되는 모듈. 여기 없으면 실패한다.
ALLOWED: dict[str, set[str]] = {
    # 경로 탐색(D-018·D-014) + 「법령」 조항 인용 파싱. 후자는 의도된 확장이다 —
    # `cites()` 에 허위 인용 19건을 잡아낸 규칙이 들어 있어 복사하면 그 지식이 갈라진다
    # (`rag/README.md` 설계 메모).
    "rag": {"crawler.core.config", "crawler.core.textutil"},
    # 경로 탐색 하나뿐 (RT-001 ①-2). `textutil` 은 한국 법령 문서용이라 realtime 이 쓸 일이
    # 없고, 목록이 갈려 있어야 그게 새로 들어오는 날 여기서 잡힌다.
    "realtime": {"crawler.core.config"},
}


def _crawler_imports(path: Path) -> list[tuple[int, str]]:
    """(줄번호, 가리키는 crawler 모듈). `crawler` 밖은 관심 없다."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found += [(node.lineno, a.name) for a in node.names
                      if a.name.split(".")[0] == "crawler"]
        elif isinstance(node, ast.ImportFrom):
            # level > 0 은 패키지 내부 상대 import 라 crawler 까지 못 나간다
            if node.level or not node.module:
                continue
            if node.module.split(".")[0] != "crawler":
                continue
            # `from crawler.core import textutil` 은 module 이 아니라 이름 쪽이 모듈이다.
            # 두 형태를 다 봐야 한다 — 한쪽만 보면 우회로가 생긴다.
            found += [(node.lineno, f"{node.module}.{a.name}") for a in node.names]
    return found


def _violations(allowed: set[str], root: Path) -> list[str]:
    out: list[str] = []
    for path in sorted(root.rglob("*.py")):
        for lineno, target in _crawler_imports(path):
            # `from crawler.core.config import DATA_DIR` 는 target 이
            # `crawler.core.config.DATA_DIR` 로 잡힌다 — 접두사가 허용되면 통과다.
            if any(target == ok or target.startswith(ok + ".") for ok in allowed):
                continue
            rel = path.relative_to(root.parent)
            out.append(f"{rel}:{lineno} imports {target!r}")
    return out


def test_packages_reach_only_the_allowed_crawler_modules() -> None:
    checked = 0
    for package, allowed in ALLOWED.items():
        root = BACKEND / package
        if not root.is_dir():
            continue                       # 아직 없는 패키지는 건너뛴다
        checked += 1
        found = _violations(allowed, root)
        assert not found, (
            f"`{package}` 가 허용 밖의 crawler 모듈을 import 했다 (RT-001 ①-2).\n"
            f"  허용: {', '.join(sorted(allowed))}\n  "
            + "\n  ".join(found)
            + f"\n\n정말 필요하면 ALLOWED['{package}'] 에 추가하고 **왜 넓혔는지**를 남길 것 — "
              "`rag` 의 textutil 이 그 선례다."
        )
    assert checked, "검사한 패키지가 하나도 없다 — ALLOWED 의 이름이 실제 디렉터리와 어긋났다"


def test_guard_actually_detects_a_violation(tmp_path: Path) -> None:
    """가드가 살아 있는지 — 위반 파일을 만들어 실제로 잡히는지 확인한다.

    이 확인이 없으면 검사기가 조용히 아무것도 안 보게 돼도 테스트는 계속 통과한다
    (`test_import_direction.py` 와 같은 이유로 붙인다).
    """
    fake = tmp_path / "realtime"
    (fake / "providers").mkdir(parents=True)
    (fake / "providers" / "bad.py").write_text(
        # 실제로 걱정하는 형태 그대로 — realtime 이 수집기를 끌어오는 순간이다
        "from crawler.core import store\n"
        "from crawler.core.config import DATA_DIR\n",
        encoding="utf-8")

    found = _violations(ALLOWED["realtime"], fake)
    assert len(found) == 1 and "crawler.core.store" in found[0], found


def test_the_allowed_prefix_rule_does_not_leak() -> None:
    """접두사 매칭이 `crawler.core.configX` 같은 이웃 모듈까지 열어주면 안 된다."""
    fake_ok = "crawler.core.config"
    for target, expected in [
        ("crawler.core.config", True),
        ("crawler.core.config.DATA_DIR", True),
        ("crawler.core.configuration", False),      # 접두사가 같지만 다른 모듈이다
        ("crawler.core.store", False),
    ]:
        got = target == fake_ok or target.startswith(fake_ok + ".")
        assert got is expected, target
