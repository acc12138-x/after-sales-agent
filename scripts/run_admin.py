
"""启动 Streamlit 管理后台。"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
dashboard = ROOT / "app" / "admin" / "dashboard.py"

cmd = [
    sys.executable, "-m", "streamlit", "run", str(dashboard),
    "--server.port", "8501",
    "--server.address", "127.0.0.1",
    "--browser.gatherUsageStats", "false",
]
print("[启动] Streamlit 管理后台 -> http://127.0.0.1:8501")
subprocess.run(cmd)
