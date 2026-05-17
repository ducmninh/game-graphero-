import wave
import numpy as np

def find_peak(filename):
    with wave.open(filename, 'rb') as w:
        params = w.getparams()
        frames = w.readframes(params.nframes)
        samples = np.frombuffer(frames, dtype=np.int16)
        if params.nchannels == 2:
            samples = samples[::2] # Left channel
        
        # Absolute values to find peaks
        abs_samples = np.abs(samples)
        
        # Find index of max
        peak_idx = np.argmax(abs_samples)
        peak_time = peak_idx / params.framerate
        print(f"Peak at {peak_time:.3f}s")
        return peak_time

if __name__ == "__main__":
    # Convert original to wav first to analyze
    import subprocess
    input_mp3 = r"amthanh\(6) Âm Thanh Súng Bắn Tỉa - YouTube.mp3"
    temp_wav = "temp_sniper.wav"
    subprocess.run(["ffmpeg", "-i", input_mp3, temp_wav, "-y"], capture_output=True)
    find_peak(temp_wav)
