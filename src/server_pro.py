import argparse
from collections import OrderedDict
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
import json
import math
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import threading
from urllib.parse import urlparse, parse_qs, unquote
import webbrowser
import urllib.request

from process_guard import attach_to_server
from subtitles import SubtitleService, ProviderError, load_settings, http_json, http_bytes, to_vtt, guess_search

class HTTPServer(ThreadingHTTPServer):
    allow_reuse_address = False


HOST, PORT = '127.0.0.1', 8780
FFMPEG_BIN = r'C:\Program Files\FFmpeg\bin\ffmpeg.exe'
FFPROBE_BIN = r'C:\Program Files\FFmpeg\bin\ffprobe.exe'
if not os.path.isfile(FFMPEG_BIN):
    FFMPEG_BIN = shutil.which('ffmpeg') or 'ffmpeg'
if not os.path.isfile(FFPROBE_BIN):
    FFPROBE_BIN = shutil.which('ffprobe') or 'ffprobe'
NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
VIDEO_EXTENSIONS = {'.mp4', '.mkv', '.avi', '.mov', '.m4v', '.webm', '.ts', '.m2ts', '.mpg', '.mpeg', '.wmv'}
LOCAL_FILES = OrderedDict()
PROBE_CACHE = OrderedDict()
LOCAL_LOCK = threading.Lock()
DIALOG_LOCK = threading.Lock()
LANGUAGE_NAMES = {'por':'Portuguese', 'pob':'Portuguese (Brazil)', 'eng':'English', 'jpn':'Japanese', 'spa':'Spanish', 'fre':'French', 'ger':'German', 'ita':'Italian'}
try:
    SUBTITLES = SubtitleService(load_settings())
except (ValueError, OSError):
    print('Could not read the protected settings. Configure the keys again in the interface.')
    SUBTITLES = SubtitleService({})


def find_application(name, folders):
    for folder in folders:
        path = os.path.expandvars(folder)
        if os.path.isfile(path):
            return path
    return shutil.which(name)


def find_chrome():
    return find_application('chrome', [r'%ProgramFiles%\Google\Chrome\Application\chrome.exe', r'%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe', r'%LocalAppData%\Google\Chrome\Application\chrome.exe'])


def find_vlc():
    return find_application('vlc', [r'%ProgramFiles%\VideoLAN\VLC\vlc.exe', r'%ProgramFiles(x86)%\VideoLAN\VLC\vlc.exe'])


def normalize_url(raw):
    value = raw.strip()
    return 'https://' + value[len('stremio://'):] if value.startswith('stremio://') else value


def resolve_target_url(raw):
    value = normalize_url(raw)
    if value.startswith('local:'):
        with LOCAL_LOCK:
            path = LOCAL_FILES.get(value[6:])
        if not path or not os.path.isfile(path):
            raise ValueError('Local file unavailable. Use Open video from PC again.')
        return path
    parsed = urlparse(value)
    if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('Paste an HTTP/HTTPS link or use Open video from PC.')
    return value


def choose_local_video():
    # Tk owns its widgets on this request thread; no global Tk instance is shared.
    import tkinter
    from tkinter import filedialog
    with DIALOG_LOCK:
        root = tkinter.Tk()
        root.withdraw()
        icon_file = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent.parent)) / 'assets' / 'app.ico'
        if icon_file.exists():
            root.iconbitmap(str(icon_file))
        root.attributes('-topmost', True)
        try:
            return filedialog.askopenfilename(parent=root, title='Open video in StreamChromePro', filetypes=[('Videos', ' '.join('*' + extension for extension in sorted(VIDEO_EXTENSIONS))), ('All files', '*.*')])
        finally:
            root.destroy()


def probe_media(source):
    with LOCAL_LOCK:
        if source in PROBE_CACHE:
            return PROBE_CACHE[source]
    try:
        result = subprocess.run([FFPROBE_BIN, '-v', 'error', '-show_entries', 'format=duration:stream=index,codec_name,codec_type,width,height:stream_tags=language,title', '-of', 'json', source], stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=25, creationflags=NO_WINDOW)
    except FileNotFoundError:
        raise ValueError('FFprobe not found. Install FFmpeg to play videos.') from None
    except subprocess.TimeoutExpired:
        raise ValueError('The video took too long to respond. Check the file or connection and try again.') from None
    if result.returncode:
        raise ValueError('Could not read the video. Check that the file or link is valid.')
    data = json.loads(result.stdout)
    tracks = []
    video_codec = None
    width = height = 0
    for stream in data.get('streams', []):
        if stream.get('codec_type') == 'video' and video_codec is None:
            video_codec = stream.get('codec_name')
            width, height = stream.get('width', 0), stream.get('height', 0)
        if stream.get('codec_type') == 'audio':
            tags = stream.get('tags', {})
            lang = tags.get('language', 'und')
            title = tags.get('title', '')
            tracks.append({'index': stream['index'], 'label': f"{LANGUAGE_NAMES.get(lang, lang.upper())} ({stream.get('codec_name', '').upper()}) {title}".strip()})
    try:
        duration = float(data.get('format', {}).get('duration', 0))
        if not math.isfinite(duration):
            duration = 0
    except (ValueError, TypeError):
        duration = 0
    metadata = {'duration': duration, 'audio_tracks': tracks, 'video_codec': video_codec, 'width': width, 'height': height}
    if not video_codec:
        raise ValueError('The file does not contain a video track.')
    with LOCAL_LOCK:
        PROBE_CACHE[source] = metadata
        while len(PROBE_CACHE) > 64:
            PROBE_CACHE.popitem(last=False)
    return metadata


def fetch_stremio_subtitles(raw):
    match = re.search(r'tt\d{7,10}(?::\d+:\d+)?', unquote(raw))
    if not match:
        return []
    video_id = match.group()
    kind = 'series' if ':' in video_id else 'movie'
    try:
        data = http_json(f'https://opensubtitles-v3.strem.io/subtitles/{kind}/{video_id}.json')
        return [{'url': item['url'], 'lang': item.get('lang', ''), 'label': LANGUAGE_NAMES.get(item.get('lang'), item.get('lang', '').upper())} for item in data.get('subtitles', []) if item.get('url', '').startswith('https://')]
    except ProviderError:
        return []


def convert_srt_to_vtt(content):
    return to_vtt(content)


def build_stream_command(source, metadata, seek, audio='', compatibility=False):
    cmd = [FFMPEG_BIN, '-nostdin', '-hide_banner', '-loglevel', 'error', '-ss', str(seek), '-i', source, '-map', '0:v:0']
    if audio:
        if not audio.isdigit() or int(audio) not in [item['index'] for item in metadata['audio_tracks']]:
            raise ValueError('Invalid audio track.')
        cmd += ['-map', '0:' + audio]
    else:
        cmd += ['-map', '0:a:0?']
    if metadata['video_codec'] in ('h264', 'hevc', 'av1') and not compatibility:
        # Preserve the same pre-roll for audio and copied video after input seeking.
        cmd.insert(cmd.index('-ss'), '-noaccurate_seek')
        cmd += ['-c:v', 'copy']
        if metadata['video_codec'] == 'hevc':
            cmd += ['-tag:v', 'hvc1']
    else:
        cmd += ['-c:v', 'libx264', '-preset', 'veryfast', '-crf', '21', '-pix_fmt', 'yuv420p']
    cmd += ['-c:a', 'aac', '-b:a', '192k', '-ac', '2', '-sn', '-dn', '-map_chapters', '-1', '-avoid_negative_ts', 'make_zero', '-f', 'mp4', '-movflags', 'frag_keyframe+empty_moov+default_base_moof', 'pipe:1']
    return cmd


def seek_start(source, requested):
    if requested <= 0:
        return 0.0
    result = subprocess.run([FFPROBE_BIN, '-v', 'error', '-select_streams', 'v:0', '-read_intervals', f'{requested}%+#1', '-show_packets', '-show_entries', 'packet=pts_time', '-of', 'json', source], stdin=subprocess.DEVNULL, capture_output=True, text=True, encoding='utf-8', timeout=15, creationflags=NO_WINDOW)
    if result.returncode:
        raise ValueError('Could not locate the video position. Try again.')
    packets = json.loads(result.stdout).get('packets', [])
    if not packets or 'pts_time' not in packets[0]:
        raise ValueError('The file did not report the frame timestamp. Try another video position.')
    start = float(packets[0]['pts_time'])
    if not math.isfinite(start):
        raise ValueError('The file reported an invalid video timestamp.')
    return max(0.0, start)


class StreamProHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        # Query strings can contain private video links; keep them out of logs.
        return

    def allowed(self, mutation=False):
        port = self.server.server_address[1]
        origins = {f'http://127.0.0.1:{port}', f'http://localhost:{port}'}
        hosts = {f'127.0.0.1:{port}', f'localhost:{port}'}
        origin = self.headers.get('Origin')
        if self.headers.get('Host') not in hosts or (origin and origin not in origins) or (self.headers.get('Sec-Fetch-Site') == 'cross-site' and urlparse(self.path).path not in ('/', '/index.html')):
            self.send_json({'error': 'Access is allowed only through the local application interface.'}, 403)
            return False
        if mutation and self.headers.get('X-StreamChrome') != '1':
            self.send_json({'error': 'Invalid local request.'}, 403)
            return False
        return True

    def do_GET(self):
        if not self.allowed():
            return
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        try:
            if parsed.path in ('/', '/index.html'):
                self.serve_asset()
            elif parsed.path in ('/player_helpers.js', '/player.css', '/layouts.css', '/appearance.js', '/i18n.js','/presentation.js'):
                self.serve_asset(parsed.path[1:])
            elif parsed.path == '/api/settings':
                self.send_json(SUBTITLES.status())
            elif parsed.path == '/api/status':
                self.send_json({'version': '2.4', 'ffmpeg': bool(shutil.which(FFMPEG_BIN)), 'ffprobe': bool(shutil.which(FFPROBE_BIN))})
            elif parsed.path == '/api/inspect':
                raw = query.get('url', [''])[0]
                source = resolve_target_url(raw)
                metadata = probe_media(source)
                if raw.startswith('local:'):
                    filename = Path(source).name
                else:
                    filename = parse_qs(urlparse(raw).query).get('torrent_name', [unquote(Path(urlparse(raw).path).name) or 'Video por link'])[0]
                self.send_json({**metadata, 'filename': filename, 'subtitles': [] if raw.startswith('local:') else fetch_stremio_subtitles(raw), 'suggestion': guess_search(filename)})
            elif parsed.path == '/stream':
                self.handle_stream(query)
            elif parsed.path == '/api/subtitles/vtt':
                self.send_bytes(SUBTITLES.download(query.get('id', [''])[0]).encode('utf-8'), 'text/vtt; charset=utf-8')
            elif parsed.path == '/api/vtt':
                self.send_bytes(to_vtt(http_bytes(query.get('url', [''])[0])).encode('utf-8'), 'text/vtt; charset=utf-8')
            else:
                self.send_json({'error': 'Resource not found.'}, 404)
        except ValueError as error:
            self.send_json({'error': str(error)}, 400)
        except ProviderError as error:
            self.send_json({'error': str(error)}, 502)
        except (OSError, json.JSONDecodeError):
            self.send_json({'error': 'Could not complete the operation. Check the file and try again.'}, 500)

    def do_POST(self):
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 65536 or self.headers.get_content_type() != 'application/json':
                raise ValueError('Send a valid JSON request.')
            self.connection.settimeout(20)
            raw_body = self.rfile.read(length)
            if not self.allowed(mutation=True):
                return
            data = json.loads(raw_body)
            if not isinstance(data, dict):
                raise ValueError('Invalid data.')
            path = urlparse(self.path).path
            if path == '/api/shutdown':
                self.send_json({'status': 'stopping'})
                threading.Thread(target=self.server.shutdown, daemon=True).start()
            elif path == '/api/local/open':
                selected = choose_local_video()
                if not selected:
                    self.send_json({'cancelled': True})
                    return
                selected = Path(selected).resolve()
                if not selected.is_file() or selected.suffix.lower() not in VIDEO_EXTENSIONS:
                    raise ValueError('Select a supported video file.')
                token = secrets.token_urlsafe(24)
                with LOCAL_LOCK:
                    LOCAL_FILES[token] = str(selected)
                    while len(LOCAL_FILES) > 64:
                        LOCAL_FILES.popitem(last=False)
                self.send_json({'source': 'local:' + token, 'filename': selected.name, 'suggestion': guess_search(selected.name)})
            elif path == '/api/playback':
                source = resolve_target_url(str(data.get('url', '')))
                requested = float(data.get('t', 0))
                if not math.isfinite(requested) or requested < 0:
                    raise ValueError('Invalid playback position.')
                metadata = probe_media(source)
                copied = metadata['video_codec'] in ('h264', 'hevc', 'av1') and not data.get('compatibility', False)
                self.send_json({'start': seek_start(source, requested) if copied else requested})
            elif path == '/api/settings':
                self.send_json(SUBTITLES.configure(data))
            elif path == '/api/subtitles/search':
                self.send_json(SUBTITLES.search(data))
            elif path == '/api/vlc':
                source = resolve_target_url(str(data.get('url', '')))
                vlc = find_vlc()
                if not vlc:
                    raise ValueError('VLC was not found on this computer.')
                seek = float(data.get('t', 0))
                if not math.isfinite(seek) or seek < 0:
                    raise ValueError('Invalid playback position.')
                subprocess.Popen([vlc, source, f'--start-time={int(seek)}'], stdin=subprocess.DEVNULL)
                self.send_json({'status': 'ok'})
            else:
                self.send_json({'error': 'Resource not found.'}, 404)
        except (ValueError, TypeError) as error:
            self.send_json({'error': str(error)}, 400)
        except ProviderError as error:
            self.send_json({'error': str(error)}, 502)
        except Exception:
            self.send_json({'error': 'Could not complete the local operation. Try again.'}, 500)

    def serve_asset(self, filename='index.html'):
        bundle = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent.parent))
        candidates = [Path(sys.executable).parent / 'assets' / filename, bundle / 'assets' / filename, Path(__file__).resolve().parent.parent / 'assets' / filename] if getattr(sys, 'frozen', False) else [bundle / 'assets' / filename]
        for path in candidates:
            if path.is_file():
                self.send_bytes(path.read_bytes(), ('text/javascript' if filename.endswith('.js') else 'text/css' if filename.endswith('.css') else 'text/html') + '; charset=utf-8')
                return
        self.send_json({'error': 'assets/index.html was not found.'}, 404)

    def send_bytes(self, content, content_type, code=200):
        self.send_response(code)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(content)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.end_headers()
        try:
            self.wfile.write(content)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass

    def send_json(self, data, code=200):
        self.send_bytes(json.dumps(data, ensure_ascii=False).encode('utf-8'), 'application/json; charset=utf-8', code)

    def handle_stream(self, query):
        seek = float(query.get('t', ['0'])[0])
        if not math.isfinite(seek) or seek < 0:
            raise ValueError('Invalid playback position.')
        source = resolve_target_url(query.get('url', [''])[0])
        metadata = probe_media(source)
        cmd = build_stream_command(source, metadata, seek, query.get('a', [''])[0], query.get('compat', ['0'])[0] == '1')
        with tempfile.TemporaryFile() as errors:
            try:
                process = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=errors, creationflags=NO_WINDOW)
                attach_to_server(process)
            except FileNotFoundError:
                raise ValueError('FFmpeg not found. Install FFmpeg to play videos.') from None
            try:
                chunk = process.stdout.read(64 * 1024)
                if not chunk:
                    raise ValueError('FFmpeg could not convert this video. Try opening it in VLC.')
                self.send_response(200)
                self.send_header('Content-Type', 'video/mp4')
                self.send_header('Cache-Control', 'no-store')
                self.send_header('Connection', 'close')
                self.end_headers()
                while chunk:
                    self.wfile.write(chunk)
                    self.wfile.flush()
                    chunk = process.stdout.read(64 * 1024)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass
            finally:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
                process.stdout.close()


def open_browser(port=PORT):
    url = f'http://{HOST}:{port}'
    chrome = find_chrome()
    if chrome:
        subprocess.Popen([chrome, url])
    else:
        webbrowser.open(url)


def start_tray(server, port):
    import pystray
    from PIL import Image, ImageDraw
    icon_path = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent.parent)) / 'assets' / 'app.ico'
    image = Image.open(icon_path)
    def stop_player(icon, item):
        threading.Thread(target=server.shutdown, daemon=True).start()
    icon = pystray.Icon('StreamChromePro', image, 'StreamChrome PRO', menu=pystray.Menu(
        pystray.MenuItem('Open player / Abrir player', lambda icon, item: open_browser(port), default=True),
        pystray.MenuItem('Exit / Sair', stop_player),
    ))
    threading.Thread(target=icon.run, daemon=True).start()
    return icon


def main():
    if os.name == 'nt':
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('OhCato.StreamChromePro')
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=PORT)
    parser.add_argument('--no-browser', action='store_true')
    parser.add_argument('--background', action='store_true')
    args = parser.parse_args()
    try:
        server = HTTPServer((HOST, args.port), StreamProHandler)
    except OSError:
        try:
            with urllib.request.urlopen(f'http://{HOST}:{args.port}/api/status', timeout=2) as response:
                status = json.load(response)
            if 'version' in status and 'ffmpeg' in status and 'ffprobe' in status:
                if not args.no_browser and not args.background:
                    open_browser(args.port)
                return 0
        except (OSError, ValueError):
            pass
        print(f'Port {args.port} is in use. Close the previous version and try again.')
        return 1
    print(f'StreamChrome PRO 2.4: http://{HOST}:{args.port}')
    print('Local videos, SubDL and OpenSubtitles.')
    tray = start_tray(server, args.port) if not args.no_browser else None
    if not args.no_browser and not args.background:
        threading.Timer(0.5, open_browser, args=(args.port,)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        if tray:
            tray.stop()
        server.server_close()
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
