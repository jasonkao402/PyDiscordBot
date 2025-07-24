@echo off
echo Starting Schedule Generator Flask GUI...
echo.
echo Make sure you have installed the requirements:
echo pip install -r requirements.txt
echo.
echo Opening browser to http://127.0.0.1:5000
echo.

cd /d "%~dp0"
start http://127.0.0.1:5000
python LLM_tests/flask_app.py

pause
