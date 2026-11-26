Option Explicit
Dim shell, fso, folder
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
folder = fso.GetParentFolderName(WScript.ScriptFullName)
' Installs only a desktop shortcut; does not download executables or change system settings.
Dim desktop, shortcut
desktop = shell.SpecialFolders("Desktop")
Set shortcut = shell.CreateShortcut(desktop & "\ArchiCord Overlay Studio.lnk")
shortcut.TargetPath = folder & "\START_OVERLAY_DESKTOP.bat"
shortcut.WorkingDirectory = folder
shortcut.Description = "ArchiCord local Overlay Studio"
shortcut.Save
MsgBox "ArchiCord Overlay Studio desktop shortcut created.", 64, "ArchiCord"
