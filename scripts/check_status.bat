@echo off
chcp 65001 >nul
title 监听程序运行状态
powershell -NoProfile -ExecutionPolicy Bypass -Command "$p=@(Get-CimInstance Win32_Process -Filter \"Name='pythonw.exe' OR Name='python.exe'\" | Where-Object { $_.CommandLine -like '*crypto_tracker.py*' -or $_.CommandLine -like '*a_stock_realtime.py*' }); foreach($i in @(@('加密货币监听','*crypto_tracker.py*'),@('A股监听','*a_stock_realtime.py*'))){$m=@($p | Where-Object { $_.CommandLine -like $i[1] }); if($m.Count -gt 0){ foreach($x in $m){ $t=(Get-Process -Id $x.ProcessId -ErrorAction SilentlyContinue).StartTime.ToString('MM-dd HH:mm'); Write-Host ($i[0]+'：运行中   PID='+$x.ProcessId+'   启动于 '+$t) -ForegroundColor Green } } else { Write-Host ($i[0]+'：未运行') -ForegroundColor Gray } }; Write-Host ''; Write-Host '提示：任务管理器 → 详细信息 → 右键列标题 → 选择列 → 勾选“命令行”，即可看到脚本路径区分两个 pythonw.exe'"
echo.
pause
