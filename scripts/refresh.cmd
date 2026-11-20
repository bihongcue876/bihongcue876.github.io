@echo off
rem 一键刷新交互式热力图并推送到 github.io 站点仓库。
rem   refresh.cmd         正常刷新（有变化才提交 + 推送）
rem   refresh.cmd --dry   只看会改什么，不提交
setlocal
wsl.exe -d Debian -e bash -lc "~/.local/bin/heatmap-refresh %*"
if errorlevel 1 echo [!] 失败，看看 .heatmap.log
pause
