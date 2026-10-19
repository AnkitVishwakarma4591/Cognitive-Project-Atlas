@echo off
echo ========================================================
echo   Running Project Atlas Test Suite & Benchmarks
echo ========================================================

call .\venv\Scripts\activate

echo [1/2] Running Unit & Security Tests...
pytest -v

echo.
echo [2/2] Running 28-Question Benchmark Evaluation...
python evaluation/run_evaluation.py

pause
