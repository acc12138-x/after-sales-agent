# -*- coding: utf-8 -*-
"""克隆自检：确认从远端 clone 下来的仓库是完整的、能跑起来的。

由来
----
.gitignore 里曾有无锚定模式（`data/`、`_*.py`），git 会把它们匹配到
【任意层级】，于是这些源码被静默排除、从未提交：

    app/intent/data/intents.yaml   意图定义
    app/rules/data/*.yaml          规则配置
    app/services/data/*.json       演示数据
    app/integrations/__init__.py   包初始化

结果是：本机跑得好好的，别人 clone 下来却发现意图引擎和规则引擎是空的。
本脚本把这类「本机正常、克隆后残缺」的问题变成一条命令可验证的检查。

用法
----
    python scripts/clone_check.py           # 全部检查
    python scripts/clone_check.py -v        # 额外打印通过项
    python scripts/clone_check.py --tests   # 追加跑一遍单元测试（较慢）

退出码：0 全部通过；1 存在失败项
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

OK, BAD, WARN = "[✓]", "[✗]", "[!]"
_fail: list[str] = []
_warn: list[str] = []
_verbose = False


def head(title: str) -> None:
    print()
    print("=" * 68)
    print(title)
    print("=" * 68)


def ok(msg: str) -> None:
    if _verbose:
        print(f"  {OK} {msg}")


def fail(msg: str, detail: str = "") -> None:
    print(f"  {BAD} {msg}")
    if detail:
        print(f"      {detail}")
    _fail.append(msg)


def warn(msg: str, detail: str = "") -> None:
    print(f"  {WARN} {msg}")
    if detail:
        print(f"      {detail}")
    _warn.append(msg)


def git(*args: str) -> tuple[int, str]:
    """跑一条 git 命令，返回 (returncode, stdout)。git 不可用时返回 (-1, '')。"""
    try:
        r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                           text=True, encoding="utf-8", errors="replace")
        return r.returncode, (r.stdout or "").strip()
    except FileNotFoundError:
        return -1, ""


# ============================================================
# 1. 必备文件清单
# ============================================================
REQUIRED = [
    # ---- 意图引擎配置（曾经被 .gitignore 吞掉）----
    "app/intent/data/intents.yaml",
    # ---- 规则引擎配置（同上）----
    "app/rules/data/refund_rules.yaml",
    "app/rules/data/return_rules.yaml",
    "app/rules/data/shipping_rules.yaml",
    "app/rules/data/warranty_rules.yaml",
    # ---- 演示数据（同上）----
    "app/services/data/customers.json",
    "app/services/data/orders.json",
    "app/services/data/logistics.json",
    "app/services/data/products.json",
    # ---- 其它配置 ----
    "app/config/feishu_routes.yaml",
    # ---- 入口与依赖 ----
    "app/main.py",
    "requirements.txt",
    "pyproject.toml",
    ".env.example",
    # ---- 前端入口 ----
    "frontend/package.json",
    "frontend/src/main.js",
    "frontend/src/App.vue",
    "frontend/src/router/index.js",
    "frontend/index.html",
]


def check_required() -> None:
    head("1. 必备文件（既要存在于磁盘，也要已被 git 跟踪）")
    has_git = git("rev-parse", "--is-inside-work-tree")[0] == 0
    if not has_git:
        warn("当前不是 git 仓库或未安装 git，跳过「是否已跟踪」检查")

    n_ok = 0
    for rel in REQUIRED:
        p = ROOT / rel
        if not p.exists():
            fail(f"{rel}", "文件不存在 —— 克隆不完整")
            continue
        if not has_git:
            ok(f"{rel}（存在）")
            n_ok += 1
            continue
        rc, _ = git("ls-files", "--error-unmatch", rel)
        if rc != 0:
            fail(f"{rel}", "文件存在但【从未提交】—— 别人 clone 会缺这个文件")
        else:
            ok(f"{rel}")
            n_ok += 1

    if n_ok == len(REQUIRED):
        print(f"  {OK} {n_ok}/{len(REQUIRED)} 个必备文件均已提交")
    elif n_ok:
        print(f"  {OK} {n_ok}/{len(REQUIRED)} 个必备文件通过")


# ============================================================
# 2. 包完整性（每个含 .py 的目录都要有 __init__.py）
# ============================================================
def check_packages() -> None:
    head("2. Python 包完整性（__init__.py）")
    has_git = git("rev-parse", "--is-inside-work-tree")[0] == 0
    missing, untracked = [], []

    for d in sorted((ROOT / "app").rglob("*")):
        if not d.is_dir() or "__pycache__" in d.parts:
            continue
        if not any(f.suffix == ".py" for f in d.iterdir() if f.is_file()):
            continue
        init = d / "__init__.py"
        rel = init.relative_to(ROOT).as_posix()
        if not init.exists():
            missing.append(rel)
        elif has_git and git("ls-files", "--error-unmatch", rel)[0] != 0:
            untracked.append(rel)

    if missing:
        for m in missing:
            fail(f"缺少 {m}", "该目录有 .py 但没有 __init__.py")
    if untracked:
        for u in untracked:
            fail(f"{u} 未被 git 跟踪", "可能被 .gitignore 误排除（注意 `_*.py` 会匹配 __init__.py）")
    if not missing and not untracked:
        print(f"  {OK} app/ 下所有 Python 包都有 __init__.py，且均已提交")


# ============================================================
# 3. .gitignore 反向检查：有没有源码被忽略
# ============================================================
SOURCE_SUFFIX = {".py", ".yaml", ".yml", ".json", ".txt", ".md", ".vue", ".js"}


def check_ignored_source() -> None:
    head("3. 有没有源码被 .gitignore 误忽略")
    if git("rev-parse", "--is-inside-work-tree")[0] != 0:
        warn("不是 git 仓库，跳过")
        return

    hits = []
    for base in ("app", "scripts", "tests"):
        d = ROOT / base
        if not d.is_dir():
            continue
        for p in d.rglob("*"):
            if not p.is_file() or p.suffix not in SOURCE_SUFFIX:
                continue
            if "__pycache__" in p.parts:
                continue
            rel = p.relative_to(ROOT).as_posix()
            if git("check-ignore", "-q", rel)[0] == 0:
                hits.append(rel)

    if hits:
        for h in hits:
            fail(f"{h} 被 .gitignore 忽略", "源码不应被忽略，检查 .gitignore 是否缺少前导 /")
    else:
        print(f"  {OK} app/ scripts/ tests/ 下没有被忽略的源码文件")


# ============================================================
# 4. 配置文件可解析 + 内容非空
# ============================================================
def check_configs() -> None:
    head("4. 配置文件可解析且内容非空")
    import yaml

    try:
        with open(ROOT / "app/intent/data/intents.yaml", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        intents = data.get("intents") or []
        if not intents:
            fail("intents.yaml 里没有意图定义", "文件可能是空壳，检查是否漏提交内容")
        else:
            with_pat = sum(1 for i in intents if i.get("patterns") or i.get("keywords"))
            print(f"  {OK} intents.yaml：{len(intents)} 个意图，其中 {with_pat} 个带 pattern/keyword")
            ids = {i.get("id") for i in intents}
            for must in ("chitchat", "qa"):
                if must not in ids:
                    fail(f"intents.yaml 缺少内置意图 `{must}`")
                else:
                    ok(f"内置意图 {must} 存在")
    except FileNotFoundError:
        fail("app/intent/data/intents.yaml 不存在")
    except Exception as e:
        fail("intents.yaml 解析失败", str(e)[:160])

    rules_dir = ROOT / "app/rules/data"
    rules = sorted(rules_dir.glob("*.yaml")) if rules_dir.is_dir() else []
    if not rules:
        fail("app/rules/data 下没有规则文件", "规则引擎会是空的")
    else:
        total = 0
        empty = []
        for r in rules:
            try:
                d = yaml.safe_load(r.read_text(encoding="utf-8")) or {}
            except Exception as e:
                fail(f"{r.name} 解析失败", str(e)[:120])
                continue
            n = len(d.get("rules") or [])
            total += n
            if n == 0:
                empty.append(r.name)
        if empty:
            warn(f"这些规则文件里没有 rules 条目：{empty}")
        else:
            print(f"  {OK} 规则：{len(rules)} 个文件，共 {total} 条规则")

    data_dir = ROOT / "app/services/data"
    jsons = sorted(data_dir.glob("*.json")) if data_dir.is_dir() else []
    if not jsons:
        fail("app/services/data 下没有演示数据", "订单/客户/物流查询会没数据")
    else:
        for j in jsons:
            try:
                json.loads(j.read_text(encoding="utf-8"))
            except Exception as e:
                fail(f"{j.name} 不是合法 JSON", str(e)[:120])
        print(f"  {OK} 演示数据：{len(jsons)} 个 JSON 文件均可解析")


# ============================================================
# 5. 依赖与导入
# ============================================================
def check_imports() -> None:
    head("5. 依赖与导入自检")
    try:
        import fastapi  # noqa: F401
    except ImportError as e:
        fail("缺少运行依赖", f"{e} —— 先执行 pip install -r requirements.txt")
        return

    try:
        import app.main  # noqa: F401
        print(f"  {OK} import app.main 成功")
    except Exception as e:
        fail("import app.main 失败", f"{type(e).__name__}: {str(e)[:200]}")
        return

    try:
        from app.intent.factory import get_intent_engine
        eng = get_intent_engine()
        top = eng.classify_top("你好啊")
        if top and top.id == "chitchat":
            print(f"  {OK} 意图引擎可用（「你好啊」→ {top.id}）")
        else:
            fail("意图引擎结果异常", f"「你好啊」→ {top.id if top else 'None'}，应为 chitchat")
    except Exception as e:
        fail("意图引擎不可用", f"{type(e).__name__}: {str(e)[:200]}")

    try:
        from app.rules.factory import DEFAULT_DATA_DIR, get_engine
        from app.rules.loaders.yaml_loader import YamlLoader

        loaded = YamlLoader(DEFAULT_DATA_DIR).load()
        get_engine()          # 顺便确认引擎能正常构建
        if not loaded:
            fail("规则引擎载入 0 条规则", "app/rules/data 下的 YAML 可能是空壳")
        else:
            print(f"  {OK} 规则引擎可用（载入 {len(loaded)} 条规则）")
    except Exception as e:
        fail("规则引擎不可用", f"{type(e).__name__}: {str(e)[:200]}")


# ============================================================
# 6. 未提交的源码（提示，不算失败）
# ============================================================
def check_uncommitted() -> None:
    head("6. 未提交的源码（仅提示）")
    if git("rev-parse", "--is-inside-work-tree")[0] != 0:
        warn("不是 git 仓库，跳过")
        return
    rc, out = git("status", "--porcelain", "--untracked-files=all")
    if rc != 0 or not out:
        print(f"  {OK} 工作区干净，没有未提交内容")
        return
    src = [ln for ln in out.splitlines()
           if ln.startswith("??") and Path(ln[3:].strip()).suffix in SOURCE_SUFFIX]
    if src:
        for ln in src:
            warn(f"未提交：{ln[3:].strip()}", "确认它是你要保留的文件，然后 git add")
    else:
        print(f"  {OK} 没有未提交的源码文件（改动的是已跟踪文件或非源码）")


# ============================================================
# 7. 硬编码本机绝对路径
# ============================================================
# 由来：scripts/seed_*.py 曾经写死 os.chdir(r"I:\XMWJ\...")，
# 本机跑得好好的，一进 Docker / 服务器就 FileNotFoundError。
# 正确写法：ROOT = Path(__file__).resolve().parents[1]
ABS_PATH_RE = re.compile(r"""(["'])(?:[A-Za-z]:[\\/]|/home/|/Users/|/root/|/opt/apps/)""")


def check_hardcoded_paths() -> None:
    head("7. 硬编码本机绝对路径（会让脚本在 Docker / 服务器上失效）")
    hits = []
    for base in ("app", "scripts", "tests"):
        d = ROOT / base
        if not d.is_dir():
            continue
        for p in sorted(d.rglob("*.py")):
            if "__pycache__" in p.parts:
                continue
            try:
                lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
            except Exception:
                continue
            for i, line in enumerate(lines, 1):
                s = line.strip()
                if s.startswith("#"):
                    continue
                if ABS_PATH_RE.search(line):
                    hits.append((p.relative_to(ROOT).as_posix(), i, s[:90]))

    if hits:
        for f, i, s in hits:
            fail(f"{f}:{i} 写死了绝对路径", s)
    else:
        print(f"  {OK} app/ scripts/ tests/ 下没有硬编码的绝对路径")


# ============================================================
# 8. 单元测试
# ============================================================
def run_tests() -> None:
    head("7. 单元测试（意图识别）")
    try:
        r = subprocess.run(
            [sys.executable, "-m", "pytest", "tests/test_intent.py", "-q",
             "-p", "no:cacheprovider", "-o", "addopts="],
            cwd=ROOT, capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        )
        tail = (r.stdout or "").strip().splitlines()
        summary = next((l for l in reversed(tail) if "passed" in l or "failed" in l), "")
        if r.returncode == 0:
            print(f"  {OK} {summary}")
        else:
            fail("tests/test_intent.py 未通过", summary or (r.stdout or "")[-300:])
    except Exception as e:
        warn("无法运行测试", f"{type(e).__name__}: {str(e)[:160]}")


# ============================================================
def main() -> int:
    global _verbose
    ap = argparse.ArgumentParser()
    ap.add_argument("-v", "--verbose", action="store_true", help="打印通过项详情")
    ap.add_argument("--tests", action="store_true", help="追加运行单元测试")
    args = ap.parse_args()
    _verbose = args.verbose

    print(f"克隆自检  root = {ROOT}")

    check_required()
    check_packages()
    check_ignored_source()
    check_configs()
    check_imports()
    check_uncommitted()
    check_hardcoded_paths()
    if args.tests:
        run_tests()

    head("汇总")
    if _fail:
        print(f"  {BAD} 失败 {len(_fail)} 项：")
        for m in _fail:
            print(f"     - {m}")
    if _warn:
        print(f"  {WARN} 提示 {len(_warn)} 项：")
        for m in _warn:
            print(f"     - {m}")
    if not _fail:
        print(f"  {OK} 全部关键检查通过 —— 这份仓库是完整可用的")
        if not args.tests:
            print("     （加 --tests 可再跑一遍意图识别单元测试）")
    return 1 if _fail else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
