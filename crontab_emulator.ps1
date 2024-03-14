
# Ruta al archivo bat
$archivoBat = "C:\Users\lbisa\Mi unidad (leonardo.bisaro@gmail.com)\Cripto\python\trd_app\crontab.bat"

# Bucle infinito para ejecutar el archivo bat cada minuto
while ($true) {
    # Ejecutar el archivo bat
    Start-Process -FilePath $archivoBat -NoNewWindow
    
    # Esperar 1 minuto antes de la próxima ejecución
    Start-Sleep -Seconds 60
}