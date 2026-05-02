@echo off
setlocal

cd /d "%~dp0\.."
set "ROOT=%cd%"

if not exist backend\.env (
  echo Missing backend\.env file.
  exit /b 1
)

if not exist "%ROOT%\.venv\Scripts\python.exe" (
  echo Creating virtual environment .venv ...
  uv venv .venv
  if errorlevel 1 goto :fail
)

echo [1/3] Installing backend dependencies into .venv ...
uv pip install -r backend\requirements.txt
if errorlevel 1 goto :fail

set "PY=%ROOT%\.venv\Scripts\python.exe"

echo [2/3] Running Django migrations...
"%PY%" backend\django_app\manage.py makemigrations
"%PY%" backend\django_app\manage.py migrate
if errorlevel 1 goto :fail

echo [3/3] Starting Django and FastAPI in separate windows...
start "Glunova Django" /D "%ROOT%" "%PY%" backend\django_app\manage.py runserver 0.0.0.0:8000
start "Glunova FastAPI" /D "%ROOT%" "%PY%" -m uvicorn --app-dir backend/fastapi_ai main:app --host 0.0.0.0 --port 8001 --reload

echo Backends started:
echo - Django: http://localhost:8000
echo - FastAPI: http://localhost:8001
echo - FastAPI Docs: http://localhost:8001/docs
exit /b 0

:fail
echo Failed to start local backends.
exit /b 1
