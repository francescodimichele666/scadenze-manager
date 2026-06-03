' Avvia ScadenzeManager in background (senza finestra nera)
' Doppio clic su questo file per lanciare l'app

Dim WshShell, oExec, appDir

appDir = Left(WScript.ScriptFullName, InStrRev(WScript.ScriptFullName, "\"))

Set WshShell = CreateObject("WScript.Shell")

' Controlla se l'app e' gia' in esecuzione
Dim objNet : Set objNet = CreateObject("WScript.Network")
On Error Resume Next
Dim http : Set http = CreateObject("MSXML2.XMLHTTP")
http.Open "GET", "http://127.0.0.1:5000", False
http.Send
If Err.Number = 0 And http.Status = 200 Then
    ' Gia' in esecuzione, apre solo il browser
    WshShell.Run "http://127.0.0.1:5000", 1, False
    WScript.Quit
End If
On Error GoTo 0

' Avvia Python in background (nessuna finestra)
WshShell.Run "cmd /c cd /d """ & appDir & """ && python app.py", 0, False

' Aspetta che il server parta
WScript.Sleep 3000

' Apre il browser
WshShell.Run "http://127.0.0.1:5000", 1, False

Set WshShell = Nothing
