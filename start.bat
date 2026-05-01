@echo off
echo.
echo  ====================================
echo   Indeed求人作る君 - 起動中...
echo  ====================================
echo.

cd /d %~dp0

if not exist .env (
  echo [ERROR] .env ファイルが見つかりません。
  echo .env.example をコピーして .env を作成し、ANTHROPIC_API_KEY を設定してください。
  pause
  exit /b 1
)

if not exist venv (
  echo [1/2] 仮想環境を作成中...
  python -m venv venv
  echo [2/2] パッケージをインストール中...
  venv\Scripts\pip install -r requirements.txt --quiet
)

echo サーバーを起動中: http://localhost:8000
echo 終了するには Ctrl+C を押してください
echo.
start "" http://localhost:8000
venv\Scripts\uvicorn main:app --host 0.0.0.0 --port 8000 --reload
pause
