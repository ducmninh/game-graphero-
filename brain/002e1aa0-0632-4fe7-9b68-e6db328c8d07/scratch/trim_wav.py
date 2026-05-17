import wave
import struct
import os

def trim_wav(in_path, out_path, threshold=500, max_duration_sec=1.5):
    with wave.open(in_path, 'rb') as w:
        params = w.getparams()
        n_channels, sampwidth, framerate, n_frames, comptype, compname = params
        frames = w.readframes(n_frames)
        
    # Assume 16-bit (sampwidth=2)
    if sampwidth != 2:
        print(f"Unsupported sample width {sampwidth} for {in_path}")
        return

    # Convert bytes to list of signed shorts
    fmt = f"<{len(frames)//2}h"
    samples = struct.unpack(fmt, frames)
    
    # Find start
    start_frame = 0
    for i in range(0, len(samples), n_channels):
        # check max amplitude in any channel
        amp = max(abs(samples[i + j]) for j in range(n_channels))
        if amp > threshold:
            start_frame = i // n_channels
            break
    
    # Trim to max duration
    end_frame = min(n_frames, start_frame + int(framerate * max_duration_sec))
    
    # Extract trimmed frames
    trimmed_frames = frames[start_frame * n_channels * sampwidth : end_frame * n_channels * sampwidth]
    
    with wave.open(out_path, 'wb') as w_out:
        w_out.setparams(params)
        w_out.setnframes(len(trimmed_frames) // (n_channels * sampwidth))
        w_out.writeframes(trimmed_frames)
    print(f"Trimmed {in_path} -> {out_path} (Start: {start_frame}, End: {end_frame})")

sounds_dir = r"c:\Users\LAPTOP\Downloads\grab_hero (1)\assets\sounds"
trim_wav(os.path.join(sounds_dir, "sniper.wav"), os.path.join(sounds_dir, "sniper_trim.wav"), threshold=1000, max_duration_sec=1.5)
trim_wav(os.path.join(sounds_dir, "pistol.wav"), os.path.join(sounds_dir, "pistol_trim.wav"), threshold=1000, max_duration_sec=0.5)
trim_wav(os.path.join(sounds_dir, "ak47.wav"), os.path.join(sounds_dir, "ak47_trim.wav"), threshold=1000, max_duration_sec=0.8)

# Overwrite originals
os.replace(os.path.join(sounds_dir, "sniper_trim.wav"), os.path.join(sounds_dir, "sniper.wav"))
os.replace(os.path.join(sounds_dir, "pistol_trim.wav"), os.path.join(sounds_dir, "pistol.wav"))
os.replace(os.path.join(sounds_dir, "ak47_trim.wav"), os.path.join(sounds_dir, "ak47.wav"))
