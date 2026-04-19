' Immediate CA (runs as installing user): writes token to ProgramData — avoids Program Files ACL issues.
' If TOKEN property is empty, reads clipboard (htmlfile first; PowerShell -STA fallback — htmlfile often fails in MSI).

Function GetClipboardText
  On Error Resume Next
  Dim html, t, sh, exec, waited
  t = ""

  Err.Clear
  Set html = CreateObject("htmlfile")
  If Not html Is Nothing Then
    t = Trim(html.ParentWindow.ClipboardData.GetData("text"))
    If Len(t) = 0 Then t = Trim(html.ParentWindow.ClipboardData.GetData("Text"))
  End If
  Set html = Nothing

  If Len(t) = 0 Then
    Err.Clear
    Set sh = CreateObject("WScript.Shell")
    If Not sh Is Nothing Then
      Set exec = sh.Exec("powershell.exe -NoProfile -ExecutionPolicy Bypass -STA -WindowStyle Hidden -Command ""(Get-Clipboard -Raw).Trim()""")
      waited = 0
      Do While exec.Status = 0 And waited < 100
        WScript.Sleep 50
        waited = waited + 1
      Loop
      If exec.ExitCode = 0 Then
        t = Trim(exec.StdOut.ReadAll())
      End If
      Set exec = Nothing
    End If
    Set sh = Nothing
  End If

  GetClipboardText = t
End Function

Function WriteTokenToFile
  On Error Resume Next
  Dim token, base, folder, fso, file, path
  token = Trim(Session.Property("TOKEN"))

  If Len(token) = 0 Then
    token = GetClipboardText()
  End If

  If Len(token) = 0 Then
    WriteTokenToFile = 1
    Exit Function
  End If

  base = Session.Property("CommonAppDataFolder")
  If Len(base) = 0 Then base = "C:\ProgramData"

  Set fso = CreateObject("Scripting.FileSystemObject")
  folder = fso.BuildPath(base, "ctrldesk")
  If Not fso.FolderExists(folder) Then fso.CreateFolder folder
  path = fso.BuildPath(folder, "token_pending.txt")

  Set file = fso.CreateTextFile(path, True)
  file.Write token
  file.Close
  Set file = Nothing
  Set fso = Nothing

  ' MSI script CAs: 0 = success, non-zero = failure
  WriteTokenToFile = 0
End Function
