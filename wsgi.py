"""
PythonAnywhere 用 WSGI エントリポイント

PythonAnywhereのWeb設定で
  Source code:  /home/YOUR_USERNAME/indeed_job_creator
  WSGI file:    /home/YOUR_USERNAME/indeed_job_creator/wsgi.py
  Virtualenv:   /home/YOUR_USERNAME/.virtualenvs/indeed_job_creator
と設定してください。
"""
import sys
import os

# プロジェクトをPythonパスに追加
project_home = '/home/YOUR_USERNAME/indeed_job_creator'  # ← ユーザー名を変更
if project_home not in sys.path:
    sys.path.insert(0, project_home)

# 環境変数（PythonAnywhereのWeb設定 > Environment variablesで設定するか、ここに書く）
os.environ.setdefault('ANTHROPIC_API_KEY', 'sk-ant-YOUR_KEY_HERE')  # ← 要変更
os.environ.setdefault('DB_PATH', f'{project_home}/indeed_jobs.db')
os.environ.setdefault('SERVE_STATIC', 'false')  # 静的ファイルはPAのStatic Filesで配信

# FastAPI(ASGI) → WSGI に変換
from main import app  # noqa: E402
from a2wsgi import ASGIMiddleware  # noqa: E402

application = ASGIMiddleware(app)
