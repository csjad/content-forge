# ContentForge 内容工厂 · Windows 定时任务安装脚本
# 用法（管理员或普通用户均可）：
#   powershell -ExecutionPolicy Bypass -File scripts\install_scheduler.ps1
# 效果：
#   1. ContentForge-Produce  每天 08:30 自动生产当日内容（选题→文案→视频→入队）
#   2. ContentForge-Publish  每 15 分钟检查并执行到期的发布队列
# 卸载：
#   schtasks /Delete /F /TN ContentForge-Produce
#   schtasks /Delete /F /TN ContentForge-Publish

$ErrorActionPreference = "Stop"
$py = (Get-Command python).Source
if (-not $py) { Write-Error "未找到 python，请先安装并加入 PATH"; exit 1 }
$script = "E:\Desktop\doubao\content-forge\main.py"

$produceCmd = "`"$py`" `"$script`" run --auto"
$publishCmd = "`"$py`" `"$script`" publish"

Write-Host "安装定时任务..."
schtasks /Create /F /TN "ContentForge-Produce" /SC DAILY /ST 08:30 /TR $produceCmd | Out-Null
schtasks /Create /F /TN "ContentForge-Publish" /SC MINUTE /MO 15 /TR $publishCmd | Out-Null

Write-Host "已安装："
schtasks /Query /TN "ContentForge-Produce" | Select-Object -First 4
schtasks /Query /TN "ContentForge-Publish" | Select-Object -First 4
Write-Host "提示：每日 08:30 自动生产，发布任务每 15 分钟检查队列。"
Write-Host "如需改生产时间：schtasks /Change /TN ContentForge-Produce /ST 07:00"
