@echo off
REM ===========================================================================
REM  dev.cmd - Sobe/para o sistema no Windows (pode dar duplo clique).
REM  Uso:  dev.cmd start | stop | status | restart
REM  Sem argumento: sobe tudo (start).
REM ===========================================================================
chcp 65001 >nul
cd /d "%~dp0.."
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0dev.ps1" %*
set EXITCODE=%ERRORLEVEL%
echo.
if %EXITCODE% NEQ 0 (
  echo  [31mTerminou com erros (codigo %EXITCODE%). Veja as mensagens acima.[0m
  pause
)
exit /b %EXITCODE%