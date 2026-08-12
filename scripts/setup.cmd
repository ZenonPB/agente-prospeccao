@echo off
REM ===========================================================================
REM  setup.cmd - Setup do Windows sem Docker (pode dar duplo clique).
REM  Equivalente a:  powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
REM  Repassa parametros opcionais, ex.: setup.cmd -StartDev
REM ===========================================================================
chcp 65001 >nul
cd /d "%~dp0.."
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1" %*
set EXITCODE=%ERRORLEVEL%
echo.
if %EXITCODE% NEQ 0 (
  echo  [31mSetup terminou com erros (codigo %EXITCODE%). Veja as mensagens acima.[0m
) else (
  echo  OK. O setup foi concluido com sucesso.
)
echo  Para subir o sistema:  scripts\dev.cmd start   (ou de duplo clique em dev.cmd)
echo.
pause
exit /b %EXITCODE%