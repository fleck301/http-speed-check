from contextlib import redirect_stdout
from http.server import BaseHTTPRequestHandler, HTTPServer
from io import StringIO
from pathlib import Path
import subprocess
import sys
from threading import Thread
import unittest

from speed_test import print_report


SCRIPT = Path(__file__).with_name("speed_test.py")


class SpeedTest(unittest.TestCase):
    def test_report_calculates_total_mean_median_and_speed(self):
        downloads = [(1_000_000, 0.25)] * 9 + [(1_000_000, 1.75)]
        output = StringIO()
        with redirect_stdout(output):
            print_report(downloads)

        lines = output.getvalue().splitlines()
        self.assertEqual(
            [line.split()[0] for line in lines[2:12]],
            [str(index) for index in range(1, 11)],
        )
        self.assertIn("Среднее время запроса: 400.00 мс", lines)
        self.assertIn("Медиана времени:       250.00 мс", lines)
        self.assertIn("Скачано всего:         10 000 000 байт", lines)
        self.assertIn("Скорость скачивания:   20.00 Мбит/с", lines)

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
