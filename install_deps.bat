@echo off
REM Script d'installation des dépendances avec GDAL de QGIS

echo Configuration de l'environnement GDAL...

set OSGEO4W_ROOT=C:\Program Files\QGIS 3.40.13
set GDAL_DATA=%OSGEO4W_ROOT%\share\gdal
set PROJ_LIB=%OSGEO4W_ROOT%\share\proj
set PATH=%OSGEO4W_ROOT%\bin;%OSGEO4W_ROOT%\apps\qgis\bin;%PATH%
set GDAL_VERSION=3.10

echo OSGEO4W_ROOT=%OSGEO4W_ROOT%
echo GDAL_VERSION=%GDAL_VERSION%

echo.
echo Installation des dependances...
call .venv\Scripts\activate
pip install -r requirements.txt

echo.
echo Installation terminee!
pause
