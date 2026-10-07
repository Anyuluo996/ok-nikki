Set-Location D:\app\ok-nikki
$env:PYTHONIOENCODING = 'utf-8'
& D:\app\ok-nikki\.venv\Scripts\python.exe scripts\probe.py @args *> D:\app\ok-nikki\admin_probe.log
