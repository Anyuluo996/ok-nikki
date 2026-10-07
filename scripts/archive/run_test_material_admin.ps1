param([string]$Phase = 'all')
Set-Location D:\app\ok-nikki
# 清掉残留的测试进程
Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -like '*test_material_passport.py*' -and $_.ProcessId -ne $PID } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 1
$env:PYTHONIOENCODING = 'utf-8'
& D:\app\ok-nikki\.venv\Scripts\python.exe scripts\test_material_passport.py $Phase *> "D:\app\ok-nikki\test_$Phase.log"
