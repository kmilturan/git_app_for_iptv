from __future__ import annotations

import concurrent.futures
import logging
import os
import re
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parent.parent
SOURCES_FILE = ROOT / "sources.txt"
OUTPUT_FILE = ROOT / "playlist.m3u"
LOG = logging.getLogger("iptv_builder")

USER_AGENT = "IPTV-Playlist-Builder/1.0 (+https://github.com/)"
DEFAULT_SOURCES: list[str] = []
SOURCE_TIMEOUT = float(os.getenv("SOURCE_TIMEOUT", "15"))
STREAM_TIMEOUT = float(os.getenv("STREAM_TIMEOUT", "6"))
WORKERS = max(1, min(int(os.getenv("WORKERS", "16")), 64))
RETRIES = max(0, min(int(os.getenv("RETRIES", "1")), 4))
MIN_CHANNELS = max(1, int(os.getenv("MIN_CHANNELS", "5")))
MAX_PLAYLIST_BYTES = 20 * 1024 * 1024

# Alias matching uses normalized exact names first, then conservative token boundaries.
# Keep short aliases (e.g. "arb", "space") only when they cannot swallow a longer channel name.
MASTER_CHANNELS = {
    "aztv": {"name": "AzTV", "group": "Azerbaycan", "tvg_id": "AzTV.az",
             "aliases": ["aztv", "az tv", "azerbaijan tv"]},
    "itv": {"name": "İTV HD", "group": "Azerbaycan", "tvg_id": "ITV.az",
            "aliases": ["itv", "itv hd", "ictimai tv", "ictimai"]},
    "baku tv": {"name": "Baku TV", "group": "Azerbaycan", "tvg_id": "BakuTV.az",
                "aliases": ["baku tv", "bakutv", "baku.tv", "baku-tv"]},
    "xəzər tv": {"name": "Xəzər TV", "group": "Azerbaycan", "tvg_id": "KhazarTV.az",
                 "aliases": ["xəzər tv", "khazar tv", "xezer tv", "xezertv", "xəzər"]},
    "arb tv": {"name": "ARB TV", "group": "Azerbaycan", "tvg_id": "ARBTv.az",
               "aliases": ["arb tv", "azad azərbaycan"]},
    "arb 24": {"name": "ARB 24", "group": "Xeber", "tvg_id": "ARB24.az",
               "aliases": ["arb 24", "arb24"]},
    "arb günəş": {"name": "ARB Günəş", "group": "Usaq ve Senedli", "tvg_id": "ARBGunesh.az",
                  "aliases": ["arb günəş", "arb gunes"]},
    "space tv": {"name": "Space TV", "group": "Azerbaycan", "tvg_id": "SpaceTV.az",
                 "aliases": ["space tv", "spacetv"]},
    "lider tv": {"name": "Lider TV", "group": "Azerbaycan", "tvg_id": "LiderTV.az",
                 "aliases": ["lider tv", "lidertv"]},
    "mədəniyyət tv": {"name": "Mədəniyyət TV", "group": "Azerbaycan", "tvg_id": "MedeniyyetTV.az",
                      "aliases": ["mədəniyyət tv", "medeniyyet tv", "mədəniyyət"]},
    "dunya tv": {"name": "Dünya TV", "group": "Azerbaycan", "tvg_id": "DunyaTV.az",
                 "aliases": ["dunya tv", "dünya tv", "dunyatv"]},
    "cbc az": {"name": "CBC Azerbaijan", "group": "Azerbaycan", "tvg_id": "CBCAzerbaijan.az",
               "aliases": ["cbc az", "cbc azerbaijan", "cbcaz"]},
    "cbc sport": {"name": "CBC Sport", "group": "Idman", "tvg_id": "CBCSport.az",
                  "aliases": ["cbc sport", "cbcsport"]},
    "idman az": {"name": "İdman Azərbaycan", "group": "Idman", "tvg_id": "IdmanAzerbaijan.az",
                 "aliases": ["idman az", "idmanazerbaijan", "idman tv"]},
    "trt 1": {"name": "TRT 1", "group": "Turkiye - Esas", "tvg_id": "TRT1.tr",
              "aliases": ["trt 1", "trt1"]},
    "kanal d": {"name": "Kanal D", "group": "Turkiye - Esas", "tvg_id": "KanalD.tr",
                "aliases": ["kanal d", "kanald", "euro d"]},
    "show tv": {"name": "Show TV", "group": "Turkiye - Esas", "tvg_id": "ShowTV.tr",
                "aliases": ["show tv", "showtv", "show hd"]},
    "star tv": {"name": "Star TV", "group": "Turkiye - Esas", "tvg_id": "StarTV.tr",
                "aliases": ["star tv", "startv"]},
    "atv tr": {"name": "ATV", "group": "Turkiye - Esas", "tvg_id": "ATV.tr",
               "aliases": ["atv türkiye", "atv turkiye", "atv hd", "tr atv", "a2 tv"]},
    "tv8": {"name": "TV8", "group": "Turkiye - Esas", "tvg_id": "TV8.tr", "aliases": ["tv8"]},
    "tv8.5": {"name": "TV8.5", "group": "Idman", "tvg_id": "TV85.tr",
              "aliases": ["tv8.5", "tv85", "tv 8.5"]},
    "now tv": {"name": "NOW TV", "group": "Turkiye - Esas", "tvg_id": "NowTV.tr",
               "aliases": ["now tv", "nowtv", "fox tv", "now hd"]},
    "kanal 7": {"name": "Kanal 7", "group": "Turkiye - Esas", "tvg_id": "Kanal7.tr",
                "aliases": ["kanal 7", "kanal7"]},
    "beyaz tv": {"name": "Beyaz TV", "group": "Turkiye - Esas", "tvg_id": "BeyazTV.tr",
                 "aliases": ["beyaz tv", "beyaztv"]},
    "teve2": {"name": "Teve2", "group": "Turkiye - Esas", "tvg_id": "Teve2.tr",
              "aliases": ["teve2", "teve 2"]},
    "trt haber": {"name": "TRT Haber", "group": "Xeber", "tvg_id": "TRTHaber.tr",
                  "aliases": ["trt haber", "trthaber"]},
    "trt spor": {"name": "TRT Spor", "group": "Idman", "tvg_id": "TRTSpor.tr",
                 "aliases": ["trt spor", "trtspor", "trt spor yıldız"]},
    "a haber": {"name": "A Haber", "group": "Xeber", "tvg_id": "AHaber.tr",
                "aliases": ["a haber", "ahaber"]},
    "cnnturk": {"name": "CNN Türk", "group": "Xeber", "tvg_id": "CNNTurk.tr",
                "aliases": ["cnn türk", "cnn turk", "cnntürk"]},
    "haberturk": {"name": "Habertürk", "group": "Xeber", "tvg_id": "Haberturk.tr",
                  "aliases": ["habertürk", "haberturk"]},
    "tgrt haber": {"name": "Tgrt Haber", "group": "Xeber", "tvg_id": "",
                   "aliases": ["tgrt haber", "tgrthaber"]},
    "haber global": {"name": "Haber Global", "group": "Xeber", "tvg_id": "",
                     "aliases": ["haber global"]},
    "halk tv": {"name": "Halk TV", "group": "Xeber", "tvg_id": "",
                "aliases": ["halk tv", "halktv"]},
    "ntv": {"name": "NTV", "group": "Xeber", "tvg_id": "",
            "aliases": ["ntv", "ntv hd"]},
}

BLOCKED_TERMS = ("bein sports", "s sport", "exxen", "tivibu", "smart spor")
PREFIX_RE = re.compile(r"^(?:tr|az|hd|fhd|sd|hevc|4k)\s*:\s*", re.I)
GROUP_RE = re.compile(r'(?:^|\s)group-title="([^"]*)"', re.I)
TVG_ID_RE = re.compile(r'(?:^|\s)tvg-id="([^"]*)"', re.I)
ATTR_RE = re.compile(r'([\w-]+)="([^"]*)"')
URL_RE = re.compile(r"^https?://", re.I)


@dataclass(frozen=True)
class Entry:
    extinf: str
    url: str
    source_index: int
    source_order: int


@dataclass(frozen=True)
class Channel:
    unique_key: str
    group: str
    name: str
    tvg_id: str
    url: str
    source_index: int
    source_order: int


def normalize_name(value: str) -> str:
    value = value.casefold().strip()
    value = value.replace("ı", "i")
    value = re.sub(r"[\u200b-\u200f]", "", value)
    value = re.sub(r"\s+", " ", value)
    value = PREFIX_RE.sub("", value).strip()
    return value


def match_master_channel(channel_name: str):
    name = normalize_name(channel_name)
    if any(term in name for term in BLOCKED_TERMS):
        return "BLOCKED", None

    # Longest aliases first prevents "ARB 24" from being mistaken for "ARB TV".
    candidates = []
    for key, data in MASTER_CHANNELS.items():
        for alias in data["aliases"]:
            candidates.append((normalize_name(alias), key, data))
    candidates.sort(key=lambda item: len(item[0]), reverse=True)

    for alias, key, data in candidates:
        if name == alias or name.startswith(alias + " ") or name.endswith(" " + alias):
            return key, data
    return None, None


def request_bytes(url: str, timeout: float, limit: int = MAX_PLAYLIST_BYTES) -> bytes:
    req = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        status = getattr(response, "status", response.getcode())
        if status < 200 or status >= 400:
            raise urllib.error.HTTPError(url, status, "Unexpected HTTP status", response.headers, None)
        data = response.read(limit + 1)
        if len(data) > limit:
            raise ValueError(f"Response exceeded {limit} bytes: {url}")
        return data


def load_sources() -> list[str]:
    if SOURCES_FILE.exists():
        result = []
        for line in SOURCES_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and line not in result:
                result.append(line)
        return result
    return DEFAULT_SOURCES.copy()


def parse_m3u(content: str, source_index: int) -> list[Entry]:
    lines = content.lstrip("\ufeff").splitlines()
    entries: list[Entry] = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line.startswith("#EXTINF:"):
            i += 1
            continue
        extinf = line
        j = i + 1
        while j < len(lines) and (not lines[j].strip() or lines[j].strip().startswith("#")):
            j += 1
        if j < len(lines):
            url = lines[j].strip()
            if URL_RE.match(url):
                entries.append(Entry(extinf, url, source_index, len(entries)))
                i = j + 1
                continue
        i += 1
    return entries


def get_channel_name(extinf: str) -> str:
    # EXTINF attributes are quoted; use the last comma as the display-name separator.
    _, sep, display_name = extinf.partition(",")
    if not sep:
        return ""
    return display_name.strip()


def get_group(extinf: str) -> str:
    match = GROUP_RE.search(extinf)
    group = match.group(1).strip() if match else ""
    if not group or group.casefold() in {"diger kanallar", "other", "unsorted"}:
        return "unsorted"
    return group


def stream_is_valid(url: str) -> bool:
    """Check reachability without downloading an entire live stream."""
    last_error = None
    for attempt in range(RETRIES + 1):
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": USER_AGENT, "Accept": "*/*", "Range": "bytes=0-2047"}
            )
            with urllib.request.urlopen(req, timeout=STREAM_TIMEOUT) as response:
                status = getattr(response, "status", response.getcode())
                if 200 <= status < 400:
                    # For HLS playlists, a reachable master/media manifest is a stronger signal.
                    path = urllib.parse.urlparse(response.geturl()).path.lower()
                    content_type = response.headers.get("Content-Type", "").lower()
                    if path.endswith((".m3u8", ".m3u")) or "mpegurl" in content_type:
                        sample = response.read(8192).decode("utf-8", errors="ignore")
                        return "#EXTM3U" in sample or "#EXT-X-" in sample
                    return True
                last_error = f"HTTP {status}"
        except Exception as exc:
            last_error = str(exc)
        if attempt < RETRIES:
            time.sleep(0.25 * (attempt + 1))
    LOG.debug("Stream check failed for %s: %s", url, last_error)
    return False


def process_entry(entry: Entry, valid_cache: dict[str, bool], cache_lock) -> Channel | None:
    name = get_channel_name(entry.extinf)
    if not name:
        return None
    master_key, master = match_master_channel(name)
    if master_key == "BLOCKED":
        return None

    # Cache URL checks so duplicate URLs are not repeatedly probed.
    with cache_lock:
        cached = valid_cache.get(entry.url)
    if cached is None:
        is_valid = stream_is_valid(entry.url)
        with cache_lock:
            valid_cache[entry.url] = is_valid
    else:
        is_valid = cached
    if not is_valid:
        return None

    if master:
        return Channel(master_key, master["group"], master["name"], master["tvg_id"],
                       entry.url, entry.source_index, entry.source_order)

    clean_name = PREFIX_RE.sub("", name).strip()
    return Channel(normalize_name(clean_name), get_group(entry.extinf), clean_name, "",
                   entry.url, entry.source_index, entry.source_order)


def build_playlist(channels: Iterable[Channel]) -> str:
    # Keep first valid occurrence, but output in stable source order.
    ordered = sorted(channels, key=lambda c: (c.source_index, c.source_order, c.name.casefold()))
    deduped: list[Channel] = []
    seen: set[str] = set()
    for channel in ordered:
        if channel.unique_key not in seen:
            seen.add(channel.unique_key)
            deduped.append(channel)

    lines = ["#EXTM3U"]
    for channel in deduped:
        group = channel.group.replace('"', "'")
        name = channel.name.replace("\r", " ").replace("\n", " ").replace(",", " -")
        tvg_id = channel.tvg_id.replace('"', "'")
        if tvg_id:
            lines.append(f'#EXTINF:-1 tvg-id="{tvg_id}" group-title="{group}",{name}')
        else:
            lines.append(f'#EXTINF:-1 group-title="{group}",{name}')
        lines.append(channel.url)
    return "\n".join(lines) + "\n"


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except OSError:
            pass
        raise


def main() -> int:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(message)s",
    )
    sources = load_sources()
    LOG.info("Active authorized sources configured: %d", len(sources))
    if not sources:
        LOG.error("No sources configured. Add authorized M3U/M3U8 URLs to sources.txt. Existing playlist was not changed.")
        return 1
    all_entries: list[Entry] = []
    successful_sources = 0

    for index, source in enumerate(sources):
        try:
            content = request_bytes(source, SOURCE_TIMEOUT).decode("utf-8", errors="replace")
            entries = parse_m3u(content, index)
            all_entries.extend(entries)
            successful_sources += 1
            LOG.info("Loaded source %d/%d: %d entries", index + 1, len(sources), len(entries))
        except Exception as exc:
            LOG.warning("Source failed (%s): %s", source, exc)

    if successful_sources == 0:
        LOG.error("All sources failed. Existing playlist was not changed.")
        return 2
    if not all_entries:
        LOG.error("No entries found. Existing playlist was not changed.")
        return 3

    LOG.info("Checking %d candidate entries with %d workers", len(all_entries), WORKERS)
    valid_cache: dict[str, bool] = {}
    import threading
    cache_lock = threading.Lock()
    channels: list[Channel] = []
    failures = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=WORKERS) as executor:
        futures = [executor.submit(process_entry, entry, valid_cache, cache_lock) for entry in all_entries]
        for future in concurrent.futures.as_completed(futures):
            try:
                result = future.result()
                if result:
                    channels.append(result)
            except Exception:
                failures += 1
                LOG.exception("Unexpected channel processing error")

    playlist = build_playlist(channels)
    channel_count = max(0, (len(playlist.splitlines()) - 1) // 2)
    if channel_count < MIN_CHANNELS:
        LOG.error(
            "Only %d channels passed validation (minimum %d). Existing playlist was not changed.",
            channel_count, MIN_CHANNELS,
        )
        return 4

    # Verify basic structure before replacing the last known-good output.
    lines = playlist.splitlines()
    if not lines or lines[0] != "#EXTM3U" or (len(lines) - 1) % 2 != 0:
        LOG.error("Generated playlist failed structural validation. Existing playlist was not changed.")
        return 5

    atomic_write(OUTPUT_FILE, playlist)
    LOG.info(
        "Updated %s: %d channels; %d unique URL checks; %d processing errors",
        OUTPUT_FILE.name, channel_count, len(valid_cache), failures,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
