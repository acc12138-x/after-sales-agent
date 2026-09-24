
"""一键启动：FastAPI + frpc + Streamlit

用法:
    python scripts\start_all.py

Ctrl+C 一次停止全部。
"""
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENV_PY = Path(r"I:\XMWJ\PYxm\venvs\easkb-agent\Scripts\python.exe")
FRP_DIR = Path(r"I:\XMWJ\PYxm\frp")

# 所有子进程统一日志目录
LOG_DIR = ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)

# 后台运行标志（Windows）
CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0

_procs = []


def port_open(host, port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        try:
            s.connect((host, port))
            return True
        except Exception:
            return False


def frpc_running():
    try:
        import psutil
        for p in psutil.process_iter(["name"]):
            if p.info["name"] and "frpc" in p.info["name"].lower():
                return True
    except ImportError:
        pass
    return False


def start(name, cmd, cwd, log_name, wait_port=None):
    if wait_port and port_open("127.0.0.1", wait_port):
        print(f"  [跳过] {name} 已在运行 (端口 {wait_port})")
        return None

    log_path = LOG_DIR / log_name
    log_file = open(log_path, "a", encoding="utf-8", buffering=1)

    print(f"  [启动] {name}  ->  {log_path}")
    p = subprocess.Popen(
        cmd,
        cwd=str(cwd),
        stdout=log_file,
        stderr=subprocess.STDOUT,
        creationflags=CREATE_NO_WINDOW,
    )
    _procs.append((name, p, log_file))
    return p


def wait_port(host, port, timeout=30):
    start_t = time.time()
    while time.time() - start_t < timeout:
        if port_open(host, port):
            return True
        time.sleep(0.5)
    return False


def stop_all():
    print()
    print("=" * 50)
    print("  正在停止所有服务...")
    print("=" * 50)
    for name, p, log_file in _procs:
        if p.poll() is None:
            print(f"  [停止] {name}")
            try:
                p.terminate()
                try:
                    p.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    p.kill()
            except Exception as e:
                print(f"    错误: {e}")
        try:
            log_file.close()
        except Exception:
            pass
    print()
    print("  ✅ 全部已停止")


def main():
    os.environ.setdefault("NO_PROXY", "127.0.0.1,localhost,::1")
    os.environ.setdefault("no_proxy", "127.0.0.1,localhost,::1")

    print()
    print("=" * 50)
    print("  ServiceMind 一键启动")
    print("=" * 50)
    print()

    # ---------- 1. FastAPI ----------
    start(
        "FastAPI",
        [str(VENV_PY), "-m", "uvicorn", "app.main:app",
         "--host", "127.0.0.1", "--port", "8000"],
        ROOT,
        "fastapi.log",
        8000,
    )
    if not wait_port("127.0.0.1", 8000, 20):
        print("  ⚠️  FastAPI 未在 20 秒内就绪，看 logs/fastapi.log")
    else:
        print("  ✅ FastAPI 就绪")

    # ---------- 2. frpc ----------
    if frpc_running():
        print("  [跳过] frpc 已在运行")
    else:
        start("frpc", [str(FRP_DIR / "frpc.exe"), "-c", "frpc.toml"],
              FRP_DIR, "frpc.log")
        time.sleep(2)
        print("  ✅ frpc 已启动")

    # ---------- 3. Streamlit ----------
    start(
        "Streamlit",
        [str(VENV_PY), "-m", "streamlit", "run", "app/admin/dashboard.py",
         "--server.port", "8501", "--server.address", "127.0.0.1",
         "--browser.gatherUsageStats", "false", "--server.headless", "true"],
        ROOT,
        "streamlit.log",
        8501,
    )
    if not wait_port("127.0.0.1", 8501, 20):
        print("  ⚠️  Streamlit 未在 20 秒内就绪，看 logs/streamlit.log")
    else:
        print("  ✅ Streamlit 就绪")

    print()
    print("=" * 50)
    print("  🌐 管理后台:  http://127.0.0.1:8501")
    print("  🔧 FastAPI:   http://127.0.0.1:8000/docs")
    print("  📋 日志目录:  " + str(LOG_DIR))
    print("=" * 50)
    print()
    print("  按 Ctrl+C 停止所有服务")
    print()

    # 打开浏览器（可选）
    try:
        import webbrowser
        time.sleep(1)
        webbrowser.open("http://127.0.0.1:8501")
    except Exception:
        pass

    # 主循环，检测子进程死亡
    try:
        while True:
            time.sleep(2)
            for name, p, _ in _procs:
                if p.poll() is not None:
                    print(f"  ⚠️  {name} 已退出 (code={p.returncode})")
    except KeyboardInterrupt:
        stop_all()


if __name__ == "__main__":
    main()
