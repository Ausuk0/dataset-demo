@echo off
chcp 65001 >nul
rem Полный прогон конвейера: сбор -> проверка -> дедупликация -> отчёт.
rem Критерии ТЗ меняются в config.yaml. Нужны Python 3.10+ и ffmpeg/ffprobe в PATH.
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe (
  echo Создаю виртуальное окружение .venv ...
  python -m venv .venv || goto :err
  .venv\Scripts\python.exe -m pip install -q -r requirements.txt || goto :err
)
set PY=.venv\Scripts\python.exe
set PYTHONIOENCODING=utf-8
echo === 1/4 Сбор кандидатов (collect.py)
%PY% -u collect.py || goto :err
echo === 2/4 Техническая проверка (check.py)
%PY% -u check.py || goto :err
echo === 3/4 Почти-дубли (dedup.py)
%PY% -u dedup.py || goto :err
echo === 4/4 Отчёт (report.py)
%PY% -u report.py || goto :err
echo.
echo Готово. Результат — в папке output\
exit /b 0
:err
echo Ошибка на шаге выше. Повторный запуск продолжит с кэшем в raw\ и tmp\.
exit /b 1
