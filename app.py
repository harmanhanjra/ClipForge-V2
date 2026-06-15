import os
import uuid
import subprocess
import PIL.Image

# Monkeypatch PIL.Image.ANTIALIAS for compatibility with moviepy and newer Pillow versions
if not hasattr(PIL.Image, 'ANTIALIAS'):
    PIL.Image.ANTIALIAS = PIL.Image.Resampling.LANCZOS

from flask import Flask, request, jsonify, send_from_directory, render_template

from utils.audio_engine import (
    generate_speech, create_mixed_audio, generate_preview,
    generate_ai_video,
    VOICES, VOICE_STYLES, MOOD_LABELS, AGE_PRESETS
)
from utils.video_effects import concatenate_clips, apply_copyright_filters, slice_video

app = Flask(__name__, static_folder='static', static_url_path='')

# Configuration
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
OUTPUT_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'outputs')

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# ── Clean up any leftover temp/partial files on startup ──
for _f in os.listdir(OUTPUT_FOLDER):
    if '.temp' in _f or 'TEMP_MPY' in _f or _f.endswith('.part'):
        try:
            os.remove(os.path.join(OUTPUT_FOLDER, _f))
            print(f'[cleanup] Removed temp file: {_f}')
        except Exception:
            pass

# Helper to execute shell commands (e.g. yt-dlp using local venv)
def get_pip_binary(binary_name):
    # Returns path to binary in virtual env
    venv_bin = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'venv', 'bin', binary_name)
    if os.path.exists(venv_bin):
        return venv_bin
    return binary_name

@app.route('/')
def index():
    return send_from_directory('static', 'index.html')

@app.route('/api/voices', methods=['GET'])
def get_voices():
    """Returns voices + style + age metadata."""
    return jsonify({
        'voices':       VOICES,
        'voice_styles': VOICE_STYLES,
        'mood_labels':  MOOD_LABELS,
        'age_presets':  AGE_PRESETS,
    })


@app.route('/api/preview-voice', methods=['POST'])
def preview_voice():
    """
    Generate a short voice preview sample and stream it back as audio/mpeg.
    Body: { voice, lang, style, style_degree, rate, pitch }
    """
    import tempfile
    from flask import send_file

    voice        = request.form.get('voice', 'en-US-EmmaMultilingualNeural')
    lang         = request.form.get('lang', 'en-US')
    style        = request.form.get('style', '')
    style_degree = float(request.form.get('style_degree', 1.0))
    rate         = request.form.get('rate', '+0%')
    pitch        = request.form.get('pitch', '+0Hz')

    # Write to a temp file
    tmp = tempfile.NamedTemporaryFile(suffix='.mp3', delete=False, dir=UPLOAD_FOLDER)
    tmp.close()
    out_path = tmp.name

    ok = generate_preview(voice=voice, lang_prefix=lang,
                          style=style, style_degree=style_degree,
                          rate=rate, pitch=pitch,
                          output_path=out_path)
    if not ok or not os.path.exists(out_path):
        return jsonify({'error': 'Preview generation failed'}), 500

    return send_file(out_path, mimetype='audio/mpeg',
                     as_attachment=False,
                     download_name='preview.mp3')


@app.route('/api/clear-library', methods=['POST'])
def clear_library():
    """Delete all exported files from the outputs folder."""
    deleted, failed = [], []
    for f in os.listdir(OUTPUT_FOLDER):
        if f.endswith('.mp4') or f.endswith('.mp3'):
            try:
                os.remove(os.path.join(OUTPUT_FOLDER, f))
                deleted.append(f)
            except Exception as ex:
                failed.append({'file': f, 'error': str(ex)})
    return jsonify({'deleted': len(deleted), 'failed': failed})

@app.route('/api/merge', methods=['POST'])
def merge_videos():
    """
    Merge uploaded video clips and overlay generated/uploaded audio.
    Supports style, rate, pitch, style_degree for TTS voices.
    """
    try:
        aspect_ratio  = request.form.get('aspect_ratio', 'vertical')
        audio_source  = request.form.get('audio_source', 'script')
        language      = request.form.get('language', 'ur-PK')
        voice_id      = request.form.get('voice', 'ur-PK-UzmaNeural')
        script_text   = request.form.get('script_text', '')
        trim_audio    = request.form.get('trim_audio', 'true') == 'true'
        # Voice style / mood params
        voice_style        = request.form.get('style', '')
        voice_style_degree = float(request.form.get('style_degree', 1.0))
        voice_rate         = request.form.get('rate', '+0%')
        voice_pitch        = request.form.get('pitch', '+0Hz')
        
        # Handle video uploads
        uploaded_videos = request.files.getlist('videos')
        if not uploaded_videos or len(uploaded_videos) == 0 or uploaded_videos[0].filename == '':
            return jsonify({'success': False, 'error': 'No video files uploaded.'}), 400
            
        video_paths = []
        job_id = str(uuid.uuid4())
        
        # Save video uploads
        for idx, file in enumerate(uploaded_videos):
            filename = f"{job_id}_video_{idx}.mp4"
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            file.save(filepath)
            video_paths.append(filepath)
            
        # 1. Merge videos together
        merged_temp_video = os.path.join(UPLOAD_FOLDER, f"{job_id}_merged_raw.mp4")
        duration = concatenate_clips(video_paths, aspect_ratio=aspect_ratio, output_path=merged_temp_video)
        
        # 2. Process / Generate audio
        final_audio_path = None
        speech_path = None
        bg_music_path = None
        
        if audio_source == 'script' and script_text.strip():
            # Generate speech audio
            speech_path = os.path.join(UPLOAD_FOLDER, f"{job_id}_speech.mp3")
            generate_speech(script_text, voice_id, speech_path,
                            rate=voice_rate, pitch=voice_pitch,
                            style=voice_style, style_degree=voice_style_degree)
            
        elif audio_source == 'upload':
            uploaded_audio = request.files.get('audio_file')
            if uploaded_audio and uploaded_audio.filename != '':
                speech_path = os.path.join(UPLOAD_FOLDER, f"{job_id}_user_audio.mp3")
                uploaded_audio.save(speech_path)
                
        # Handle optional background music upload
        bg_music_file = request.files.get('bg_music_file')
        if bg_music_file and bg_music_file.filename != '':
            bg_music_path = os.path.join(UPLOAD_FOLDER, f"{job_id}_bg_music.mp3")
            bg_music_file.save(bg_music_path)
            
        # Mix audio tracks if we have speech or background music
        if speech_path or bg_music_path:
            mixed_audio = os.path.join(UPLOAD_FOLDER, f"{job_id}_mixed.mp3")
            final_audio_path = create_mixed_audio(
                speech_path=speech_path,
                bg_music_path=bg_music_path,
                target_duration=duration,
                output_path=mixed_audio,
                trim_to_video=trim_audio
            )
            
        # 3. Combine merged video and final audio
        output_filename = f"merged_{job_id[:8]}.mp4"
        final_output_path = os.path.join(OUTPUT_FOLDER, output_filename)
        
        if final_audio_path and os.path.exists(final_audio_path):
            # Combine via FFmpeg for speed and precision
            cmd = [
                "ffmpeg", "-y", "-i", merged_temp_video, "-i", final_audio_path,
                "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac",
                "-shortest" if trim_audio else "", final_output_path
            ]
            # Remove empty arguments from command
            cmd = [c for c in cmd if c != ""]
            subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        else:
            # No audio overlay, rename raw merged video
            os.rename(merged_temp_video, final_output_path)
            
        # Cleanup temp upload files
        for p in video_paths + [merged_temp_video, speech_path, bg_music_path, final_audio_path]:
            if p and os.path.exists(p):
                try:
                    os.remove(p)
                except Exception:
                    pass
                    
        return jsonify({
            'success': True,
            'message': 'Videos merged successfully!',
            'filename': output_filename,
            'duration': f"{duration:.2f}s"
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/clip', methods=['POST'])
def clip_youtube_video():
    """
    Downloads a YouTube video, cuts it into clips, and applies anti-copyright filters.
    """
    try:
        url = request.form.get('url')
        if not url:
            return jsonify({'success': False, 'error': 'YouTube URL is required.'}), 400
            
        mode = request.form.get('mode', 'auto') # 'auto' or 'timestamps'
        interval = int(request.form.get('interval', 8))
        timestamps_str = request.form.get('timestamps', '')
        
        # Filter options
        filters = {
            'aspect_ratio': request.form.get('aspect_ratio', 'original'),
            'mirror': request.form.get('mirror', 'true') == 'true',
            'zoom': request.form.get('zoom', 'true') == 'true',
            'speed': float(request.form.get('speed', 1.04)),
            'pitch_shift': float(request.form.get('pitch_shift', 0.8))
        }
        
        job_id = str(uuid.uuid4())
        raw_download_path = os.path.join(UPLOAD_FOLDER, f"{job_id}_raw.mp4")
        
        # 1. Download YouTube Video using yt-dlp
        ytdlp_bin = get_pip_binary('yt-dlp')
        
        print(f"Downloading video from {url}...")
        download_cmd = [
            ytdlp_bin,
            "-f", "bestvideo+bestaudio/best",
            "--merge-output-format", "mp4",
            "-o", raw_download_path,
            url
        ]
        
        result = subprocess.run(download_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if result.returncode != 0 or not os.path.exists(raw_download_path):
            error_msg = result.stderr.decode('utf-8', errors='ignore')
            return jsonify({'success': False, 'error': f"Failed to download YouTube video: {error_msg}"}), 500
            
        # 2. Slice downloaded video
        temp_clips_dir = os.path.join(UPLOAD_FOLDER, f"{job_id}_slices")
        os.makedirs(temp_clips_dir, exist_ok=True)
        
        custom_ranges = []
        if mode == 'timestamps' and timestamps_str:
            # Parse timestamps "10-20, 30-45"
            parts = timestamps_str.split(',')
            for part in parts:
                subparts = part.strip().split('-')
                if len(subparts) == 2:
                    try:
                        start_t = float(subparts[0].strip())
                        end_t = float(subparts[1].strip())
                        custom_ranges.append([start_t, end_t])
                    except ValueError:
                        pass
                        
        sliced_files = slice_video(
            raw_download_path,
            temp_clips_dir,
            mode=mode,
            intervals=interval,
            custom_ranges=custom_ranges
        )
        
        if not sliced_files:
            return jsonify({'success': False, 'error': 'No clips generated during slicing.'}), 500
            
        # 3. Apply safety filters to each clip and save to outputs
        processed_files = []
        for idx, file_path in enumerate(sliced_files, 1):
            out_filename = f"clip_{job_id[:8]}_{idx}.mp4"
            out_path = os.path.join(OUTPUT_FOLDER, out_filename)
            
            apply_copyright_filters(file_path, out_path, filters)
            if os.path.exists(out_path):
                processed_files.append(out_filename)
                
        # Cleanup raw downloaded file & sliced folder
        if os.path.exists(raw_download_path):
            os.remove(raw_download_path)
            
        import shutil
        if os.path.exists(temp_clips_dir):
            shutil.rmtree(temp_clips_dir)
            
        return jsonify({
            'success': True,
            'message': f'YouTube video processed into {len(processed_files)} clips!',
            'filenames': processed_files
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

def get_video_duration(path):
    try:
        cmd = [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", path
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if res.returncode == 0:
            duration = float(res.stdout.strip())
            return f"{duration:.1f}s"
    except Exception:
        pass
    return "unknown"

@app.route('/api/outputs', methods=['GET'])
def get_outputs():
    """Lists all real (non-temp) output files, newest first."""
    SKIP_PATTERNS = ('.temp', 'TEMP_MPY', '.part', '.tmp')
    files = []
    for f in os.listdir(OUTPUT_FOLDER):
        # Only include clean .mp4 files — skip any temp/partial artifacts
        if not f.endswith('.mp4'):
            continue
        if any(pat in f for pat in SKIP_PATTERNS):
            # Also delete them from disk so they don't pile up
            try:
                os.remove(os.path.join(OUTPUT_FOLDER, f))
            except Exception:
                pass
            continue
        path = os.path.join(OUTPUT_FOLDER, f)
        size_mb = os.path.getsize(path) / (1024 * 1024)
        files.append({
            'filename': f,
            'size': f"{size_mb:.2f} MB",
            'duration': get_video_duration(path)
        })
    # Sort newest first
    files.sort(
        key=lambda x: os.path.getmtime(os.path.join(OUTPUT_FOLDER, x['filename'])),
        reverse=True
    )
    return jsonify(files)

@app.route('/api/generate-video', methods=['POST'])
def generate_video():
    """
    End-to-end AI script-to-video generation route.
    """
    try:
        script_text   = request.form.get('script_text', '')
        theme         = request.form.get('theme', 'auto')
        aspect_ratio  = request.form.get('aspect_ratio', 'vertical')
        voice_id      = request.form.get('voice', 'ur-PK-UzmaNeural')
        voice_rate    = request.form.get('rate', '+0%')
        voice_pitch   = request.form.get('pitch', '+0Hz')
        trim_audio    = request.form.get('trim_audio', 'true') == 'true'
        
        if not script_text.strip():
            return jsonify({'success': False, 'error': 'Script text is required.'}), 400
            
        bg_music_file = request.files.get('bg_music_file')
        
        job_id = str(uuid.uuid4())
        output_filename = f"ai_video_{job_id[:8]}.mp4"
        final_output_path = os.path.join(OUTPUT_FOLDER, output_filename)
        
        res = generate_ai_video(
            script_text=script_text,
            theme=theme,
            aspect_ratio=aspect_ratio,
            voice_id=voice_id,
            rate=voice_rate,
            pitch=voice_pitch,
            bg_music_file=bg_music_file,
            trim_audio=trim_audio,
            output_path=final_output_path
        )
        
        if res.get('success'):
            return jsonify({
                'success': True,
                'message': 'AI Video generated successfully!',
                'filename': output_filename,
                'duration': f"{res.get('duration'):.2f}s",
                'slides': res.get('sentences_count')
            })
        else:
            return jsonify({'success': False, 'error': 'Video generation failed.'}), 500
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/outputs/<filename>', methods=['GET'])
def download_file(filename):
    """Serves file from outputs folder."""
    return send_from_directory(OUTPUT_FOLDER, filename)


if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5005))
    host = os.environ.get('HOST', '127.0.0.1')
    debug = os.environ.get('FLASK_ENV', 'production') == 'development'
    app.run(debug=debug, host=host, port=port)
