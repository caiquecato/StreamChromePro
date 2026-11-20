import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import server_pro as app

class SyncTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.source = Path(cls.tmp.name) / 'source.mkv'
        subprocess.run([app.FFMPEG_BIN,'-y','-v','error','-f','lavfi','-i','testsrc2=size=160x90:rate=24','-f','lavfi','-i','sine=frequency=500:sample_rate=48000','-t','12','-c:v','libx264','-preset','ultrafast','-g','240','-bf','2','-c:a','aac',str(cls.source)],check=True,capture_output=True,timeout=30,creationflags=app.NO_WINDOW)
        cls.metadata=app.probe_media(str(cls.source))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_seek_does_not_stretch_first_audio_packet_to_seconds(self):
        target=Path(self.tmp.name)/'output.mp4'
        command=app.build_stream_command(str(self.source),self.metadata,5.3)
        command.insert(1,'-y')
        command[-1:]=['-t','4',str(target)]
        subprocess.run(command,check=True,capture_output=True,timeout=20,creationflags=app.NO_WINDOW)
        result=subprocess.run([app.FFPROBE_BIN,'-v','error','-select_streams','a:0','-show_packets','-show_entries','packet=duration_time','-of','json',str(target)],check=True,capture_output=True,text=True,timeout=20,creationflags=app.NO_WINDOW)
        packets=json.loads(result.stdout)['packets']
        self.assertTrue(packets)
        self.assertLess(float(packets[0]['duration_time']),0.15)

    def test_seek_reports_actual_keyframe_for_subtitle_clock(self):
        start=app.seek_start(str(self.source),5.3)
        self.assertAlmostEqual(start,0,delta=.05)

if __name__ == '__main__':
    unittest.main()
