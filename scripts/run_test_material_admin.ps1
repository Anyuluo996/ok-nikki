Set-Location D:\app\ok-nikki
# 清掉残留的探索进程
Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -like '*exp_realm_mat.py*' -or $_.CommandLine -like '*test_material_passport.py*' } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 1
$env:PYTHONIOENCODING = 'utf-8'
& D:\app\ok-nikki\.venv\Scripts\python.exe scripts\test_material_passport.py *> D:\app\ok-nikki\test_material.log
