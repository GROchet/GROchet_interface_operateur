@echo off
python -m venv venv
call venv\Scripts\activate
pip install -r requirements.txt --upgrade
echo.
echo venv ready! Run "venv\Scripts\activate" to activate it or press "ENTER" to continue and launch app.
pause
@echo off
call venv\Scripts\activate
python interfaceOperateur.py