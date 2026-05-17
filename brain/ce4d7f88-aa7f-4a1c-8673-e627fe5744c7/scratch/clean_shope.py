
import os
from PIL import Image

def remove_bg(input_path, output_path):
    if not os.path.exists(input_path):
        print(f"File {input_path} not found.")
        return
    img = Image.open(input_path).convert("RGBA")
    datas = img.getdata()
    
    newData = []
    for item in datas:
        # Just ensure white is gone
        if item[0] > 250 and item[1] > 250 and item[2] > 250:
            newData.append((255, 255, 255, 0))
        else:
            newData.append(item)
    img.putdata(newData)
    img.save(output_path)
    print(f"Saved {output_path}")

# Source dir
src = r"c:\Users\LAPTOP\Downloads\grab_hero (1)\nhanvat\shope"
# Dest dir
dest = r"c:\Users\LAPTOP\Downloads\grab_hero (1)\assets\sprites"

# Mapping based on new names
remove_bg(os.path.join(src, "shopee_driver_standing-removebg-preview.png"), os.path.join(dest, "shope.png"))
remove_bg(os.path.join(src, "shopee_driver_firing-removebg-preview.png"), os.path.join(dest, "shope_holds_ar.png"))
remove_bg(os.path.join(src, "shopee_firing_smg-removebg-preview.png"), os.path.join(dest, "shope_holds_smg.png"))
remove_bg(os.path.join(src, "shopee_firing_shotgun-removebg-preview.png"), os.path.join(dest, "shope_holds_shotgun.png"))
# Also for pistol/sniper fallback
remove_bg(os.path.join(src, "shopee_driver_firing-removebg-preview.png"), os.path.join(dest, "shope_holds_pistol.png"))
remove_bg(os.path.join(src, "shopee_driver_firing-removebg-preview.png"), os.path.join(dest, "shope_holds_sniper.png"))
