#!/usr/bin/env python3
"""Измеряет скорость скачивания по десяти последовательным HTTP-запросам."""

import argparse
from http.client import HTTPException
import sys
from time import perf_counter
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


REQUEST_COUNT = 10
CHUNK_SIZE = 64 * 1024
IO_TIMEOUT = 30


def download(request: Request) -> tuple[int, float]:
    started = perf_counter()
    with urlopen(request, timeout=IO_TIMEOUT) as response:
        if response.status != 200:
            raise ValueError(f"ожидался полный ответ HTTP 200, получен {response.status}")

        byte_count = 0
        while chunk := response.read(CHUNK_SIZE):
            byte_count += len(chunk)

        # При чтении блоками EOF может наступить раньше заявленного размера.
        expected = response.getheader("Content-Length")
        if expected is not None and not response.getheader("Transfer-Encoding"):
            if byte_count != int(expected):
                raise ValueError(f"ответ оборвался: получено {byte_count} из {expected} байт")

    return byte_count, perf_counter() - started


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", metavar="URL", help="HTTP(S)-адрес файла")
    args = parser.parse_args()
    try:
        url = urlsplit(args.url)
        if url.scheme not in ("http", "https") or not url.hostname:
            raise ValueError
    except ValueError:
        parser.error("укажи полный URL, начинающийся с http:// или https://")

    request = Request(args.url, headers={"Accept-Encoding": "identity"}, method="GET")
    total_bytes = 0
    total_seconds = 0.0

    for index in range(1, REQUEST_COUNT + 1):
        try:
            byte_count, seconds = download(request)
        except HTTPError as error:
            error.close()
            print(f"Запрос {index}/{REQUEST_COUNT}: HTTP {error.code}.", file=sys.stderr)
            return 1
        except (OSError, HTTPException, ValueError) as error:
            print(f"Запрос {index}/{REQUEST_COUNT}: {error}", file=sys.stderr)
            return 1
        total_bytes += byte_count
        total_seconds += seconds

    print(f"Запросов выполнено:     {REQUEST_COUNT}")
    print(f"Среднее время запроса: {total_seconds / REQUEST_COUNT * 1000:.2f} мс")
    print(f"Скачано всего:         {total_bytes:,} байт".replace(",", " "))
    print(f"Скорость скачивания:   {total_bytes * 8 / total_seconds / 1_000_000:.2f} Мбит/с")
    return 0


if __name__ == "__main__":
    sys.exit(main())
