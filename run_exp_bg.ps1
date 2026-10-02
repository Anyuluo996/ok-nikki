# 后台执行实验启动器: 需 admin(游戏 admin, 否则输入被 UIPI 丢弃)
Set-Location $PSScriptRoot
# 清理上次实验/日常的残留 python(可能是 admin 权限, 本脚本也是 admin)
Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
  Where-Object { $_.CommandLine -match 'exp_calendar_pm|exp_bg|probe\.py|run_daily' } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Start-Sleep -Milliseconds 800
& .\.venv\Scripts\python.exe scripts\run_daily.py --dry-run *> run_daily_final.log
