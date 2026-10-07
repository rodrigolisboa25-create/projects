' Estoque Contabil: executa o clique da notificacao sem abrir janela de console.
Dim shell, folder, uri, activation
Set shell = CreateObject("WScript.Shell")
folder = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
uri = ""
activation = ""
If WScript.Arguments.Count > 0 Then uri = WScript.Arguments(0)
If WScript.Arguments.Count > 1 Then activation = WScript.Arguments(1)
uri = Replace(uri, """", "")
activation = Replace(activation, """", "")
shell.Run "powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -WindowStyle Hidden -File """ & folder & "\abrir_notificacao.ps1"" -Uri """ & uri & """ -ActivationFile """ & activation & """", 0, False
