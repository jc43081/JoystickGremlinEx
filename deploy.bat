@echo off
@echo "Starting to build Gremlin ..."
cd /d %0\..

set version=%1

@echo "Building executable ..."
python -m PyInstaller -y --clean joystick_gremlin.spec
cd dist
if exist joystick_gremlin.zip del joystick_gremlin.zip
cd joystick_gremlin

@echo "Create a Zip ..."
"C:\Program Files\7-Zip\7z" a -r ../joystick_gremlin.zip *
cd ..

@echo "Package into an installer..."
if "%version%" == "" (
    echo ERROR - Version must be provided to create installer
) else (
    python ../generate_wix.py --folder joystick_gremlin --version %version%
    wix build -src joystick_gremlin.wxs -ext WixToolset.UI.wixext
)

cd ..

