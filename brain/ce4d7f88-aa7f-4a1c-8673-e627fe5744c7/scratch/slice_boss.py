
from PIL import Image
import os

# Create directory if not exists
out_dir = r"c:\Users\LAPTOP\Downloads\grab_hero (1)\assets\sprites"
if not os.path.exists(out_dir):
    os.makedirs(out_dir)

img = Image.open(r"c:\Users\LAPTOP\Downloads\grab_hero (1)\nhanvat\Gemini_Generated_Image_mtipfgmtipfgmtip.png")
w, h = img.size

# Based on 2816x1536 and 5 rows, 7 columns
# There are labels like "WALK UP" which are roughly 60-80px high
rows = 5
cols = 7
cell_w = w // cols
cell_h = h // rows

# Row labels:
# 1: WALK UP
# 2: WALK DOWN
# 3: WALK LEFT
# 4: WALK RIGHT
# 5: SLASH EFFECT


all_prefixes = ["boss1", "boss2", "boss3", "boss7"]
actions = ["up", "down", "left", "right", "attack"]

for pref in all_prefixes:
    for r in range(rows):
        act = actions[r]
        for c in range(cols):
            left = c * cell_w
            top = r * cell_h + 80
            right = (c + 1) * cell_w
            bottom = (r + 1) * cell_h
            
            tile = img.crop((left, top, right, bottom))
            tile = tile.convert("RGBA")
            datas = tile.getdata()
            
            newData = []
            for item in datas:
                if item[0] < 45 and item[1] < 40 and item[2] < 55:
                    newData.append((255, 255, 255, 0))
                else:
                    newData.append(item)
            tile.putdata(newData)
            tile.save(os.path.join(out_dir, f"{pref}_{act}_{c}.png"))

print("Done slicing sprites!")
