"""Minimal native messaging launcher. Never accepts commands, file paths or URLs."""
import json,struct,subprocess,sys,time,urllib.request
from pathlib import Path

def main():
    header=sys.stdin.buffer.read(4)
    if len(header)!=4:return 1
    length=struct.unpack('<I',header)[0]
    if not 0<length<=4096:return 1
    message=json.loads(sys.stdin.buffer.read(length))
    if message!={'action':'open'}:return 1
    executable=Path(sys.executable).with_name('StreamChromePro.exe')
    def ready():
        try:
            with urllib.request.urlopen('http://127.0.0.1:8780/api/status',timeout=1) as response:
                status=json.load(response)
            return 'version' in status and 'ffmpeg' in status
        except (OSError,ValueError):return False
    if not ready():
        subprocess.Popen([str(executable),'--background'],creationflags=subprocess.CREATE_NO_WINDOW,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    deadline=time.monotonic()+20
    while time.monotonic()<deadline and not ready():time.sleep(.2)
    result=json.dumps({'ok':ready()}).encode()
    sys.stdout.buffer.write(struct.pack('<I',len(result))+result);sys.stdout.buffer.flush()
    return 0
if __name__=='__main__':raise SystemExit(main())
