' Immediate CA (runs as installing user): writes token to ProgramData — avoids Program Files ACL issues.
' If TOKEN property is empty, tries clipboard (works here; deferred post-install runs as SYSTEM and cannot read clipboard).

Function WriteTokenToFile
  On Error Resume Next
  Dim token, base, folder, fso, file, path, html
  token = Trim(Session.Property("TOKEN"))

  If Len(token) = 0 Then
    Err.Clear
    Set html = CreateObject("htmlfile")
    token = Trim(html.ParentWindow.ClipboardData.GetData("text"))
    Set html = Nothing
  End If

  If Len(token) = 0 Then
    WriteTokenToFile = 1
    Exit Function
  End If

  base = Session.Property("CommonAppDataFolder")
  If Len(base) = 0 Then base = "C:\ProgramData"

  Set fso = CreateObject("Scripting.FileSystemObject")
  folder = fso.BuildPath(base, "OTGuruAgent")
  If Not fso.FolderExists(folder) Then fso.CreateFolder folder
  path = fso.BuildPath(folder, "token_pending.txt")

  Set file = fso.CreateTextFile(path, True)
  file.Write token
  file.Close
  Set file = Nothing
  Set fso = Nothing

  WriteTokenToFile = 1
End Function
