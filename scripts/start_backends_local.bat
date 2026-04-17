@echo off
setlocal

cd /d "%~dp0\.."

if not exist backend\.env (
  echo Missing backend\.env file.
  exit /b 1
)

echo [1/3] Installing backend dependencies...
uv pip install -r backend\requirements.txt
if errorlevel 1 goto :fail

echo [2/3] Running Django migrations...
python backend\django_app\manage.py migrate
if errorlevel 1 goto :fail

echo [3/3] Starting Django and FastAPI in separate windows...
start "Glunova Django" cmd /k "cd /d %cd% && python backend\django_app\manage.py runserver 0.0.0.0:8000"
start "Glunova FastAPI" cmd /k "cd /d %cd% && python -m uvicorn --app-dir backend/fastapi_ai main:app --host 0.0.0.0 --port 8001 --reload"

echo Backends started:
echo - Django: http://localhost:8000
echo - FastAPI: http://localhost:8001
echo - FastAPI Docs: http://localhost:8001/docs
exit /b 0

:fail
echo Failed to start local backends.
exit /b 1
