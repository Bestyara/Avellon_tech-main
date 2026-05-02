@echo on

REM Always run from repository root
cd /d "%~dp0.."

IF NOT "%1"=="" (
	goto %~1
) ELSE (
	call scripts\init.bat check
	goto run
)

:update
call git restore .
call git pull
goto init

:init
call scripts\init.bat init
goto run

:run
call venv\Scripts\activate
call python Main.py

:end
