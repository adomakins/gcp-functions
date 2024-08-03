import os
import sys
import yt_dlp
from google.cloud import storage
import re
import subprocess
import functions_framework
import json
import requests
import tempfile

def sanitize_filename(filename):
    return re.sub(r'[^\w\-_\. ]', '_', filename)

def parse_time(time_str):
    if ':' in time_str:
        minutes, seconds = map(int, time_str.split(':'))
        return minutes * 60 + seconds
    return int(time_str)

def format_time(seconds):
    return f"{seconds // 60:02d}:{seconds % 60:02d}"

def download_cookie_file(url):
    response = requests.get(url)
    if response.status_code == 200:
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
            temp_file.write(response.text)
            return temp_file.name
    else:
        raise Exception(f"Failed to download cookie file. Status code: {response.status_code}")

def process_video(url, start_time, end_time, bucket_name, cookie_file_url):
    output_file = None
    trimmed_file = None
    temp_cookie_file = None
    try:
        temp_cookie_file = download_cookie_file(cookie_file_url)

        ydl_opts = {
            'outtmpl': '/tmp/%(title)s.%(ext)s',
            'format': 'bestvideo[height<=1080][ext=mp4][vcodec^=avc]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4][vcodec^=avc]',
            'cookiefile': temp_cookie_file,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            video_title = info.get('title', 'video')
            sanitized_title = sanitize_filename(video_title)
            output_file = f"/tmp/{sanitized_title}.mp4"

        print(f'Video downloaded: {output_file}')

        start_seconds = parse_time(start_time)
        end_seconds = parse_time(end_time) if end_time else None

        print(f"start_seconds: {start_seconds}")
        print(f"end_seconds: {end_seconds}")

        if start_seconds > 0 or end_seconds:
            time_range = f"{format_time(start_seconds)} to {format_time(end_seconds)}" if end_seconds else f"{format_time(start_seconds)} to end"
            trimmed_file = f"/tmp/{sanitized_title} [Clip {time_range}].mp4"

            ffmpeg_command = ['ffmpeg', '-i', output_file, '-ss', str(start_seconds)]
            if end_seconds:
                ffmpeg_command.extend(['-to', str(end_seconds)])
            ffmpeg_command.extend(['-c', 'copy', trimmed_file])

            print(f"Trimming video with command: {' '.join(ffmpeg_command)}")
            subprocess.run(ffmpeg_command, check=True)

            print(f'Trimmed video: {trimmed_file}')
            upload_file = trimmed_file
        else:
            upload_file = output_file

        if not os.path.exists(upload_file):
            raise FileNotFoundError(f"Upload file not found: {upload_file}")

        print('Uploading to Google Cloud Storage...')
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(os.path.basename(upload_file))

        with open(upload_file, 'rb') as file:
            blob.upload_from_file(file)

        public_url = blob.public_url

        client_response = {
            'public_url': public_url,
            'file_name': os.path.basename(upload_file)
        }

        return (client_response, 200)

    except Exception as error:
        print(f'Detailed error: {error}', file=sys.stderr)
        print(f'Error type: {type(error)}', file=sys.stderr)
        print('Traceback:', file=sys.stderr)
        import traceback
        traceback.print_exc()

        return (str(error), 500)

    finally:
        for file in [output_file, trimmed_file]:
            if file and os.path.exists(file):
                os.remove(file)
                print(f'Cleaned up local file: {file}')
        if temp_cookie_file and os.path.exists(temp_cookie_file):
            os.remove(temp_cookie_file)
            print(f'Cleaned up temporary cookie file: {temp_cookie_file}')

@functions_framework.http
def main(request):

    print("Received headers:")
    for key, value in request.headers.items():
        print(f"{key}: {value}")

    url = request.headers.get('video-url')
    start_time = request.headers.get('start-time', '0:00')
    end_time = request.headers.get('end-time')
    bucket_name = 'youtube-clips'
    cookie_file_url = request.headers.get('cookie-file')  # This should be the URL to the cookie file

    print(f"video-url: {url}")
    print(f"cookie-file: {cookie_file_url}")
    print(f"cookie-file: {request.headers.get('cookie_file')}")

    if not url:
        return ('Missing video URL', 400)

    if not cookie_file_url:
        return ('Missing cookie file URL', 400)

    return process_video(url, start_time, end_time, bucket_name, cookie_file_url)
