# 自动拉起测试: 杀掉游戏+残留 python, 再跑 run_daily --dry-run(验证自动拉起+登录+全链, 不耗体力)
Set-Location $PSScriptRoot
Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
  Where-Object { $_.CommandLine -match 'exp_calendar_pm|exp_bg|probe\.py|run_daily' } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Stop-Process -Name X6Game-Win64-Shipping -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 3
& .\.venv\Scripts\python.exe scripts\run_daily.py --dry-run *> run_daily_final.log
