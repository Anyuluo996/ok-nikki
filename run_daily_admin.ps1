# 一键日常入口: 右键"使用 PowerShell 运行"并在 UAC 中点"是" (游戏以管理员运行, 本脚本必须提权才能发送点击)
# 也可在管理员 PowerShell 中执行: powershell -ExecutionPolicy Bypass -File D:\app\ok-nikki\run_daily_admin.ps1
$ErrorActionPreference = 'Stop'
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Start-Process pwsh -Verb RunAs -ArgumentList '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $PSCommandFile
    exit
}
Set-Location D:\app\ok-nikki
$env:PYTHONIOENCODING = 'utf-8'
& D:\app\ok-nikki\.venv\Scripts\python.exe scripts\run_daily.py *> D:\app\ok-nikki\daily_run.log
Write-Host "Done. Log: D:\app\ok-nikki\daily_run.log"
