Option Explicit

Dim gridId, outputFolder, outputName, expectedConnection, timeoutSeconds
Dim application, connection, session, grid, button, radio, combo, entry
Dim pathControl, fileControl, saveButton, i, deadline

If WScript.Arguments.Count <> 5 Then
    WScript.Echo "Uso: sap_export.vbs GRID_ID PASTA ARQUIVO CONEXAO TIMEOUT"
    WScript.Quit 2
End If

gridId = WScript.Arguments(0)
outputFolder = WScript.Arguments(1)
outputName = WScript.Arguments(2)
expectedConnection = LCase(Trim(WScript.Arguments(3)))
timeoutSeconds = CInt(WScript.Arguments(4))
deadline = DateAdd("s", 5, Now)

On Error Resume Next
Set application = GetObject("SAPGUI").GetScriptingEngine
If Err.Number <> 0 Then
    WScript.Echo "SAP GUI Scripting nao ficou disponivel: " & Err.Description
    WScript.Quit 3
End If
On Error GoTo 0

Set session = Nothing
Do While session Is Nothing And Now < deadline
    For i = 0 To application.Children.Count - 1
        Set connection = application.Children.ElementAt(CLng(i))
        If expectedConnection = "" Or InStr(1, LCase(connection.Description), expectedConnection, 1) > 0 Then
            If connection.Children.Count > 0 Then
                Set session = connection.Children.ElementAt(0)
                Exit For
            End If
        End If
    Next
    If session Is Nothing Then WScript.Sleep 250
Loop

If session Is Nothing Then
    WScript.Echo "A sessao SAP selecionada nao foi localizada."
    WScript.Quit 4
End If

Set grid = WaitControl(session, gridId, deadline)
If grid Is Nothing Then
    WScript.Echo "A grade de resultado do SAP nao foi localizada: " & gridId
    WScript.Quit 5
End If

grid.ContextMenu
grid.SelectContextMenuItem "&XXL"

Set button = WaitControl(session, "wnd[1]/tbar[0]/btn[0]", deadline)
If button Is Nothing Then
    WScript.Echo "O seletor de formato da planilha nao foi exibido."
    WScript.Quit 6
End If

' Newer SAP GUI versions expose these stable identifiers.
Set radio = TryControl(session, "wnd[1]/usr/radRB_OTHERS")
If Not radio Is Nothing Then radio.Select

Set combo = TryControl(session, "wnd[1]/usr/cmbG_LISTBOX")
If Not combo Is Nothing Then
    For i = 0 To combo.Entries.Count - 1
        Set entry = combo.Entries.ElementAt(CLng(i))
        If InStr(1, LCase(CStr(entry.Value)), "xlsx", 1) > 0 Or _
           InStr(1, LCase(CStr(entry.Value)), "open formato xml", 1) > 0 Or _
           InStr(1, LCase(CStr(entry.Value)), "open xml", 1) > 0 Then
            combo.Key = entry.Key
            Exit For
        End If
    Next
End If

' Green confirmation icon shown in "Selecionar planilha eletronica".
button.Press

Set pathControl = WaitControl(session, "wnd[1]/usr/ctxtDY_PATH", deadline)
Set fileControl = TryControl(session, "wnd[1]/usr/ctxtDY_FILENAME")
If Not pathControl Is Nothing And Not fileControl Is Nothing Then
    pathControl.Text = outputFolder
    fileControl.Text = outputName
    Set saveButton = TryControl(session, "wnd[1]/tbar[0]/btn[0]")
    If saveButton Is Nothing Then Set saveButton = TryControl(session, "wnd[1]/tbar[0]/btn[11]")
    If saveButton Is Nothing Then
        WScript.Echo "O botao Salvar do SAP nao foi localizado."
        WScript.Quit 7
    End If
    saveButton.Press
Else
    ' Compatibility with the two-confirmation route recorded in the original VBS.
    Set saveButton = WaitControl(session, "wnd[1]/tbar[0]/btn[0]", deadline)
    If Not saveButton Is Nothing Then saveButton.Press
End If

' Confirm overwrite only when SAP presents one more modal after saving.
WScript.Sleep 50
Set pathControl = TryControl(session, "wnd[1]/usr/ctxtDY_PATH")
If pathControl Is Nothing Then
    Set button = TryControl(session, "wnd[1]/tbar[0]/btn[0]")
    If Not button Is Nothing Then button.Press
End If

WScript.Quit 0

Function TryControl(currentSession, controlId)
    Dim control
    Set control = Nothing
    On Error Resume Next
    Set control = currentSession.FindById(controlId)
    Err.Clear
    On Error GoTo 0
    Set TryControl = control
End Function

Function WaitControl(currentSession, controlId, limit)
    Dim control
    Set control = Nothing
    Do While control Is Nothing And Now < limit
        Set control = TryControl(currentSession, controlId)
        If control Is Nothing Then WScript.Sleep 50
    Loop
    Set WaitControl = control
End Function
