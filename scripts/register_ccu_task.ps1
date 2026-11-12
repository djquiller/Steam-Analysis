# Register (or remove) a Windows scheduled task that starts the CCU collector
# (python -m crawler.scheduler) automatically when the current user logs on.
#
# Usage (from any directory, normal non-admin PowerShell):
#   powershell -ExecutionPolicy Bypass -File scripts\register_ccu_task.ps1            # register + start now
#   powershell -ExecutionPolicy Bypass -File scripts\register_ccu_task.ps1 -Remove    # stop + unregister
#
# Notes:
#   - The task runs from the checkout this script lives in. After the branch is merged,
#     run it again from the main checkout to repoint the task.
#   - pythonw.exe is used so no console window stays open; logs go to data\logs\scheduler.log.
#   - The default 72-hour execution limit is disabled, and the task restarts itself
#     if the process dies. A second copy is never started while one is running.
#   - This file is ASCII-only on purpose: Windows PowerShell 5 misreads UTF-8 without BOM.
param(
    [switch]$Remove,
    [string]$TaskName = "SteamAnalysis CCU Scheduler",
    [string]$Python = "$env:USERPROFILE\anaconda3\pythonw.exe"
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot

if ($Remove) {
    Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Unregister-ScheduledTask -TaskName "$TaskName - Log Window" -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "Removed task '$TaskName'."
    exit 0
}

if (-not (Test-Path $Python)) { throw "pythonw.exe not found: $Python (pass -Python <path>)" }
if (-not (Test-Path (Join-Path $RepoRoot "crawler\scheduler.py"))) { throw "crawler\scheduler.py not found under $RepoRoot" }
if (-not (Test-Path (Join-Path $RepoRoot ".env"))) { throw ".env not found under $RepoRoot" }

$action = New-ScheduledTaskAction -Execute $Python -Argument "-m crawler.scheduler" -WorkingDirectory $RepoRoot
$trigger = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"
$settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 5) `
    -MultipleInstances IgnoreNew `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
    -Settings $settings -Principal $principal -Force `
    -Description "Hourly Steam concurrent-player snapshots (python -m crawler.scheduler)" | Out-Null
Start-ScheduledTask -TaskName $TaskName

# Second task: open a console window at logon that shows the collector's log live.
# It only reads the log; closing that window does not affect the collector.
# "cmd /c start" gives the viewer a console window of its own; running the .cmd directly
# as the task action exits at once without showing a window.
$viewCmd = Join-Path $PSScriptRoot "watch_ccu.cmd"
$viewAction = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c start `"CCU log`" `"$viewCmd`"" -WorkingDirectory $RepoRoot
$viewSettings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -MultipleInstances IgnoreNew -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName "$TaskName - Log Window" -Action $viewAction -Trigger $trigger `
    -Settings $viewSettings -Principal $principal -Force `
    -Description "Console window showing the CCU collector log (safe to close)" | Out-Null
Start-ScheduledTask -TaskName "$TaskName - Log Window"

Write-Host "Registered and started task '$TaskName'."
Write-Host "  working dir : $RepoRoot"
Write-Host "  log         : $RepoRoot\data\logs\scheduler.log"
Write-Host "  status      : Get-ScheduledTask -TaskName '$TaskName' | Get-ScheduledTaskInfo"
