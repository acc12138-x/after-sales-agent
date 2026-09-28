import subprocess
VENV_PY = r"I:\XMWJ\PYxm\venvs\easkb-agent\Scripts\python.exe"

print("=" * 60)
print("[1] ragas 版本")
print("=" * 60)
r = subprocess.run([VENV_PY, "-m", "pip", "show", "ragas"],
                   capture_output=True, text=True)
print(r.stdout)

print("=" * 60)
print("[2] 尝试 import ragas（完整错误）")
print("=" * 60)
r = subprocess.run([VENV_PY, "-c", "import ragas"],
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
if r.returncode == 0:
    print("[OK] import 成功")
else:
    print("STDOUT:", r.stdout)
    print("STDERR:", r.stderr[:2000])

print()
print("=" * 60)
print("[3] ragas 关键子模块")
print("=" * 60)
for mod in ["ragas.evaluation", "ragas.metrics", "ragas.llms", "ragas.embeddings"]:
    r = subprocess.run([VENV_PY, "-c", f"import {mod}; print('OK: {mod}')"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode == 0:
        print(r.stdout.strip())
    else:
        # 只看最后一行错误
        lines = r.stderr.strip().split("\n")
        print(f"ERR: {mod}")
        for l in lines[-3:]:
            print("    " + l)

print()
print("=" * 60)
print("[4] 可用的 ragas 子模块")
print("=" * 60)
r = subprocess.run([VENV_PY, "-c",
    "import pkgutil, ragas; print([m.name for m in pkgutil.iter_modules(ragas.__path__)])"],
    capture_output=True, text=True, encoding="utf-8", errors="replace")
print(r.stdout or r.stderr[:500])
