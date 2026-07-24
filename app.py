import os
import re
import uuid
import time
import logging
import threading
from urllib.parse import urlparse

import requests
import yt_dlp
from flask import Flask, request, jsonify, render_template, send_from_directory, Response, session

# ============== CONFIGURATION ==============
DOWNLOADS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "downloads")
os.makedirs(DOWNLOADS_DIR, exist_ok=True)

# ============== LOGGING SETUP ==============
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ============== FLASK SERVER SETUP ==============
app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = "alone_music_secret_key_123"

# ============== CLEANUP CRON (BACKGROUND FILE PURGE) ==============
def file_cleanup_loop():
    while True:
        try:
            time.sleep(300)
            now = time.time()
            for filename in os.listdir(DOWNLOADS_DIR):
                filepath = os.path.join(DOWNLOADS_DIR, filename)
                if os.path.isfile(filepath) and os.stat(filepath).st_mtime < now - 600:
                    try:
                        os.remove(filepath)
                        logger.info(f"Purged expired download file: {filename}")
                    except Exception:
                        pass
        except Exception as e:
            logger.error(f"Cleanup thread error: {e}")

cleanup_thread = threading.Thread(target=file_cleanup_loop, daemon=True)
cleanup_thread.start()

# ============== ALONEMUSIC / YOUTUBE EXTRACTOR ROUTES ==============

def get_youtube_file_path(video_id, ext):
    yt_dir = os.path.join(DOWNLOADS_DIR, "youtube.com")
    os.makedirs(yt_dir, exist_ok=True)
    return os.path.join(yt_dir, f"{video_id}.{ext}")

def download_youtube_background(video_url, video_id, dl_type):
    ext = 'mp3' if dl_type == 'audio' else 'mp4'
    local_path = get_youtube_file_path(video_id, ext)
    if os.path.exists(local_path):
        return
    temp_path = local_path + ".tmp"
    
    if dl_type == 'audio':
        ydl_opts = {
            'quiet': True,
            'outtmpl': temp_path,
            'format': 'bestaudio/best',
        }
    else:
        ydl_opts = {
            'quiet': True,
            'outtmpl': temp_path,
            'format': 'best[height<=360][ext=mp4]/best[height<=360]/best',
        }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])
        if os.path.exists(temp_path):
            os.rename(temp_path, local_path)
            logger.info(f"Background pre-cache success: {local_path}")
    except Exception as e:
        logger.error(f"Background download error: {e}")
        if os.path.exists(temp_path):
            try: os.remove(temp_path)
            except: pass

@app.route('/')
@app.route('/ayush_music')
@app.route('/alone_music')
def ayush_music_dashboard():
    api_key = session.get('api_key', '')
    return render_template('ayush_music.html', api_key=api_key)

@app.route('/generate_free_key', methods=['POST'])
def generate_free_key():
    session['api_key'] = "AM-KEY-" + str(uuid.uuid4())[:8].upper()
    return jsonify({'success': True, 'api_key': session['api_key']})

@app.route('/remove_api_key', methods=['POST'])
def remove_api_key():
    session.pop('api_key', None)
    return jsonify({'success': True})

@app.route('/search')
def search_youtube():
    query = request.args.get('query', '').strip()
    if not query:
        return jsonify({'result': []})
        
    ydl_opts = {
        'quiet': True,
        'extract_flat': True,
        'skip_download': True,
    }
    
    try:
        is_url = re.match(r'^https?://', query) or 'youtube.com' in query or 'youtu.be' in query
        search_query = query if is_url else f"ytsearch10:{query}"
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            res = ydl.extract_info(search_query, download=False)
            results = []
            
            entries = []
            if 'entries' in res:
                entries = res['entries']
            else:
                entries = [res]
                
            for entry in entries:
                if not entry:
                    continue
                duration_sec = entry.get('duration')
                duration_str = 'N/A'
                if duration_sec is not None:
                    mins = int(duration_sec // 60)
                    secs = int(duration_sec % 60)
                    duration_str = f"{mins}:{secs:02d}"
                
                thumbnails = entry.get('thumbnails', [])
                thumb_url = ''
                if thumbnails:
                    thumb_url = thumbnails[-1].get('url', '')
                if not thumb_url:
                    video_id = entry.get('id')
                    if video_id:
                        thumb_url = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
                
                results.append({
                    'id': entry.get('id'),
                    'title': entry.get('title'),
                    'duration': duration_str,
                    'thumbnails': [{'url': thumb_url}] if thumb_url else []
                })
            return jsonify({'result': results})
    except Exception as e:
        logger.error(f"Search error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/download')
def download_api():
    query = request.args.get('query', '').strip()
    dl_type = request.args.get('dl_type', 'audio').strip()
    prefetch = request.args.get('prefetch', 'false').lower() == 'true'
    
    if not query:
        return jsonify({'error': 'Missing query'}), 400
        
    video_id = None
    patterns = [
        r'youtu\.be/([^?#/]+)',
        r'watch\?v=([^&#/]+)',
        r'embed/([^?#/]+)',
        r'v/([^?#/]+)',
    ]
    for p in patterns:
        m = re.search(p, query)
        if m:
            video_id = m.group(1)
            break
            
    if not video_id:
        try:
            ydl_opts = {'quiet': True, 'extract_flat': True, 'skip_download': True}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                res = ydl.extract_info(f"ytsearch1:{query}", download=False)
                if 'entries' in res and res['entries']:
                    video_id = res['entries'][0]['id']
        except Exception as e:
            return jsonify({'error': str(e)}), 500
            
    if not video_id:
        return jsonify({'error': 'Video not found'}), 404
        
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    
    if prefetch:
        threading.Thread(
            target=download_youtube_background,
            args=(video_url, video_id, dl_type),
            daemon=True
        ).start()
        return jsonify({'success': True, 'message': 'Prefetch started'})
        
    ext = 'mp3' if dl_type == 'audio' else 'mp4'
    apikey = session.get('api_key', '')
    if apikey:
        stream_url = f"/downloads/{apikey}/youtube.com/{video_id}.{ext}"
    else:
        stream_url = f"/downloads/youtube.com/{video_id}.{ext}"
        
    return jsonify({'success': True, 'stream_url': stream_url})

@app.route('/downloads/<apikey>/youtube.com/<video_id>.<ext>')
@app.route('/downloads/youtube.com/<video_id>.<ext>')
def stream_youtube(video_id, ext, apikey=None):
    quality = request.args.get('quality', '360')
    download_as_attachment = request.args.get('download', 'false').lower() == 'true'
    
    local_path = get_youtube_file_path(video_id, ext)
    if os.path.exists(local_path):
        return send_from_directory(os.path.join(DOWNLOADS_DIR, "youtube.com"), f"{video_id}.{ext}", as_attachment=download_as_attachment)
        
    if ext == 'mp3':
        ydl_opts = {
            'quiet': True,
            'format': 'bestaudio/best',
        }
    else:
        ydl_opts = {
            'quiet': True,
            'format': f'best[height<={quality}][ext=mp4]/best[height<={quality}]/best',
        }
        
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
            stream_url = info.get('url')
            if not stream_url:
                return jsonify({'error': 'Failed to obtain direct stream URL'}), 500
                
            req_headers = {}
            range_header = request.headers.get('Range')
            if range_header:
                req_headers['Range'] = range_header
                
            res = requests.get(stream_url, headers=req_headers, stream=True, timeout=15)
            
            resp_headers = {}
            for h in ['Content-Type', 'Content-Length', 'Content-Range', 'Accept-Ranges']:
                if h in res.headers:
                    resp_headers[h] = res.headers[h]
                    
            if download_as_attachment:
                title = info.get('title', 'video')
                safe_title = "".join([c if c.isalnum() or c in '._-' else '_' for c in title])
                resp_headers['Content-Disposition'] = f'attachment; filename="{safe_title}.{ext}"'
                
            def generate():
                for chunk in res.iter_content(chunk_size=40960):
                    yield chunk
                    
            return Response(generate(), status=res.status_code, headers=resp_headers)
    except Exception as e:
        logger.error(f"Stream error: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
