import os
import subprocess
from moviepy.editor import VideoFileClip, concatenate_videoclips, vfx

def crop_to_aspect_ratio(clip, target_w, target_h):
    """
    Crops a video clip from its center to match the target aspect ratio,
    then resizes it to the target dimensions.
    """
    w, h = clip.size
    target_aspect = target_w / target_h
    current_aspect = w / h
    
    if current_aspect > target_aspect:
        # Video is wider than target. Crop left/right.
        new_w = int(h * target_aspect)
        x1 = (w - new_w) // 2
        x2 = x1 + new_w
        clip_cropped = clip.crop(x1=x1, y1=0, x2=x2, y2=h)
    else:
        # Video is taller than target. Crop top/bottom.
        new_h = int(w / target_aspect)
        y1 = (h - new_h) // 2
        y2 = y1 + new_h
        clip_cropped = clip.crop(x1=0, y1=y1, x2=w, y2=y2)
        
    return clip_cropped.resize(newsize=(target_w, target_h))

def concatenate_clips(video_paths, aspect_ratio="vertical", output_path=None):
    """
    Concatenates multiple video files of varying sizes and lengths,
    resizing them to match the target aspect ratio (vertical: 1080x1920, horizontal: 1920x1080).
    """
    if not video_paths:
        raise ValueError("No video paths provided to concatenate.")
        
    target_w, target_h = (1080, 1920) if aspect_ratio == "vertical" else (1920, 1080)
    
    clips = []
    for path in video_paths:
        if os.path.exists(path):
            clip = VideoFileClip(path)
            # Standardize resolution/aspect ratio
            processed_clip = crop_to_aspect_ratio(clip, target_w, target_h)
            clips.append(processed_clip)
            
    if not clips:
        raise ValueError("None of the provided video paths exist or could be loaded.")
        
    final_clip = concatenate_videoclips(clips, method="compose")
    
    # Save target duration
    duration = final_clip.duration
    
    if output_path:
        # Write temporarily, we will mix with audio later
        final_clip.write_videofile(
            output_path, 
            codec="libx264", 
            audio_codec="aac", 
            fps=30, 
            logger=None
        )
        
    # Keep track of duration and close clips
    for clip in clips:
        clip.close()
        
    final_clip.close()
    return duration

def pitch_shift_audio(input_audio_path, output_audio_path, semitones=0.8):
    """
    Pitch shifts an audio file using FFmpeg's asetrate and atempo filters.
    semitones: shift amount (positive = higher, negative = lower).
    """
    multiplier = 2.0 ** (semitones / 12.0)
    sample_rate = 44100
    new_rate = int(sample_rate * multiplier)
    tempo = 1.0 / multiplier
    
    cmd = [
        "ffmpeg", "-y", "-i", input_audio_path,
        "-filter_complex", f"asetrate={new_rate},atempo={tempo}",
        output_audio_path
    ]
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)

def apply_copyright_filters(input_path, output_path, options):
    """
    Applies visual and audio transformations to bypass copyright filters:
    - Aspect Ratio adjustment (original, vertical 9:16, horizontal 16:9)
    - Mirroring (horizontal flip)
    - Slight cropping/zooming (e.g. 1.05x)
    - Slight speed alteration
    - Slight pitch shifting of original audio (if preserved)
    """
    clip = VideoFileClip(input_path)
    
    # 0. Handle Aspect Ratio Conversion
    aspect = options.get("aspect_ratio", "original")
    if aspect == "vertical":
        clip = crop_to_aspect_ratio(clip, 1080, 1920)
    elif aspect == "horizontal":
        clip = crop_to_aspect_ratio(clip, 1920, 1080)
        
    w, h = clip.size
    
    # 1. Visual Mirroring
    if options.get("mirror", True):
        clip = clip.fx(vfx.mirror_x)
        
    # 2. Slight Zoom / Crop (to dodge visual signature detection)
    if options.get("zoom", True):
        zoom_factor = 1.05
        new_w, new_h = int(w / zoom_factor), int(h / zoom_factor)
        x1, y1 = (w - new_w) // 2, (h - new_h) // 2
        x2, y2 = x1 + new_w, y1 + new_h
        clip = clip.crop(x1=x1, y1=y1, x2=x2, y2=y2)
        clip = clip.resize(newsize=(w, h))
        
    # 3. Slight Speed Alteration (e.g., 1.04x speedup)
    speed_factor = float(options.get("speed", 1.04))
    if speed_factor != 1.0:
        clip = clip.fx(vfx.speedx, speed_factor)
        
    # Write to a temporary file
    temp_video = output_path + ".temp.mp4"
    clip.write_videofile(
        temp_video,
        codec="libx264",
        audio_codec="aac",
        fps=30,
        logger=None
    )
    clip.close()
    
    # 4. Audio Pitch Shifting (if we want to preserve and pitch-shift the audio)
    pitch_semitones = float(options.get("pitch_shift", 0.8))
    if pitch_semitones != 0.0 and os.path.exists(temp_video):
        # Extract audio from temp video
        temp_audio = output_path + ".temp.wav"
        temp_shifted_audio = output_path + ".shifted.wav"
        
        # Extract command
        extract_cmd = ["ffmpeg", "-y", "-i", temp_video, "-vn", "-acodec", "pcm_s16le", temp_audio]
        subprocess.run(extract_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        if os.path.exists(temp_audio) and os.path.getsize(temp_audio) > 0:
            try:
                # Apply pitch shift
                pitch_shift_audio(temp_audio, temp_shifted_audio, pitch_semitones)
                
                # Combine shifted audio back to the temp video
                combine_cmd = [
                    "ffmpeg", "-y", "-i", temp_video, "-i", temp_shifted_audio,
                    "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", output_path
                ]
                subprocess.run(combine_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            except Exception as e:
                print(f"Error shifting audio pitch: {e}. Falling back to normal audio.")
                if os.path.exists(output_path):
                    os.remove(output_path)
                os.rename(temp_video, output_path)
            finally:
                # Cleanup temp audio files
                for f in [temp_audio, temp_shifted_audio]:
                    if os.path.exists(f):
                        os.remove(f)
        else:
            # Video might have no audio
            os.rename(temp_video, output_path)
    else:
        os.rename(temp_video, output_path)
        
    # Cleanup temp video
    if os.path.exists(temp_video):
        os.remove(temp_video)

def slice_video(input_path, output_dir, mode="auto", intervals=8, custom_ranges=None):
    """
    Slices a video into multiple segments.
    mode: "auto" (split every N seconds) or "timestamps" (split by custom list of ranges).
    intervals: number of seconds per slice in auto mode.
    custom_ranges: list of tuples/lists e.g. [[10, 20], [35, 45]] (in seconds).
    Returns a list of created file paths.
    """
    clip = VideoFileClip(input_path)
    duration = clip.duration
    clip.close()
    
    slices = []
    if mode == "auto":
        start = 0
        idx = 1
        while start < duration:
            end = min(start + intervals, duration)
            # Avoid tiny trailing clips less than 1 second
            if duration - end < 1.0:
                end = duration
            slices.append((start, end, f"clip_{idx}.mp4"))
            idx += 1
            if end == duration:
                break
            start = end
    elif mode == "timestamps" and custom_ranges:
        for idx, r in enumerate(custom_ranges, 1):
            start = r[0]
            end = min(r[1], duration)
            if start < duration:
                slices.append((start, end, f"clip_{idx}.mp4"))
                
    output_files = []
    for start, end, filename in slices:
        out_path = os.path.join(output_dir, filename)
        # Use FFmpeg directly for fast lossless seeking and cutting
        cmd = [
            "ffmpeg", "-y", "-ss", str(start), "-to", str(end),
            "-i", input_path, "-c", "copy", out_path
        ]
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
            output_files.append(out_path)
            
    return output_files
