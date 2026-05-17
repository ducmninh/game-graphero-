@echo off
echo GRAB HERO - DONG GOI UNG DUNG
echo -----------------------------
echo Dang kiem tra PyInstaller...
pyinstaller --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [LOI] Khong tim thay PyInstaller. Dang cai dat...
    pip install pyinstaller
)

echo Dang bat dau dong goi...
pyinstaller --noconsole --onefile ^
    --name "GrabHero" ^
    --add-data "assets;assets" ^
    --add-data "nhanvat;nhanvat" ^
    --add-data "amthanh;amthanh" ^
    --add-data "bando;bando" ^
    --paths "grab_hero/tong" ^
    "grab_hero/tong/main.py"

echo -----------------------------
if %errorlevel% eq 0 (
    echo [THANH CONG] File GrabHero.exe da duoc tao trong thu muc 'dist'.
    echo Ban hay gui file trong 'dist' cho ban be test nhe!
) else (
    echo [LOI] Co loi xay ra trong qua trinh dong goi.
)
pause
