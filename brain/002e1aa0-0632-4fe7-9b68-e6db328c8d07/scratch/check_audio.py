import pygame
import os

pygame.mixer.init()

amthanh_dir = r"c:\Users\LAPTOP\Downloads\grab_hero (1)\amthanh"
files = [
    "(6) Âm Thanh Súng Bắn Tỉa - YouTube.mp3",
    "(6) Âm Thanh Súng Ngắn Bắn Liên Tục - YouTube.mp3",
    "(6) tiếng súng AK 47 - YouTube.mp3"
]

for f in files:
    path = os.path.join(amthanh_dir, f)
    try:
        sound = pygame.mixer.Sound(path)
        print(f"{f}: {sound.get_length():.2f} seconds")
    except Exception as e:
        print(f"Error loading {f}: {e}")
