import concurrent.futures
import http.client
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import server_pro as server

class ServerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = server.HTTPServer(('127.0.0.1', 0), server.StreamProHandler)
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.thread.join()

    def request(self, path, data=None, extra_headers=None):
        conn = http.client.HTTPConnection(*self.httpd.server_address, timeout=4)
        headers = {'X-StreamChrome': '1', 'Content-Type': 'application/json'}
        headers.update(extra_headers or {})
        conn.request('POST' if data is not None else 'GET', path, json.dumps(data) if data is not None else None, headers)
        response = conn.getresponse()
        result = response.status, response.read()
        conn.close()
        return result

    def test_local_selection_registers_token_and_never_sends_full_path(self):
        with tempfile.TemporaryDirectory() as directory:
            video = Path(directory) / 'Movie.2024.mkv'
            video.write_bytes(b'test')
            with patch.object(server, 'choose_local_video', return_value=str(video)):
                status, body = self.request('/api/local/open', {})
            self.assertEqual(status, 200)
            data = json.loads(body)
            self.assertEqual(data['filename'], video.name)
            self.assertNotIn(directory.encode(), body)
            self.assertEqual(server.resolve_target_url(data['source']), str(video.resolve()))

    def test_unregistered_local_paths_are_rejected(self):
        with self.assertRaises(ValueError):
            server.resolve_target_url('file:///C:/private.mkv')
        with self.assertRaises(ValueError):
            server.resolve_target_url('C:\\private.mkv')
        with self.assertRaises(ValueError):
            server.resolve_target_url('local:missing-token')

    def test_websites_cannot_trigger_local_dialog(self):
        with patch.object(server, 'choose_local_video') as dialog:
            status, _ = self.request('/api/local/open', {}, {'Origin': 'https://example.org'})
        self.assertEqual(status, 403)
        dialog.assert_not_called()

    def test_top_level_navigation_can_open_player_but_not_private_apis(self):
        status, body = self.request('/', extra_headers={'Sec-Fetch-Site': 'cross-site'})
        self.assertEqual(status, 200)
        self.assertIn(b'StreamChrome', body)
        status, _ = self.request('/api/settings', extra_headers={'Sec-Fetch-Site': 'cross-site'})
        self.assertEqual(status, 403)

    def test_host_guard_rejects_dns_rebinding(self):
        status, _ = self.request('/api/settings', extra_headers={'Host': 'attacker.example'})
        self.assertEqual(status, 403)

    def test_settings_response_contains_no_secret(self):
        status, body = self.request('/api/settings')
        self.assertEqual(status, 200)
        self.assertEqual(set(json.loads(body)), {'subdl', 'opensubtitles', 'opensubtitles_login'})

    def test_cancelled_dialog_is_not_a_failure(self):
        with patch.object(server, 'choose_local_video', return_value=''):
            status, body = self.request('/api/local/open', {})
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(body)['cancelled'])

    def test_long_running_request_does_not_block_other_requests(self):
        entered = threading.Event()
        release = threading.Event()
        def slow_search(data):
            entered.set()
            release.wait(3)
            return {'subtitles': [], 'warnings': []}
        with patch.object(server.SUBTITLES, 'search', side_effect=slow_search), concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            job = pool.submit(self.request, '/api/subtitles/search', {'title': 'Dune'})
            self.assertTrue(entered.wait(1))
            start = time.monotonic()
            try:
                self.assertEqual(self.request('/api/settings')[0], 200)
                self.assertLess(time.monotonic() - start, 1)
            finally:
                release.set()
            self.assertEqual(job.result()[0], 200)

    def test_original_hevc_is_not_reencoded_by_default(self):
        metadata = {'video_codec':'hevc', 'audio_tracks':[]}
        command = server.build_stream_command('movie.mkv', metadata, 0)
        self.assertEqual(command[command.index('-c:v') + 1], 'copy')
        self.assertIn('hvc1', command)
        fallback = server.build_stream_command('movie.mkv', metadata, 0, compatibility=True)
        self.assertEqual(fallback[fallback.index('-c:v') + 1], 'libx264')

    def test_invalid_seek_is_rejected(self):
        status, _ = self.request('/stream?url=https%3A%2F%2Fexample.org%2Fmovie.mkv&t=nan')
        self.assertEqual(status, 400)

if __name__ == '__main__':
    unittest.main()
