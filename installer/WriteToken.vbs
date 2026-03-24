Function WriteTokenToFile
  On Error Resume Next
  Set oSession = Session
  token = oSession.Property("TOKEN")
  installFolder = oSession.Property("INSTALLFOLDER")
  If token <> "" And installFolder <> "" Then
    Set fso = CreateObject("Scripting.FileSystemObject")
    If Right(installFolder, 1) <> "\" Then installFolder = installFolder & "\"
    path = installFolder & "token_pending.txt"
    Set file = fso.CreateTextFile(path, True)
    file.Write token
    file.Close
  End If
  WriteTokenToFile = 1
End Function
