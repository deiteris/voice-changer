import os
import json
import asyncio
import re
import tempfile

from downloader.HttpClient import HttpClient
from tqdm import tqdm
from threading import Lock
from xxhash import xxh128
from utils.hasher import compute_hash
from const import ASSETS_FILE
from Exceptions import DownloadVerificationException

import logging
logger = logging.getLogger(__name__)

lock = Lock()

try:
    with open(ASSETS_FILE, encoding='utf-8') as f:
        files = json.load(f)
    if not isinstance(files, dict):
        raise ValueError("Download cache must be an object")
except FileNotFoundError:
    files = {}
except (OSError, ValueError, UnicodeError):
    logger.warning("Ignoring invalid download cache: %s", ASSETS_FILE)
    files = {}


_download_locks: dict[str, asyncio.Lock] = {}


async def download(params: dict):
    path = os.path.abspath(params["saveTo"])
    download_lock = _download_locks.setdefault(path, asyncio.Lock())
    async with download_lock:
        await _download(params)


async def _download(params: dict):
    url, saveTo = params["url"], params["saveTo"]
    expected_hash = params.get("hash")
    use_cache = params.get("cache", True)
    cached_hash = files.get(saveTo) if use_cache else None
    dirname = os.path.dirname(saveTo)
    if dirname:
        os.makedirs(dirname, exist_ok=True)

    if os.path.isfile(saveTo):
        with open(saveTo, "rb") as f:
            existing_hash = compute_hash(f, xxh128())
        if existing_hash == (expected_hash if expected_hash is not None else cached_hash):
            logger.info("Verified %s", saveTo)
            return
    else:
        existing_hash = None

    session = await HttpClient.get_client()
    head = await session.head(url, headers={"Accept-Encoding": "identity"}, allow_redirects=True)
    head.raise_for_status()
    head_length = head.headers.get("content-length")
    head_length = int(head_length) if head_length is not None else None
    # Preserve the existing length-based cache behavior only when no hash was requested.
    if use_cache and expected_hash is None and cached_hash is None and existing_hash is not None and head_length is not None and os.path.getsize(saveTo) == head_length:
        write_file_entry(saveTo, existing_hash)
        return

    part = saveTo + ".part"
    part_exists = os.path.isfile(part)
    offset = os.path.getsize(part) if part_exists else 0
    if part_exists and head_length is not None and offset >= head_length:
        # A complete partial file still needs validation below; oversized files restart.
        if offset > head_length:
            os.remove(part)
            offset = 0
        elif expected_hash is not None:
            with open(part, "rb") as f:
                partial_hash = compute_hash(f, xxh128())
            if partial_hash == expected_hash:
                os.replace(part, saveTo)
                if use_cache:
                    write_file_entry(saveTo, partial_hash)
                return
            os.remove(part)
            offset = 0
        else:
            offset = 0
    # A partial file without a trusted hash may belong to another URL or an
    # older version of the same URL; matching its length cannot verify it.
    resume = expected_hash is not None and offset > 0 and head.headers.get("Accept-Ranges", "").lower() == "bytes"
    headers = {"Accept-Encoding": "identity"}
    if resume:
        headers["Range"] = f"bytes={offset}-"
    response = await session.get(url, headers=headers, allow_redirects=True)
    if resume and response.status == 416:
        response.release()
        resume = False
        response = await session.get(url, headers={"Accept-Encoding": "identity"}, allow_redirects=True)
    response.raise_for_status()
    range_match = re.fullmatch(r"bytes (\d+)-(\d+)/(\d+|\*)", response.headers.get("Content-Range", "")) if resume else None
    valid_range = (response.status == 206 and range_match is not None
                   and int(range_match.group(1)) == offset
                   and int(range_match.group(2)) >= offset
                   and (range_match.group(3) == "*" or int(range_match.group(2)) < int(range_match.group(3)))
                   and (head_length is None or range_match.group(3) == "*" or int(range_match.group(3)) == head_length))
    if resume and not valid_range:
        if response.status == 206:
            response.release()
            response = await session.get(url, headers={"Accept-Encoding": "identity"}, allow_redirects=True)
            response.raise_for_status()
        resume = False
    if not resume and response.status != 200:
        raise ValueError("Unexpected download response status")
    if resume and head_length is None and range_match.group(3) != "*":
        head_length = int(range_match.group(3))

    range_length = int(range_match.group(2)) - offset + 1 if resume else None
    get_length = response.headers.get("content-length")
    get_length = int(get_length) if get_length is not None else None
    if resume and get_length is not None and get_length != range_length:
        raise ValueError("Invalid download range length")
    received = 0
    with tqdm(total=get_length, leave=False, unit="B", unit_scale=True, unit_divisor=1024, desc=os.path.basename(saveTo)) as progress:
        with open(part, "ab" if resume else "wb") as f:
            async for chunk in response.content.iter_chunked(1024 * 1024):
                f.write(chunk)
                received += len(chunk)
                progress.update(len(chunk))
    size = os.path.getsize(part)
    if (get_length is not None and received != get_length) or (range_length is not None and received != range_length) or (head_length is not None and size != head_length):
        if (get_length is not None and received > get_length) or (range_length is not None and received > range_length) or (head_length is not None and size > head_length):
            os.remove(part)
        raise ValueError("Downloaded file length does not match server response")
    with open(part, "rb") as f:
        result_hash = compute_hash(f, xxh128())
    if expected_hash is not None and result_hash != expected_hash:
        os.remove(part)
        raise DownloadVerificationException(saveTo, result_hash, expected_hash)
    os.replace(part, saveTo)
    if use_cache:
        write_file_entry(saveTo, result_hash)


def write_file_entry(saveTo: str, hash: str):
    with lock:
        files[saveTo] = hash
        directory = os.path.dirname(os.path.abspath(ASSETS_FILE))
        temp_name = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=directory, delete=False) as f:
                temp_name = f.name
                json.dump(files, f)
            os.replace(temp_name, ASSETS_FILE)
        finally:
            if temp_name and os.path.exists(temp_name):
                os.remove(temp_name)
