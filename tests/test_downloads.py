import json,sys,tempfile,time,threading,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from downloads import DownloadService,validate_link

class DownloadTests(unittest.TestCase):
 def test_input_and_quality_validation(self):
  for value in ['file:///secret','--exec bad','https://user:password@example.org/a',None]:
   with self.assertRaises(ValueError):validate_link(value)
  self.assertEqual(validate_link(' https://example.org/a '),'https://example.org/a')
  service=DownloadService('tool','ffmpeg')
  fake=type('Result',(),{'returncode':0,'stdout':json.dumps({'title':'Movie <script>','formats':[{'height':1080,'vcodec':'h264'},{'height':720,'vcodec':'h264'},{'height':1080,'vcodec':'h264','has_drm':True}]})})()
  with patch('downloads.subprocess.run',return_value=fake):job=service.analyze('https://example.org/a')
  self.assertEqual(job['heights'],[1080,720]);self.assertEqual(job['title'],'Movie <script>')
  self.assertNotIn('url',job);self.assertNotIn('process',job)
  with self.assertRaises(ValueError):service.start(job['id'],'1080;command')
  with self.assertRaises(ValueError):service.completed_file(job['id'])
 def test_playlist_is_not_silently_downloaded(self):
  service=DownloadService('tool','ffmpeg');fake=type('Result',(),{'returncode':0,'stdout':'{"_type":"playlist","entries":[]}'})()
  with patch('downloads.subprocess.run',return_value=fake):
   with self.assertRaisesRegex(ValueError,'single video'):service.analyze('https://example.org/list')
 def test_cancel_targets_only_job_process(self):
  service=DownloadService('tool','ffmpeg');job={'id':'x','title':'Movie','duration':1,'heights':[],'state':'downloading','downloaded':0,'total':0,'speed':0,'eta':None,'error':'','process':object(),'cancel':False};service.jobs['x']=job
  with patch.object(service,'_stop') as stop:
   service.cancel('x');stop.assert_called_once_with(job['process'])
  self.assertTrue(job['cancel'])

if __name__=='__main__':unittest.main()
