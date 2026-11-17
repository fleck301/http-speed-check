from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import subprocess
import sys
from threading import Thread
import unittest


SCRIPT = Path(__file__).with_name("speed_test.py")


class SpeedTest(unittest.TestCase):
    def test_downloads_and_detects_truncated_response(self):
        payload = b"x" * 100_000
        received = []

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                received.append(self.path)
                self.send_response(200)
                length = len(payload) + int(self.path == "/truncated")
                self.send_header("Content-Length", str(length))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, format, *args):
                pass

        with HTTPServer(("127.0.0.1", 0), Handler) as server:
            worker = Thread(target=server.serve_forever, daemon=True)
            worker.start()
            try:
                url = f"http://127.0.0.1:{server.server_port}"
                complete = subprocess.run(
                    [sys.executable, str(SCRIPT), f"{url}/file"],
                    capture_output=True, text=True, timeout=10,
                )
                truncated = subprocess.run(
                    [sys.executable, str(SCRIPT), f"{url}/truncated"],
                    capture_output=True, text=True, timeout=10,
                )
            finally:
                server.shutdown()
                worker.join()

        self.assertEqual(received, ["/file"] * 10 + ["/truncated"])
        self.assertEqual(complete.returncode, 0, complete.stderr)
        self.assertIn("1 000 000 байт", complete.stdout)
        self.assertRegex(complete.stdout, r"Среднее время запроса:\s+\d+\.\d{2} мс")
        self.assertRegex(complete.stdout, r"Скорость скачивания:\s+\d+\.\d{2} Мбит/с")
        self.assertEqual(truncated.returncode, 1)
        self.assertEqual(truncated.stdout, "")
        self.assertIn("Запрос 1/10: ответ оборвался", truncated.stderr)
