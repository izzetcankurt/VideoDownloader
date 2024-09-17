import os
import shutil
import threading
import time
import uuid
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, send_from_directory, send_file, \
    after_this_request, flash, jsonify
from pytubefix import YouTube, Playlist
import subprocess
from werkzeug.utils import secure_filename
import re
from moviepy.editor import VideoFileClip, AudioFileClip, concatenate_videoclips

app = Flask(__name__)
app.secret_key = 'Secret35'

i = 0
j = 0
k = 0

progress_status = {}
progress_status_mp4 = {}
progress_status_webm = {}
progress_status_list_aud = {}
progress_status_list_vid = {}

token_file = os.path.join(os.getcwd(), "tokens.json")

def down_video(link, resolution, formatted_time, task_id, upload_folder):
    global progress_status_mp4
    yt = YouTube(link, on_progress_callback=lambda stream, chunk, bytes_remaining: video_progress_callback(stream, chunk, bytes_remaining, task_id), use_oauth=True, allow_oauth_cache=True, token_file=token_file)
    video = yt.streams.filter(res=resolution, file_extension='mp4', only_video=True).first()
    video_file = video.download(output_path=upload_folder, filename=("v_" + str(formatted_time) + '.mp4'))
    return video_file

def video_progress_callback(stream, chunk, bytes_remaining, task_id):
    total_size = stream.filesize
    current_progress = 100 - (bytes_remaining / total_size * 100)
    progress_status_mp4[task_id]["video_download"] = current_progress
    progress_status_mp4[task_id]["message"] = "Video downloading..."


def down_audio(link, formatted_time, task_id, upload_folder):
    global progress_status_mp4
    yt = YouTube(link, on_progress_callback=lambda stream, chunk, bytes_remaining: audio_progress_callback(stream, chunk, bytes_remaining, task_id), use_oauth=True, allow_oauth_cache=True, token_file=token_file)
    
    # Download the audio file (assuming it downloads in .mp4 format)
    audio = yt.streams.filter(only_audio=True, file_extension='mp4').order_by('itag').desc().first()
    audio_file = audio.download(output_path=upload_folder, filename=("a_" + str(formatted_time) + '.mp4'))
    
    # Convert the audio file to MP3 using MoviePy
    audio_clip = AudioFileClip(audio_file)
    audio_file_final = os.path.join(upload_folder, f'af_{formatted_time}.mp3')
    audio_clip.write_audiofile(audio_file_final, codec='mp3')
    
    # Clean up the intermediate file if necessary
    os.remove(audio_file)
    
    return audio_file_final


def audio_progress_callback(stream, chunk, bytes_remaining, task_id):
    total_size = stream.filesize
    current_progress = 100 - (bytes_remaining / total_size * 100)
    progress_status_mp4[task_id]["audio_download"] = current_progress
    progress_status_mp4[task_id]["message"] = "Audio downloading..."


def down_video_and_audio(link, resolution,formatted_time, task_id, upload_folder):
    video_file = down_video(link, resolution,formatted_time, task_id, upload_folder)
    audio_file = down_audio(link,formatted_time, task_id, upload_folder)
    return video_file, audio_file


def down_video_webm(link, resolution, formatted_time, task_id, upload_folder):
    global progress_status_webm
    yt = YouTube(link, on_progress_callback=lambda stream, chunk, bytes_remaining: video_progress_callback_webm(stream, chunk, bytes_remaining, task_id), use_oauth=True, allow_oauth_cache=True, token_file=token_file)
    video = yt.streams.filter(res=resolution, file_extension='webm', only_video=True).first()
    video_file = video.download(output_path=upload_folder, filename=("v_" + str(formatted_time) + '.webm'))
    return video_file

def video_progress_callback_webm(stream, chunk, bytes_remaining, task_id):
    total_size = stream.filesize
    current_progress = 100 - (bytes_remaining / total_size * 100)
    try:
        progress_status_webm[task_id]["video_download"] = current_progress
        progress_status_webm[task_id]["message"] = "Video downloading..."
    except:
        progress_status_mp4[task_id]["video_download_w"] = current_progress
        progress_status_mp4[task_id]["message"] = "Video downloading..."

def down_audio_webm(link, formatted_time, task_id, upload_folder):
    global progress_status_webm
    yt = YouTube(link, on_progress_callback=lambda stream, chunk, bytes_remaining: audio_progress_callback_webm(stream, chunk, bytes_remaining, task_id), use_oauth=True, allow_oauth_cache=True, token_file=token_file)
    audio = yt.streams.filter(only_audio=True, file_extension='webm').order_by('itag').desc().first()
    audio_file = audio.download(output_path=upload_folder, filename=("af_" + str(formatted_time) + '.webm'))
    return audio_file

def audio_progress_callback_webm(stream, chunk, bytes_remaining, task_id):
    total_size = stream.filesize
    current_progress = 100 - (bytes_remaining / total_size * 100)
    try:
        progress_status_webm[task_id]["audio_download"] = current_progress
        progress_status_webm[task_id]["message"] = "Audio downloading..."
    except:
        progress_status_mp4[task_id]["audio_download_w"] = current_progress
        progress_status_mp4[task_id]["message"] = "Audio downloading..."


def down_video_and_audio_webm(link, resolution,formatted_time, task_id, upload_folder):
    video_file = down_video_webm(link, resolution,formatted_time, task_id, upload_folder)
    audio_file = down_audio_webm(link,formatted_time, task_id, upload_folder)
    return video_file, audio_file


def merge_video_and_audio(video_file, audio_file, output_file, task_id):
    global progress_status_mp4
    try:
        video_clip = VideoFileClip(video_file)
        audio_clip = AudioFileClip(audio_file)
        
        # Set audio to video clip
        video_clip = video_clip.set_audio(audio_clip)
        
        def track_progress():
            total_duration = video_clip.duration
            while True:
                current_time = video_clip.reader.pos / video_clip.reader.fps
                progress = (current_time / total_duration) * 100
                progress_status_mp4[task_id]["merge"] = progress
                time.sleep(1)  # Update every second
                if current_time >= total_duration:
                    break
        
        from threading import Thread
        progress_thread = Thread(target=track_progress)
        progress_thread.start()

        # Write the result to a file
        video_clip.write_videofile(output_file, codec='libx264', audio_codec='aac', threads=4)
        
        progress_thread.join()
        # Update progress
        progress_status_mp4[task_id]["merge"] = 100
        progress_status_mp4[task_id]["message"] = "Merging complete!"
    except Exception as e:
        progress_status_mp4[task_id]["message"] = f"Error merging video: {e}"


@app.route('/progress_mp4/<task_id>')
def progress_mp4(task_id):
    status = progress_status_mp4.get(task_id, {
        "video_download": 0,
        "audio_download": 0,
        "merge": 0,
        "lang":0,
        "video_download_w": 0,
        "audio_download_w": 0,
        "merge_w":0,
        "convert":0,
        "message": ""
    })
    return jsonify(status)


def merge_video_and_audio_webm(video_file, audio_file, output_file, task_id):
    global progress_status_webm
    try:
        video_clip = VideoFileClip(video_file)
        audio_clip = AudioFileClip(audio_file)
        
        # Set audio to video clip
        video_clip = video_clip.set_audio(audio_clip)

        def track_progress():
            total_duration = video_clip.duration
            while True:
                current_time = video_clip.reader.pos / video_clip.reader.fps
                progress = (current_time / total_duration) * 100
                try:
                    progress_status_webm[task_id]["merge"] = progress
                    progress_status_webm[task_id]["message"] = "Merging..."
                except:
                    progress_status_mp4[task_id]["merge_w"] = progress
                    progress_status_mp4[task_id]["message"] = "Merging..."
                time.sleep(1)  # Update every second
                if current_time >= total_duration:
                    break
        
        from threading import Thread
        progress_thread = Thread(target=track_progress)
        progress_thread.start()
        
        # Write the result to a file
        video_clip.write_videofile(output_file, codec='libvpx', audio_codec='libvorbis', threads=4)
        
        progress_thread.join()
        # Update progress
        try:
            progress_status_webm[task_id]["merge"] = 100
            progress_status_webm[task_id]["message"] = "Merging complete!"
        except:
            progress_status_mp4[task_id]["merge_w"] = 100
            progress_status_mp4[task_id]["message"] = "Merge complete!"
    except Exception as e:
        progress_status_webm[task_id]["message"] = f"Error merging video: {e}"

@app.route('/progress_webm/<task_id>')
def progress_webm(task_id):
    status = progress_status_webm.get(task_id, {"video_download": 0, "audio_download": 0, "merge": 0, "message": ""})
    return jsonify(status)


def merge_lang_and_mp4(mp4, lang, output_file, task_id):
    global progress_status_mp4
    try:
        # ffmpeg command to merge subtitles with video
        command = [
            'ffmpeg',
            '-i', mp4,  # Input video file
            '-vf', f"subtitles='{lang}'",  # Subtitle filter
            '-c:v', 'libx264',  # Video codec
            '-c:a', 'copy',  # Copy audio without re-encoding
            '-c:s', 'mov_text',  # Subtitle codec
            output_file  # Output file
        ]

        # Execute the command
        process = subprocess.Popen(command, stderr=subprocess.PIPE, universal_newlines=True)

        # Track progress of the merge operation
        total_duration = get_video_duration(mp4)  # Assuming you have a function to get video duration
        for line in process.stderr:
            if 'time=' in line:
                time_match = re.search(r'time=(\d+:\d+:\d+\.\d+)', line)
                if time_match:
                    current_time_str = time_match.group(1)
                    current_time = sum(float(x) * 60 ** i for i, x in enumerate(reversed(current_time_str.split(':'))))
                    progress_status_mp4[task_id]["lang"] = (current_time / total_duration) * 100
                    progress_status_mp4[task_id]["message"] = "Subtitle adding..."

        process.wait()  # Wait for the process to complete
        if process.returncode == 0:
            progress_status_mp4[task_id][
                "message"] = "Subtitle added."
            progress_status_mp4[task_id]["lang"] = 100
        else:
            progress_status_mp4[task_id]["message"] = f"Error merging video and subtitles: {process.stderr.read()}"

    except Exception as e:
        progress_status_mp4[task_id]["message"] = f"Exception during merging: {e}"



def get_video_duration(input_file):
    """Retrieve the duration of the video file using ffmpeg."""
    result = subprocess.run(
        ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', input_file],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT
    )
    return float(result.stdout)

def convert_webm_to_mp4(input_file, output_file, task_id):
    global progress_status
    try:
        video_clip = VideoFileClip(input_file)
        total_duration = video_clip.duration
        
        def track_progress():
            while True:
                # Compute progress based on the current position in the video
                current_time = video_clip.reader.pos / video_clip.reader.fps
                progress = (current_time / total_duration) * 100
                try:
                    progress_status[task_id]["progress"] = progress
                    progress_status[task_id]["message"] = "Video converting..."
                except:
                    progress_status_mp4[task_id]["convert"] = progress
                    progress_status_mp4[task_id]["message"] = "Video converting..."
                time.sleep(1)  # Update every second
                if current_time >= total_duration:
                    break
        
        # Start a thread to track progress
        progress_thread = threading.Thread(target=track_progress)
        progress_thread.start()
        
        # Write the video file to the desired output format
        video_clip.write_videofile(output_file, codec='libx264', audio_codec='aac', threads=4)
        
        # Wait for the progress tracking thread to finish
        progress_thread.join()
        
        # Update progress status to 100% on completion
        try:
            progress_status[task_id]["progress"] = 100
            progress_status[task_id]["message"] = "Conversion complete!"
        except:
            progress_status_mp4[task_id]["convert"] = 100
            progress_status_mp4[task_id]["message"] = "Conversion complete!"
    except Exception as e:
        try:
            progress_status[task_id]["message"] = f"Error converting video: {e}"
        except:
            progress_status_mp4[task_id]["message"] = f"Error converting video: {e}"

def convert_mp4_to_webm(input_file, output_file, task_id):
    global progress_status
    try:
        video_clip = VideoFileClip(input_file)

        def track_progress():
            total_duration = video_clip.duration
            while True:
                current_time = video_clip.reader.pos / video_clip.reader.fps
                progress = (current_time / total_duration) * 100
                progress_status[task_id]["progress"] = progress
                progress_status[task_id]["message"] = "Video converting..."
                if current_time >= total_duration:
                    break
                time.sleep(1)  # Update every second

        from threading import Thread
        progress_thread = Thread(target=track_progress)
        progress_thread.start()

        # Convert MP4 to WebM
        video_clip.write_videofile(output_file, codec='libvpx', audio_codec='libvorbis', bitrate='1M', threads=4)

        progress_thread.join()
        progress_status[task_id]["progress"] = 100
        progress_status[task_id]["message"] = "Video converted!"

    except Exception as e:
        progress_status[task_id]["message"] = f"Error converting video: {e}"



@app.route('/progress/<task_id>')
def progress(task_id):
    return jsonify(progress_status.get(task_id, {"progress": 0, "message": ""}))

"""
def cleanup_uploads(directory):
    for filename in os.listdir(directory):
        file_path = os.path.join(directory, filename)
        try:
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
        except Exception as e:
            print(f'Failed to delete {file_path}. Reason: {e}')
"""
"""
@app.route('/cleanup', methods=['POST'])
def cleanup():
    try:
        cleanup_uploads(UPLOAD_DIRECTORY)
        return 'Cleanup successful', 200
    except Exception as e:
        return f'Cleanup failed: {e}', 500
"""

@app.route('/')
def main():
    return render_template('main.html')


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in {'mp4', 'webm'}


@app.route('/convert', methods=['POST'])
def convert():
    if 'file' not in request.files:
        flash('No file part')
        return redirect(request.url)

    file = request.files['file']

    if file.filename == '':
        flash('No selected file')
        return redirect(request.url)

    if file and allowed_file(file.filename):
        # Generate unique task ID
        task_id = str(uuid.uuid4())

        upload_folder = os.path.join(os.getcwd(), f'uploads_{task_id}')
        if not os.path.exists(upload_folder):
            os.makedirs(upload_folder)
        app.config['upload_folder'] = upload_folder

        filename = secure_filename(file.filename)
        file_path = os.path.join(upload_folder, filename)
        file.save(file_path)

        # Determine file extension and set output filename
        file_ext = filename.rsplit('.', 1)[1].lower()
        if file_ext == 'webm':
            output_filename = f'video_{task_id}.mp4'
        elif file_ext == 'mp4':
            output_filename = f'video_{task_id}.webm'
        else:
            flash('Invalid file format')
            return redirect(request.url)

        output_path = os.path.join(upload_folder, output_filename)

        # Start conversion in a separate thread to handle progress
        def start_conversion():
            global progress_status
            try:
                progress_status[task_id] = {"progress": 0, "message": ""}
                if file_ext == 'webm':
                    convert_webm_to_mp4(file_path, output_path, task_id)
                elif file_ext == 'mp4':
                    convert_mp4_to_webm(file_path, output_path, task_id)
            finally:
                progress_status[task_id]["message"] = 'Conversion complete!'

        threading.Thread(target=start_conversion).start()

        return jsonify({'task_id': task_id})

    flash('Invalid file format')
    return redirect(request.url)


def convert_video(file_path, upload_folder, filename, formatted_time, task_id):
    file_ext = filename.rsplit('.', 1)[1].lower()
    output_filename = f'video_{formatted_time}.mp4' if file_ext == 'webm' else f'video_{formatted_time}.webm'
    output_path = os.path.join(upload_folder, output_filename)

    if file_ext == 'webm':
        convert_webm_to_mp4(file_path, output_path, task_id)
    elif file_ext == 'mp4':
        convert_mp4_to_webm(file_path, output_path, task_id)

@app.route('/download/<task_id>')
def download(task_id):
    upload_folder = os.path.join(os.getcwd(), f'uploads_{task_id}')
    output_files = [f for f in os.listdir(upload_folder) if f.startswith(f'video_{task_id}')]
    if output_files:
        output_file = os.path.join(upload_folder, output_files[0])
        if os.path.exists(output_file):
            return send_file(output_file, as_attachment=True)


@app.route('/select_res', methods=["POST"])
def select_res():
    link = request.form.get('link')
    res_list_mp4 = []
    res_list_webm = []
    is_mp4_normal = True
    try:
        yt = YouTube(link, use_oauth=True, allow_oauth_cache=True, token_file=token_file)
        captions = yt.captions
        lang_list = [caption.code for caption in captions]
        stream = yt.streams.filter(file_extension='mp4').order_by('resolution').desc()
        stream2 = yt.streams.filter(file_extension='webm').order_by('resolution').desc()
        filtered_stream = [s for s in stream if s.codecs and s.codecs[0].startswith("av01")]
        if len(filtered_stream) == 0:
            is_mp4_normal = False
        else:
            pass
        for i in filtered_stream:
            if not i.resolution in res_list_mp4:
                res_list_mp4.append(i.resolution)
        for i in stream2:
            if not i.resolution in res_list_webm:
                res_list_webm.append(i.resolution)
            if not i.resolution in res_list_mp4:
                res_list_mp4.append(i.resolution)

        thumbnail_url = yt.thumbnail_url
        video_title = yt.title
        times = yt.length
        minutes, seconds = divmod(times, 60)
        video_time = f"{minutes} minutes, {seconds} seconds."

        return render_template('res_select.html', res_list_mp4=res_list_mp4, link=link, lang_list=lang_list, res_list_webm=res_list_webm,thumbnail_url=thumbnail_url,
            video_title=video_title, video_time=video_time, is_mp4_normal=is_mp4_normal)
    except Exception as e:
        flash("Invalid link or error occurred. Please check the link and try again.", "video")
        return redirect(url_for('main'))


@app.route('/downloadvideo/<task_id>/<time>')
def downloadvideo(task_id, time):
    upload_folder = os.path.join(os.getcwd(), f'uploads_{task_id}')
    output_files = [f for f in os.listdir(upload_folder) if f.startswith(f'video_{time}')]
    if output_files:
        output_file = os.path.join(upload_folder, output_files[0])
        if os.path.exists(output_file):
            return send_file(output_file, as_attachment=True)


@app.route('/download_video_a', methods=["POST", "GET"])
def download_video_a():
    link = request.form.get('link')
    yt = YouTube(link, use_oauth=True, allow_oauth_cache=True, token_file=token_file)
    stream = yt.streams.filter(file_extension='mp4').order_by('resolution').desc()
    filtered_stream = [s for s in stream if s.codecs and s.codecs[0].startswith("av01")]
    resolution = request.form.get('resolution')
    task_id = str(uuid.uuid4())  # Generate unique task ID
    now = datetime.now()
    formatted_time = now.strftime('%H_%M_%S')

    upload_folder = os.path.join(os.getcwd(), f'uploads_{task_id}')
    if not os.path.exists(upload_folder):
        os.makedirs(upload_folder)
    app.config['upload_folder'] = upload_folder

    # Initialize progress status for this task
    global progress_status_mp4
    progress_status_mp4[task_id] = {
        "video_download": 0,
        "audio_download": 0,
        "merge": 0,
        "lang": 0,
        "video_download_w": 0,
        "audio_download_w": 0,
        "merge_w": 0,
        "convert": 0,
        "message": ""
    }
    video_file_path = os.path.join(upload_folder, f'v_{formatted_time}.mp4')
    audio_file_path = os.path.join(upload_folder, f'af_{formatted_time}.mp3')
    convert_video_path = os.path.join(upload_folder, f'c_{formatted_time}.webm')
    final_video_path = os.path.join(upload_folder, f'video_{formatted_time}.mp4')

    try:
        if len(filtered_stream)==0:

            def download_and_merge():
                video_file, audio_file = down_video_and_audio_webm(link, resolution, formatted_time, task_id, upload_folder)
                merge_video_and_audio_webm(video_file, audio_file, convert_video_path, task_id)

                convert_webm_to_mp4(convert_video_path, final_video_path, task_id)

            threading.Thread(target=download_and_merge).start()

            return jsonify({'status': 'success', 'task_id': task_id,
                            'file_path': url_for('downloadvideo', task_id=task_id, time=formatted_time)})

        else:
            def download_and_merge():
                # Download video
                down_video(link, resolution, formatted_time, task_id, upload_folder)
                progress_status_mp4[task_id]["video_download"] = 100

                # Download audio
                down_audio(link, formatted_time, task_id, upload_folder)
                progress_status_mp4[task_id]["audio_download"] = 100

                # Merge video and audio
                merge_video_and_audio(video_file_path, audio_file_path, final_video_path, task_id)

            threading.Thread(target=download_and_merge).start()

            return jsonify({'status': 'success', 'task_id': task_id,
                            'file_path': url_for('downloadvideo', task_id=task_id, time=formatted_time)})

    except Exception as e:
        return str(e)

"""
@app.route('/serve_file/<filename>', methods=["GET"])
def serve_file(filename):
    file_path = os.path.join(upload_folder, filename)
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True)
    else:
        return jsonify({'status': 'error', 'message': 'File not found'}), 404
"""

@app.route('/download_video_b', methods=["POST"])
def download_video_b():
    link = request.form.get('link')
    resolution = request.form.get('resolution')
    task_id = str(uuid.uuid4())  # Generate unique task ID
    now = datetime.now()
    formatted_time = now.strftime('%H_%M_%S')

    upload_folder = os.path.join(os.getcwd(), f'uploads_{task_id}')
    if not os.path.exists(upload_folder):
        os.makedirs(upload_folder)
    app.config['upload_folder'] = upload_folder

    # Initialize progress status for this task
    global progress_status_webm
    progress_status_webm[task_id] = {
        "video_download": 0,
        "audio_download": 0,
        "merge": 0,
        "message": ""
    }

    try:
        def download_and_merge():
            video_file, audio_file = down_video_and_audio_webm(link, resolution, formatted_time, task_id, upload_folder)
            final_video_path = os.path.join(upload_folder, f'video_{formatted_time}.webm')
            merge_video_and_audio_webm(video_file, audio_file, final_video_path, task_id)

        threading.Thread(target=download_and_merge).start()

        return jsonify({'status': 'success', 'task_id': task_id,
                        'file_path': url_for('downloadvideo', task_id=task_id, time=formatted_time)})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})


@app.route('/download_v_subtitle', methods=["POST"])
def download_v_subtitle():
    link = request.form.get('link')
    yt = YouTube(link, use_oauth=True, allow_oauth_cache=True, token_file=token_file)
    stream = yt.streams.filter(file_extension='mp4').order_by('resolution').desc()
    filtered_stream = [s for s in stream if s.codecs and s.codecs[0].startswith("av01")]
    resolution = request.form.get('resolution')
    task_id = str(uuid.uuid4())  # Generate unique task ID
    lang = request.form.get('lang')
    now = datetime.now()
    formatted_time = now.strftime('%H_%M_%S')
    upload_folder = os.path.join(os.getcwd(), f'uploads_{task_id}')
    if not os.path.exists(upload_folder):
        os.makedirs(upload_folder)
    app.config['upload_folder'] = upload_folder

    # Initialize progress status for this task
    global progress_status_mp4
    progress_status_mp4[task_id] = {
        "video_download": 0,
        "audio_download": 0,
        "merge": 0,
        "lang": 0,
        "video_download_w": 0,
        "audio_download_w": 0,
        "merge_w": 0,
        "convert": 0,
        "message": ""
    }

    video_file_path = os.path.join(upload_folder, f'v_{formatted_time}.mp4')
    audio_file_path = os.path.join(upload_folder, f'af_{formatted_time}.mp3')
    convert_video_path = os.path.join(upload_folder, f'c_{formatted_time}.webm')
    final_video_path = os.path.join(upload_folder, f'vid_{formatted_time}.mp4')
    try:
        if len(filtered_stream) == 0:
            def download_and_merge():
                video_file, audio_file = down_video_and_audio_webm(link, resolution, formatted_time, task_id,
                                                                   upload_folder)
                merge_video_and_audio_webm(video_file, audio_file, convert_video_path, task_id)
                convert_webm_to_mp4(convert_video_path, final_video_path, task_id)
                caption = yt.captions[lang]
                if caption:
                    caption_file = f'caption_{formatted_time}.srt'
                    with open(caption_file, 'w', encoding='utf-8') as file:
                        file.write(caption.generate_srt_captions())
                # Convert paths to use forward slashes for ffmpeg
                final_video_path2 = final_video_path.replace("\\", "/")
                final_video = os.path.join(upload_folder, f'video_{formatted_time}.mp4')
                final_video = final_video.replace("\\", "/")
                merge_lang_and_mp4(final_video_path2, caption_file, final_video, task_id=task_id)
            threading.Thread(target=download_and_merge).start()
            return jsonify({'status': 'success', 'task_id': task_id,
                            'file_path': url_for('downloadvideo', task_id=task_id, time=formatted_time)})
        else:
            def download_and_merge():
                # Download video
                down_video(link, resolution, formatted_time, task_id, upload_folder)
                progress_status_mp4[task_id]["video_download"] = 100
                # Download audio
                down_audio(link, formatted_time, task_id, upload_folder)
                progress_status_mp4[task_id]["audio_download"] = 100
                # Merge video and audio
                merge_video_and_audio(video_file_path, audio_file_path, final_video_path, task_id)
                caption = yt.captions[lang]
                if caption:
                    caption_file = f'caption_{formatted_time}.srt'
                    with open(caption_file, 'w', encoding='utf-8') as file:
                        file.write(caption.generate_srt_captions())
                        
                final_video_path2 = final_video_path.replace("\\", "/")
                final_video = os.path.join(upload_folder, f'video_{formatted_time}.mp4')
                final_video = final_video.replace("\\", "/")
                merge_lang_and_mp4(final_video_path2, caption_file, final_video, task_id=task_id)
            threading.Thread(target=download_and_merge).start()
            return jsonify({'status': 'success', 'task_id': task_id,
                            'file_path': url_for('downloadvideo', task_id=task_id, time=formatted_time)})

    except Exception as e:
        return str(e)

@app.route('/downloadaudio/<task_id>/<time>')
def downloadaudio(task_id, time):
    upload_folder = os.path.join(os.getcwd(), f'uploads_{task_id}')
    output_file = os.path.join(upload_folder, f'af_{time}.mp3')
    if os.path.exists(output_file):
        return send_file(output_file, as_attachment=True)
    else:
        return "File not found", 404


@app.route('/download_audio', methods=["POST"])
def download_audio():
    link = request.form.get('link')
    task_id = str(uuid.uuid4())  # Generate unique task ID
    now = datetime.now()
    formatted_time = now.strftime('%H_%M_%S')
    upload_folder = os.path.join(os.getcwd(), f'uploads_{task_id}')
    if not os.path.exists(upload_folder):
        os.makedirs(upload_folder)
    app.config['upload_folder'] = upload_folder
    # Initialize progress status for this task
    global progress_status_mp4
    progress_status_mp4[task_id] = {
        "video_download": 0,
        "audio_download": 0,
        "merge": 0,
        "lang": 0,
        "video_download_w": 0,
        "audio_download_w": 0,
        "merge_w": 0,
        "convert": 0,
        "message": ""
    }
    out = os.path.join(upload_folder, f'af_{formatted_time}.mp3')
    try:
        yt = YouTube(link, use_oauth=True, allow_oauth_cache=True, token_file=token_file)
        stream = yt.streams.filter(file_extension='mp4').order_by('resolution').desc()
        filtered_stream = [s for s in stream if s.codecs and s.codecs[0].startswith("av01")]
        if len(filtered_stream)==0:
            def download_aud():
                audio_file = down_audio_webm(link, formatted_time, task_id, upload_folder)
                conv(audio_file, out, task_id)
            threading.Thread(target=download_aud).start()
            return jsonify({'status': 'success', 'task_id': task_id,
                            'file_path': url_for('downloadaudio', task_id=task_id, time=formatted_time)})
        else:
            def download_aud():
                down_audio(link, formatted_time,task_id, upload_folder)
                progress_status_mp4[task_id]["message"] = "Completed!"
            threading.Thread(target=download_aud).start()
            return jsonify({'status': 'success', 'task_id': task_id,
                            'file_path': url_for('downloadaudio', task_id=task_id, time=formatted_time)})
    except Exception as e:
        return str(e)

def conv(audio_file, out, task_id):
    global progress_status_mp4
    try:
        # Load the audio file with MoviePy
        audio_clip = AudioFileClip(audio_file)
        total_duration = audio_clip.duration
        
        progress_status_mp4[task_id]["audio_download_w"] = 100

        # Create a function to track the conversion progress
        def track_progress():
            while True:
                current_time = audio_clip.reader.pos / audio_clip.reader.fps
                progress = (current_time / total_duration) * 100
                progress_status_mp4[task_id]["convert"] = progress
                progress_status_mp4[task_id]["message"] = "Converting..."
                time.sleep(1)  # Update every second
                if current_time >= total_duration:
                    break

        from threading import Thread
        progress_thread = Thread(target=track_progress)
        progress_thread.start()

        # Convert and save the file as MP3
        audio_clip.write_audiofile(out, codec='mp3', bitrate='192k')

        progress_thread.join()
        
        # Mark the task as completed
        progress_status_mp4[task_id]["message"] = "Completed!"
        progress_status_mp4[task_id]["convert"] = 100
    except Exception as e:
        progress_status_mp4[task_id]["message"] = f"Error: {e}"

@app.route('/download_subtitle', methods=["POST"])
def download_subtitle():
    task_id = str(uuid.uuid4())  # Generate unique task ID
    upload_folder = os.path.join(os.getcwd(), f'uploads_{task_id}')
    if not os.path.exists(upload_folder):
        os.makedirs(upload_folder)
    app.config['upload_folder'] = upload_folder
    link = request.form.get('link')
    lang = request.form.get('lang')
    now = datetime.now()
    formatted_time = now.strftime('%H_%M_%S')
    try:
        yt = YouTube(link, use_oauth=True, allow_oauth_cache=True, token_file=token_file)
        caption = yt.captions[lang]
        if caption:
            caption_file = os.path.join(upload_folder, f'caption_{formatted_time}.txt')
            with open(caption_file, 'w', encoding='utf-8') as file:
                file.write(caption.generate_srt_captions())

        return send_file(caption_file, as_attachment=True)

    except Exception as e:
        return str(e)

@app.route('/playlist', methods=["POST"])
def playlist():
    playlist_link = request.form.get('playlist_link')
    try:
        pl = Playlist(playlist_link, use_oauth=True, allow_oauth_cache=True, token_file=token_file)
        thumbnail_url = YouTube(pl.video_urls[0], use_oauth=True, allow_oauth_cache=True, token_file=token_file).thumbnail_url
        video_title = pl.title

        return render_template('playlist.html', playlist_link=playlist_link, thumbnail_url=thumbnail_url,
                               video_title=video_title)
    except Exception as e:
        flash("Invalid link or error occurred. Please check the link and try again.", "playlist")
        return redirect(url_for('main'))


def compress_folder(folder_path, output_filename):
    # Remove the extension if provided in the output filename
    output_filename = output_filename.replace('.zip', '')

    # Create a ZIP file from the folder
    shutil.make_archive(output_filename, 'zip', folder_path)

def download_audio(task_id, playlist_link, upload_folder, output):
    global progress_status_list_aud
    progress_status_list_aud[task_id] = {"audio_download": 0, "audio_total": 0, "status":"Downloading"}
    pl = Playlist(playlist_link, use_oauth=True, allow_oauth_cache=True, token_file=token_file)
    all_links = pl.video_urls

    try:
        progress_status_list_aud[task_id]["audio_total"] = len(all_links)
        for link in all_links:
            yt = YouTube(link, use_oauth=True, allow_oauth_cache=True, token_file=token_file)
            # Existing logic for downloading audio
            stream = yt.streams.filter(file_extension='mp4').order_by('resolution').desc()
            filtered_stream = [s for s in stream if s.codecs and s.codecs[0].startswith("av01")]
            if len(filtered_stream) == 0:
                audio = yt.streams.filter(only_audio=True, file_extension='webm').order_by('itag').desc().first()
                audio_file = audio.download(output_path=upload_folder, filename=(str(yt.title) + '.webm'))
                # Convert the audio file to MP3 using MoviePy
                audio_clip = AudioFileClip(audio_file)
                out = os.path.join(upload_folder, (str(yt.title) + '.mp3'))
                audio_clip.write_audiofile(out, codec='mp3', bitrate='192k')
                if os.path.exists(audio_file):
                    os.remove(audio_file)
            else:
                audio = yt.streams.filter(only_audio=True, file_extension='mp4').order_by('itag').desc().first()
                audio_file = audio.download(output_path=upload_folder, filename=(str(yt.title) + '_temp.mp4'))
                
                audio_clip = AudioFileClip(audio_file)
                audio_file_final = os.path.join(upload_folder, f'{str(yt.title)}.mp3')
                audio_clip.write_audiofile(audio_file_final, codec='mp3')

                if os.path.exists(audio_file):
                    os.remove(audio_file)

            progress_status_list_aud[task_id]["audio_download"] += 1
        progress_status_list_aud[task_id]["status"] = "Downloaded"
        compress_folder(upload_folder, output)
        progress_status_list_aud[task_id]["status"] = "Compressed"
    except Exception as e:
        print(f"Error: {e}")

def download_video(task_id, playlist_link, upload_folder, final_folder, output):
    global progress_status_list_vid
    progress_status_list_vid[task_id] = {"video_download": 0, "video_total": 0, "status":"Downloading"}
    pl = Playlist(playlist_link, use_oauth=True, allow_oauth_cache=True, token_file=token_file)
    all_links = pl.video_urls
    try:
        progress_status_list_vid[task_id]["video_total"] = len(all_links)
        now = datetime.now()
        formatted_time = now.strftime('%H_%M_%S')

        for i, link in enumerate(all_links):
            yt = YouTube(link, use_oauth=True, allow_oauth_cache=True, token_file=token_file)
            stream = yt.streams.filter(file_extension='mp4').order_by('resolution').desc()
            filtered_stream = [s for s in stream if s.codecs and s.codecs[0].startswith("av01")]
            final_video_path2 = os.path.join(final_folder, (str(yt.title) + '.mp4'))
            try:
                if len(filtered_stream) == 0:
                    print(str(yt.title))
                    video = yt.streams.filter(file_extension='webm', only_video=True).order_by('resolution').desc()[1]
                    video_file = video.download(output_path=upload_folder, filename=("v_" + str(formatted_time) + "_" + str(i) + '.webm'))
                    audio = yt.streams.filter(only_audio=True, file_extension='webm').order_by('itag').desc().first()
                    audio_file = audio.download(output_path=upload_folder, filename=("a_" + str(formatted_time) + "_" + str(i) + '.webm'))
                    final_video_path = os.path.join(upload_folder, (str(yt.title) + '.webm'))
                    merge_video_and_audio_list_webm(video_file, audio_file, final_video_path)
                    convert_webm_to_mp4_list(final_video_path, final_video_path2)
                else:
                    filtered_video2 = filtered_stream[0]
                    video_file2 = filtered_video2.download(output_path=upload_folder, filename=("v_" + str(formatted_time) + "_" + str(i) + '.mp4'))
                    audio2 = yt.streams.filter(only_audio=True, file_extension='mp4').order_by('itag').desc().first()
                    audio_file2 = audio2.download(output_path=upload_folder, filename=("a_" + str(formatted_time) + "_" + str(i) + '.mp3'))
                    merge_video_and_audio_list(video_file2, audio_file2, final_video_path2)
            except:
                pass

            progress_status_list_vid[task_id]["video_download"] += 1
        progress_status_list_vid[task_id]["status"] = "Downloaded"
        compress_folder(final_folder, output)
        progress_status_list_vid[task_id]["status"] = "Compressed"

    except Exception as e:
        print(f"Error: {e}")


def merge_video_and_audio_list(video_file, audio_file, output_file):
    try:
        # Load video and audio clips
        video_clip = VideoFileClip(video_file)
        audio_clip = AudioFileClip(audio_file)
        
        # Set the audio to the video clip
        final_clip = video_clip.set_audio(audio_clip)
        
        # Write the result to the output file
        final_clip.write_videofile(output_file, codec='libx264', audio_codec='aac')
        
        return "Merging completed successfully"
    except Exception as e:
        return f"An error occurred: {str(e)}"

def merge_video_and_audio_list_webm(video_file, audio_file, output_file):
    try:
        # Load the video and audio clips
        video_clip = VideoFileClip(video_file)
        audio_clip = AudioFileClip(audio_file)
        
        # Set the audio to the video clip
        final_clip = video_clip.set_audio(audio_clip)
        
        # Write the result to the output file in WebM format
        final_clip.write_videofile(output_file, codec='libvpx', audio_codec='libvorbis')
        
        return "Merging completed successfully"
    except Exception as e:
        return f"There is an error while merging: {str(e)}"

def convert_webm_to_mp4_list(input_file, output_file):
    try:
        # Load the WebM video file (with audio)
        video_clip = VideoFileClip(input_file)
        
        # Write the output as MP4 with the desired codecs
        video_clip.write_videofile(output_file, codec='libx264', audio_codec='aac', bitrate="1M")
        
        return "Conversion completed successfully"
    except Exception as e:
        return f"An error occurred: {str(e)}"


@app.route('/progress_status_list_aud/<task_id>')
def progress_status_list_aud_func(task_id):
    status = progress_status_list_aud.get(task_id, {
        "audio_download": 0,
        "audio_total": 0,
        "status": "Downloading"
    })
    return jsonify(status)

@app.route('/progress_status_list_vid/<task_id>')
def progress_status_list_vid_func(task_id):
    status = progress_status_list_vid.get(task_id, {
        "video_download": 0,
        "video_total": 0,
        "status": "Downloading"
    })
    return jsonify(status)

@app.route('/download_list_a', methods=["POST"])
def download_list_a():
    task_id = str(uuid.uuid4())  # Generate unique task ID
    playlist_link = request.form.get('playlist_link')
    upload_folder = os.path.join(os.getcwd(), f'uploads_{task_id}')
    output = f"{os.path.join(os.getcwd(), f'uploads_{task_id}')}.zip"

    if not os.path.exists(upload_folder):
        os.makedirs(upload_folder)

    # Start the download process in a new thread
    threading.Thread(target=download_audio, args=(task_id, playlist_link, upload_folder, output)).start()

    return jsonify({"task_id": task_id})

@app.route('/download_list_v', methods=["POST"])
def download_list_v():
    task_id = str(uuid.uuid4())  # Generate unique task ID
    playlist_link = request.form.get('playlist_link')
    upload_folder = os.path.join(os.getcwd(), f'uploads_{task_id}')
    final_folder = os.path.join(os.getcwd(), f'playlist_final_{task_id}')
    output = f"{os.path.join(os.getcwd(), f'uploads_{task_id}')}.zip"

    if not os.path.exists(upload_folder):
        os.makedirs(upload_folder)
    if not os.path.exists(final_folder):
        os.makedirs(final_folder)

    # Start the download process in a new thread
    threading.Thread(target=download_video, args=(task_id, playlist_link, upload_folder, final_folder, output)).start()

    return jsonify({"task_id": task_id})

@app.route('/download_zip/<task_id>')
def download_zip(task_id):
    zip_file_path = os.path.join(os.getcwd(),f"uploads_{task_id}.zip")
    if not os.path.exists(zip_file_path):
        return f"{zip_file_path} File not found", 404

    return send_file(zip_file_path, as_attachment=True)


@app.route('/delete-folder', methods=['POST'])
def delete_folder():
    task_id = request.json.get('task_id')
    folder_path = os.path.join(os.getcwd(), f'uploads_{task_id}')

    try:
        shutil.rmtree(folder_path)  # Delete folder and all its contents
        return jsonify({'status': 'success', 'message': 'Folder deleted successfully!'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

if __name__ == '__main__':
    app.run(debug=True, port=5000, host='0.0.0.0')