# ROMO CAMBIOS - selector de archivos de Windows.
# Imprime una ruta por linea; si el usuario cancela no imprime nada.
# Lo llama plataforma.py (es el equivalente del `osascript` de la Mac).
param([string]$Modo = "files")

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Add-Type -AssemblyName System.Windows.Forms | Out-Null

# Ventana invisible que hace de dueña del dialogo: sin esto el selector puede
# abrirse DETRAS del navegador y parece que la app se colgo.
$duena = New-Object System.Windows.Forms.Form
$duena.TopMost = $true
$duena.ShowInTaskbar = $false
$duena.Opacity = 0
$duena.Show()

try {
  if ($Modo -eq "folder") {
    $d = New-Object System.Windows.Forms.FolderBrowserDialog
    $d.Description = "Elige la carpeta"
    $d.ShowNewFolderButton = $true
    if ($d.ShowDialog($duena) -eq [System.Windows.Forms.DialogResult]::OK) {
      [Console]::Out.WriteLine($d.SelectedPath)
    }
  }
  else {
    $d = New-Object System.Windows.Forms.OpenFileDialog
    $d.Title = "Elige los videos de los cambios"
    $d.Multiselect = $true
    $d.Filter = "Videos (*.mp4;*.mov;*.m4v;*.avi;*.mkv)|*.mp4;*.mov;*.m4v;*.avi;*.mkv|Todos los archivos|*.*"
    if ($d.ShowDialog($duena) -eq [System.Windows.Forms.DialogResult]::OK) {
      foreach ($f in $d.FileNames) { [Console]::Out.WriteLine($f) }
    }
  }
}
finally {
  $duena.Close()
}
