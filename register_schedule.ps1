# 定时任务注册: 每天 04:00 以最高权限自动跑一键日常(游戏需保持登录态在登录页或大世界)
# 用法: 右键"使用 PowerShell 运行"本脚本并在 UAC 中点"是"(注册计划任务需要管理员)
# 卸载: schtasks /Delete /TN "ok-nikki-daily" /F

$ErrorActionPreference = 'Stop'
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Start-Process pwsh -Verb RunAs -ArgumentList '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', $PSCommandPath
    exit
}

$taskName = "ok-nikki-daily"
$workDir = "D:\app\ok-nikki"
$python = "$workDir\.venv\Scripts\python.exe"
$script = "$workDir\scripts\run_daily.py"
$runLog = "$workDir\scheduled_run.log"

# 包装: 清残留 python(单实例锁) -> 跑任务(前台模式, 保证挖掘可用) -> 日志轮转(保留最近一份)
$action = New-ScheduledTaskAction -Execute "pwsh.exe" -Argument `
    "-NoProfile -Command `"Stop-Process -Name python -Force -ErrorAction SilentlyContinue; Start-Sleep 2; Set-Location '$workDir'; `$env:PYTHONIOENCODING='utf-8'; & '$python' '$script' --fg *> '$runLog'`""
$trigger = New-ScheduledTaskTrigger -Daily -At 04:00
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 15) -MultipleInstances IgnoreNew
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Highest

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger `
    -Settings $settings -Principal $principal -Force | Out-Null
Write-Host "Registered scheduled task '$taskName': daily 04:00, run as $env:USERNAME (highest), log: $runLog"
Write-Host "Test now: schtasks /Run /TN `"$taskName`""
