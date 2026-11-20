@echo off
rem 本地预览站点页面：
rem   preview.cmd          打开热力图页 heatmap\index.html
rem   preview.cmd --home   打开首页 index.html
setlocal
if "%HEATMAP_SITE_REPO%"=="" set "HEATMAP_SITE_REPO=D:\Projects\主页设计\bihongcue876.github.io"
set "TARGET=%HEATMAP_SITE_REPO%\heatmap\index.html"
if /i "%~1"=="--home" set "TARGET=%HEATMAP_SITE_REPO%\index.html"
if not exist "%TARGET%" (
  echo [!] 没找到 %TARGET%
  echo     先把站点仓库拉下来，或者先跑一次 refresh.cmd
  pause
  exit /b 1
)
start "" "%TARGET%"
