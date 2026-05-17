import os
import shutil

amthanh_dir = r"c:\Users\LAPTOP\Downloads\grab_hero (1)\amthanh"
files = os.listdir(amthanh_dir)

mapping = {
    "Súng Bắn Tỉa": "src_sniper.mp3",
    "Súng Ngắn Bắn Liên Tục": "src_pistol.mp3",
    "súng AK 47": "src_ak47.mp3"
}

for f in files:
    for key, target in mapping.items():
        if key in f:
            src = os.path.join(amthanh_dir, f)
            dst = os.path.join(amthanh_dir, target)
            shutil.copy2(src, dst) # Use copy to be safe
