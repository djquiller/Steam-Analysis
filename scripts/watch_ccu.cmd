@echo off
rem Live view of the CCU collector log. Double-click to open.
rem Closing this window does NOT stop the collector (it runs hidden as a scheduled task).
chcp 65001 >nul
title Steam CCU collector - live log (safe to close)
powershell -NoProfile -ExecutionPolicy Bypass -Command "[Console]::OutputEncoding=[Text.Encoding]::UTF8; Get-Content -LiteralPath '%~dp0..\data\logs\scheduler.log' -Wait -Tail 30 -Encoding UTF8"
