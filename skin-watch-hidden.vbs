' WorkBuddy skin keeper - hidden launcher (no console window)
' Optional arg: theme id, e.g. wscript.exe skin-watch-hidden.vbs gojo-inverse
' Override the interpreter with the WBSKIN_PYTHON environment variable.
Dim sh, fso, py, keeper, cmd
Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

py = sh.ExpandEnvironmentStrings("%WBSKIN_PYTHON%")
If py = "" Or py = "%WBSKIN_PYTHON%" Then
  py = sh.ExpandEnvironmentStrings("%USERPROFILE%") & _
       "\.workbuddy\binaries\python\versions\3.13.12\pythonw.exe"
  If Not fso.FileExists(py) Then py = "pythonw.exe"
End If

keeper = fso.BuildPath(fso.GetParentFolderName(WScript.ScriptFullName), "skin-watch.py")
cmd = """" & py & """ """ & keeper & """"
If WScript.Arguments.Count > 0 Then cmd = cmd & " " & WScript.Arguments(0)
sh.Run cmd, 0, False
