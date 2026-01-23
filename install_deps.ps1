# Script d'installation des dépendances avec GDAL de QGIS
Write-Host "Configuration de l'environnement GDAL..." -ForegroundColor Cyan

$env:OSGEO4W_ROOT = "C:\Program Files\QGIS 3.40.13"
$env:GDAL_DATA = "C:\Program Files\QGIS 3.40.13\share\gdal"
$env:PROJ_LIB = "C:\Program Files\QGIS 3.40.13\share\proj"
$env:GDAL_VERSION = "3.10"
$env:PATH = "C:\Program Files\QGIS 3.40.13\bin;C:\Program Files\QGIS 3.40.13\apps\qgis\bin;" + $env:PATH

Write-Host "OSGEO4W_ROOT: $env:OSGEO4W_ROOT"
Write-Host "GDAL_VERSION: $env:GDAL_VERSION"
Write-Host ""
Write-Host "Installation des dependances..." -ForegroundColor Yellow

Set-Location "D:\greensig_full\backend"
& ".\\.venv\\Scripts\\pip.exe" install -r requirements.txt

Write-Host ""
Write-Host "Installation terminee!" -ForegroundColor Green
