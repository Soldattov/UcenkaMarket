@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo.
echo === УценкаМаркет — сервер для локальной сети ===
echo.
echo В браузере НЕ открывайте http://0.0.0.0:8000 — так не работает.
echo.
echo   На ЭТОМ компьютере:  http://127.0.0.1:8000/
echo   На телефоне в Wi-Fi:  http://ВАШ_IP:8000/
echo                         (узнайте IP: ipconfig — строка IPv4)
echo.
echo Запуск сервера...
echo.
if exist "venv\Scripts\python.exe" (
  venv\Scripts\python.exe manage.py runserver 0.0.0.0:8000
) else (
  python manage.py runserver 0.0.0.0:8000
)
