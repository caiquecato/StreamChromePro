"""Local download jobs backed by the official yt-dlp executable."""
import json,os,secrets,subprocess,threading
from pathlib import Path
from urllib.parse import urlparse
from process_guard import attach_to_server

NO_WINDOW=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0

def validate_link(value):
    if not isinstance(value,str) or len(value)>8192:raise ValueError('Paste a valid HTTP/HTTPS video link.')
    parsed=urlparse(value.strip())
    if parsed.scheme not in ('http','https') or not parsed.hostname or parsed.username or parsed.password:raise ValueError('Paste a valid HTTP/HTTPS video link.')
    return value.strip()

class DownloadService:
    def __init__(self,tool,ffmpeg,destination=None):
        self.tool=str(tool);self.ffmpeg=str(Path(ffmpeg).parent)
        self.destination=Path(destination or Path.home()/'Downloads'/'StreamChromePro')
        self.jobs={};self.lock=threading.RLock()
    def command(self):
        runtime=Path(self.tool).with_name('deno.exe')
        runtime_args=['--js-runtimes','deno:'+str(runtime)] if runtime.is_file() else []
        return [self.tool]+runtime_args+['--ignore-config','--no-playlist','--playlist-end','2','--no-warnings','--no-colors','--socket-timeout','20','--retries','2','--no-exec','--ffmpeg-location',self.ffmpeg]
    def analyze(self,url):
        url=validate_link(url)
        try:
            result=subprocess.run(self.command()+['--skip-download','--dump-single-json','--',url],capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=75,creationflags=NO_WINDOW)
        except FileNotFoundError:raise ValueError('The downloader is unavailable. Update the desktop app.') from None
        except subprocess.TimeoutExpired:raise ValueError('Link analysis timed out. Try again.') from None
        if result.returncode:raise ValueError('Could not analyze this link. It may be unavailable, require sign-in, or be unsupported.')
        try:info=json.loads(result.stdout)
        except ValueError:raise ValueError('The website returned an unsupported response.') from None
        if info.get('_type') in ('playlist','multi_video') or 'entries' in info:raise ValueError('Paste a single video link instead of a playlist.')
        if info.get('is_live') or info.get('live_status')=='is_live':raise ValueError('Live streams are not available for download.')
        formats=[f for f in info.get('formats',[]) if not f.get('has_drm') and f.get('vcodec')!='none']
        if not formats and info.get('has_drm'):raise ValueError('Protected videos cannot be downloaded.')
        heights=sorted({int(f['height']) for f in formats if isinstance(f.get('height'),(int,float)) and 0<f['height']<=8640},reverse=True)
        with self.lock:
            # Do not evict an active job while pruning previous analyses.
            if len(self.jobs)>=12:
                old=next((key for key,item in self.jobs.items() if item['state'] not in ('downloading','processing')),None)
                if old is None:raise ValueError('Finish or cancel the current download first.')
                self.jobs.pop(old)
            token=secrets.token_urlsafe(24)
            self.jobs[token]={'id':token,'url':url,'title':str(info.get('title') or 'Video')[:300],'duration':info.get('duration'),'heights':heights,'state':'ready','downloaded':0,'total':0,'speed':0,'eta':None,'path':None,'process':None,'cancel':False,'error':''}
            return self.status(token)
    def status(self,token):
        with self.lock:
            job=self.jobs.get(token)
            if job is None:raise ValueError('Download expired. Analyze the link again.')
            return {key:job[key] for key in ('id','title','duration','heights','state','downloaded','total','speed','eta','error')}
    def start(self,token,quality):
        with self.lock:
            job=self.jobs.get(token)
            if job is None:raise ValueError('Analyze the link first.')
            if job['state']!='ready':raise ValueError('Analyze the link again before another download.')
            if any(j['state'] in ('downloading','processing') for j in self.jobs.values()):raise ValueError('Finish or cancel the current download first.')
            if quality!='best' and (not str(quality).isdigit() or int(quality) not in job['heights']):raise ValueError('Choose an available quality.')
            job.update(state='downloading',cancel=False,destination=self.destination)
            threading.Thread(target=self._download,args=(job,quality),daemon=True).start()
            return self.status(token)
    def _download(self,job,quality):
        folder=job['destination']/job['id'];process=None
        try:
            folder.mkdir(parents=True,exist_ok=True)
            height='' if quality=='best' else f'[height<={int(quality)}]'
            selection=f'bv*{height}+ba/b{height}'
            args=self.command()+['--newline','--progress','--progress-template','download:PROGRESS:%(progress)j','--print','after_move:FILE:%(filepath)j','--no-simulate','--windows-filenames','--no-overwrites','--merge-output-format','mkv','-f',selection,'-P',str(folder),'-o','%(title).160B [%(id)s].%(ext)s','--',job['url']]
            process=subprocess.Popen(args,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace',creationflags=NO_WINDOW)
            attach_to_server(process)
            with self.lock:job['process']=process
            if job['cancel']:self._stop(process)
            for line in process.stdout:
                with self.lock:
                    if line.startswith('PROGRESS:'):
                        try:
                            data=json.loads(line[len('PROGRESS:'):]);job.update(downloaded=data.get('downloaded_bytes') or 0,total=data.get('total_bytes') or data.get('total_bytes_estimate') or 0,speed=data.get('speed') or 0,eta=data.get('eta'))
                            if data.get('status')=='finished':job['state']='processing'
                            elif data.get('status')=='downloading':job['state']='downloading'
                        except (ValueError,TypeError):pass
                    elif line.startswith('FILE:'):
                        candidate=Path(json.loads(line[len('FILE:'):])).resolve()
                        if candidate.is_relative_to(folder.resolve()) and candidate.is_file():job['path']=candidate
            code=process.wait()
            with self.lock:
                if job['cancel']:job['state']='cancelled'
                elif code==0 and job['path']:job['state']='complete'
                else:job.update(state='failed',error='Download failed. Check the link and try again.')
        except (OSError,ValueError):
            with self.lock:job.update(state='cancelled' if job['cancel'] else 'failed',error='' if job['cancel'] else 'Download failed. Check your connection and available disk space.')
        finally:
            if process and process.poll() is None:self._stop(process)
            if process and process.stdout:process.stdout.close()
            with self.lock:job['process']=None
    def _stop(self,process):
        if process.poll() is not None:return
        if os.name=='nt':subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],capture_output=True,creationflags=NO_WINDOW)
        else:process.terminate()
    def cancel(self,token):
        with self.lock:
            job=self.jobs.get(token)
            if not job:raise ValueError('Download expired.')
            if job['state'] not in ('downloading','processing'):return self.status(token)
            job['cancel']=True;process=job['process']
        if process:self._stop(process)
        return self.status(token)
    def completed_file(self,token):
        with self.lock:
            job=self.jobs.get(token)
            if not job or job['state']!='complete' or not job['path'] or not job['path'].is_file():raise ValueError('The download is not complete.')
            return job['path']
