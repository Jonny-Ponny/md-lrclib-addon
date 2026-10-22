# LrcLib.py
# Addon for LrcLib - single-song lyrics only

import math
import os
import re
import threading
import time
from typing import Any, Dict, List, Optional

import requests
from addon_base import MetadataFetcher


def _env_float(name: str, default: float) -> float:
    """Read a float environment variable without crashing on bad values."""
    try:
        value = float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default
    return value if math.isfinite(value) else default


class LrcLib(MetadataFetcher):
    name = "LrcLib"
    id = "lrclib"
    description = "Fetch synced and unsynced lyrics from LrcLib (songs only)"
    version = "1.1.0"
    github = "https://github.com/Jonny-Ponny/md-lrclib-addon"

    BASE_URL = "https://lrclib.net/api/"
    USER_AGENT = (
        f"metadata-docker-lrclib-addon/{version} "
        "(https://github.com/Jonny-Ponny/md-lrclib-addon)"
    )

    required_env_vars = ["MD_LRCLIB_REQUEST_DELAY"]

    REQUEST_DELAY = _env_float("MD_LRCLIB_REQUEST_DELAY", 0.0)
    REQUEST_TIMEOUT = 20
    MAX_RETRIES = 2
    MAX_RESULTS = 50

    # The app creates a new fetcher instance per API request, so the delay
    # state has to live on the class to apply across requests.
    _rate_lock = threading.Lock()
    _last_request_time = 0.0

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": self.USER_AGENT})

    def _rate_limit(self):
        delay = max(0.0, self.REQUEST_DELAY)
        if delay <= 0:
            return

        cls = type(self)
        with cls._rate_lock:
            now = time.monotonic()
            elapsed = now - cls._last_request_time
            if elapsed < delay:
                time.sleep(delay - elapsed)
            cls._last_request_time = time.monotonic()

    def _get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Any:
        url = self.BASE_URL + endpoint.lstrip("/")
        response = None

        # LrcLib occasionally returns 429/503 when busy. Retry a couple of
        # times, respecting a numeric Retry-After header when present.
        for attempt in range(self.MAX_RETRIES + 1):
            self._rate_limit()
            try:
                response = self.session.get(
                    url,
                    params=params,
                    timeout=self.REQUEST_TIMEOUT,
                )
            except requests.exceptions.RequestException as exc:
                raise RuntimeError(f"LrcLib request failed: {exc}") from exc

            if response.status_code in (429, 503) and attempt < self.MAX_RETRIES:
                try:
                    retry_delay = float(response.headers.get("Retry-After", ""))
                except (TypeError, ValueError):
                    retry_delay = 1.0
                if not math.isfinite(retry_delay):
                    retry_delay = 1.0
                time.sleep(min(max(retry_delay, 1.0), 10.0))
                continue
            break

        if response is None:
            raise RuntimeError("LrcLib request failed")

        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as exc:
            if response.status_code == 404:
                raise RuntimeError(f"LrcLib resource not found: {endpoint}") from exc
            raise RuntimeError(
                f"LrcLib API error ({response.status_code}): {exc}"
            ) from exc

        try:
            return response.json()
        except ValueError as exc:
            raise RuntimeError("LrcLib returned an invalid JSON response") from exc

    @staticmethod
    def _normalize_query(query: str) -> str:
        """Remove punctuation while preserving word boundaries."""
        normalized = re.sub(r"['’]", "", query)
        normalized = re.sub(r"[^\w\s]", " ", normalized)
        return re.sub(r"\s+", " ", normalized).strip()

    @staticmethod
    def _format_duration(value: Any) -> str:
        if value is None or value == "":
            return ""
        try:
            total = int(round(float(value)))
        except (TypeError, ValueError, OverflowError):
            return ""
        if total <= 0:
            return ""

        hours, remainder = divmod(total, 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes}:{seconds:02d}"

    @classmethod
    def _format_extra_info(cls, data: Dict[str, Any]) -> str:
        """Build the short display-only description used by metadata-docker."""
        parts = []
        album = data.get("albumName")
        if isinstance(album, str) and album.strip():
            parts.append(album.strip())

        duration = cls._format_duration(data.get("duration"))
        if duration:
            parts.append(duration)

        if data.get("instrumental") and "instrumental" not in {
            part.casefold() for part in parts
        }:
            parts.append("Instrumental")

        return " · ".join(parts)

    def _search(self, query: str) -> List[Dict[str, Any]]:
        data = self._get("search", params={"q": query})
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            items = data.get("data", [])
            return items if isinstance(items, list) else []
        return []

    # ---------- Song methods ----------

    def search_songs(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        query = (query or "").strip()
        if not query:
            return []

        try:
            limit = int(limit)
        except (TypeError, ValueError):
            limit = 5
        if limit <= 0:
            return []
        limit = min(limit, self.MAX_RESULTS)

        items = self._search(query)

        # If the exact query found nothing, retry with punctuation removed but
        # word spacing preserved.
        if not items:
            normalized = self._normalize_query(query)
            if normalized and normalized.casefold() != query.casefold():
                items = self._search(normalized)

        results = []
        for item in items:
            if not isinstance(item, dict):
                continue

            track_id = item.get("id")
            if track_id is None:
                continue

            title = item.get("trackName") or item.get("name") or "Unknown"
            artist = item.get("artistName") or "Unknown"
            result = {
                "id": str(track_id),
                "title": str(title).strip() or "Unknown",
                "artist": str(artist).strip() or "Unknown",
            }

            album = item.get("albumName")
            if isinstance(album, str) and album.strip():
                result["album"] = album.strip()

            extra_info = self._format_extra_info(item)
            if extra_info:
                result["extraInfo"] = extra_info

            results.append(result)
            if len(results) >= limit:
                break

        return results

    def fetch_song_metadata(self, song_id: str) -> Dict[str, Any]:
        song_id = str(song_id).strip()
        if not (song_id.isascii() and song_id.isdigit()):
            raise RuntimeError(f"Invalid LrcLib track ID: {song_id or '(empty)'}")

        try:
            data = self._get(f"get/{song_id}")
        except RuntimeError as exc:
            raise RuntimeError(
                f"Failed to fetch lyrics for track {song_id}: {exc}"
            ) from exc

        if not isinstance(data, dict) or data.get("id") is None:
            raise RuntimeError(f"No data returned for LrcLib track {song_id}")

        track = {}
        plain_lyrics = data.get("plainLyrics")
        if isinstance(plain_lyrics, str) and plain_lyrics.strip():
            track["unsyncedLyrics"] = plain_lyrics

        synced_lyrics = data.get("syncedLyrics")
        if isinstance(synced_lyrics, str) and synced_lyrics.strip():
            track["lyrics"] = synced_lyrics

        if not track:
            if data.get("instrumental"):
                raise RuntimeError(f"LrcLib track {song_id} is instrumental")
            raise RuntimeError(f"No lyrics available for LrcLib track {song_id}")

        extra_info = self._format_extra_info(data)
        if extra_info:
            track["extraInfo"] = extra_info

        return track
