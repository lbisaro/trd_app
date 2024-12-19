Write-Host "Iniciando Emulador de crontab - Periodo: 1 min"

# Obteniendo la ruta al script 
$scriptPath = $MyInvocation.MyCommand.Path
$scriptDirectory = [System.IO.Path]::GetDirectoryName($scriptPath)

# Ruta al archivo bat
$archivoBat = "$scriptDirectory\crontab.bat"

# Espera inicial para que el script inicie en el segundo 00 del proximo minuto
$segundo_actual = (Get-Date).Second
$segundos_restantes = 60 - $segundo_actual
Start-Sleep -Seconds $segundos_restantes
Write-Host "Inicia el bucle"

# Bucle infinito para ejecutar el archivo bat cada minuto
while ($true) {
    # Limpiar la pantalla
    Clear-Host

    # Ejecutar el archivo bat
    Start-Process -FilePath $archivoBat -NoNewWindow
    
    # Esperar 1 minuto antes de la próxima ejecución
    Start-Sleep -Seconds 60
}