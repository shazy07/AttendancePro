$WshShell = New-Object -ComObject WScript.Shell
$DesktopPath = [System.IO.Path]::Combine($env:USERPROFILE, "Desktop")
$Shortcut = $WshShell.CreateShortcut("$DesktopPath\AttendPro.lnk")
$Shortcut.TargetPath = "$PSScriptRoot\run.bat"
$Shortcut.WorkingDirectory = "$PSScriptRoot"
$Shortcut.WindowStyle = 1
$Shortcut.Description = "Launch AttendPro Attendance System"
$Shortcut.Save()
Write-Host "Desktop shortcut created successfully!" -ForegroundColor Green
