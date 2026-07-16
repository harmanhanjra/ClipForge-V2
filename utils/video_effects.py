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
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, timeout=600)

def apply_copyright_filters(input_path, output_path, options):
    """
    Applies creative visual edits and replaces the source audio.
    Uses pure FFmpeg subprocess for reliability — no moviepy silent failures.

    Filters applied:
    - Aspect Ratio (vertical 9:16, horizontal 16:9, or original)
    - Horizontal mirror (hflip)
    - 5% center zoom-in (crop + scale)
    - Speed adjustment (setpts + atempo)
    - Generated original audio, user-supplied licensed audio, or mute
    """
    aspect       = options.get("aspect_ratio", "original")
    do_mirror    = options.get("mirror", True)
    do_zoom      = options.get("zoom", True)
    speed_factor = float(options.get("speed", 1.04))
    pitch_semi   = float(options.get("pitch_shift", 0.8))
    audio_mode   = options.get("audio_mode", "generated")
    replacement  = options.get("replacement_audio_path")

    # ── Check if the source has an audio stream ──────────────────────
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a:0",
         "-show_entries", "stream=codec_name",
         "-of", "default=noprint_wrappers=1:nokey=1", input_path],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30
    )
    has_audio = bool(probe.stdout.strip())

    # ── Build video filter chain ──────────────────────────────────────
    vf = []

    if aspect == "vertical":
        # Crop to 9:16 center, scale to 1080×1920
        vf.append("scale=1080:1920:force_original_aspect_ratio=decrease,"
                  "pad=1080:1920:-1:-1:color=black")
    elif aspect == "horizontal":
        vf.append("scale=1920:1080:force_original_aspect_ratio=decrease,"
                  "pad=1920:1080:-1:-1:color=black")

    if do_mirror:
        vf.append("hflip")

    if do_zoom:
        # Scale up 5%, then crop center back to original size
        vf.append("scale=iw*1.05:ih*1.05,crop=iw/1.05:ih/1.05")

    if speed_factor != 1.0:
        vf.append(f"setpts=PTS/{speed_factor:.4f}")

    # ── Build audio filter chain ──────────────────────────────────────
    af = []

    if has_audio:
        if speed_factor != 1.0:
            af.append(f"atempo={speed_factor:.4f}")

        if pitch_semi != 0.0:
            # asetrate shifts pitch; atempo corrects back to original speed
            multiplier = 2.0 ** (pitch_semi / 12.0)
            new_rate   = int(44100 * multiplier)
            tempo_corr = 1.0 / multiplier
            af.append(f"asetrate={new_rate},atempo={tempo_corr:.6f}")

    # ── Assemble FFmpeg command ───────────────────────────────────────
    cmd = ["ffmpeg", "-y", "-i", input_path]
    if audio_mode == "generated":
        # A locally synthesized ambient chord contains no sampled recording.
        sound = "aevalsrc=0.055*(sin(2*PI*220*t)+0.6*sin(2*PI*277.18*t)+0.4*sin(2*PI*329.63*t))*(0.7+0.3*sin(2*PI*0.25*t)):s=44100"
        cmd += ["-f", "lavfi", "-i", sound]
    elif audio_mode == "upload" and replacement:
        cmd += ["-stream_loop", "-1", "-i", replacement]

    if vf:
        cmd += ["-vf", ",".join(vf)]

    cmd += ["-c:v", "libx264", "-preset", "fast", "-movflags", "+faststart"]

    if audio_mode in {"generated", "upload"}:
        cmd += ["-map", "0:v:0", "-map", "1:a:0", "-c:a", "aac", "-shortest"]
    elif audio_mode == "mute":
        cmd += ["-an"]
    elif has_audio:
        if af:
            cmd += ["-af", ",".join(af)]
        cmd += ["-c:a", "aac"]
    else:
        cmd += ["-an"]   # no audio stream in source — don't try to encode one

    cmd.append(output_path)

    # ── Run ───────────────────────────────────────────────────────────
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=900)

    if result.returncode != 0 or not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
        err = result.stderr.decode("utf-8", errors="ignore")[-600:]
        raise RuntimeError(f"FFmpeg filter failed for {os.path.basename(input_path)}: {err}")


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
        seg_duration = max(0.0, end - start)
        if seg_duration <= 0:
            continue
        # Accurate cut: fast pre-input seek + re-encode so the segment starts
        # exactly at `start` and lasts exactly `seg_duration`. `-c copy` would
        # snap to keyframes and drift, breaking custom timestamp ranges.
        cmd = [
            "ffmpeg", "-y", "-ss", f"{start:.3f}", "-i", input_path,
            "-t", f"{seg_duration:.3f}",
            "-c:v", "libx264", "-preset", "veryfast", "-c:a", "aac",
            "-movflags", "+faststart", out_path
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=600)
        if result.returncode != 0:
            err = result.stderr.decode("utf-8", errors="ignore")[-500:]
            raise RuntimeError(f"FFmpeg clip slicing failed: {err}")
        if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
            output_files.append(out_path)

    return output_files
