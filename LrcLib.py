# LrcLib.py
# Addon for LrcLib – single song lyrics only
# v1.0.0

import os
import time
import re
import requests
from typing import List, Dict, Any, Optional
from addon_base import MetadataFetcher

class LrcLib(MetadataFetcher):
    name = "LrcLib"
    id = "lrclib"
    description = "Fetch synced and unsynced lyrics from LrcLib (single songs only)"

    BASE_URL = "https://lrclib.net/api/"
    USER_AGENT = "metadata-docker-lrclib-addon/1.0.0"

    required_env_vars = []

    REQUEST_DELAY = float(os.getenv("MD_LRCLIB_REQUEST_DELAY", "0.0"))

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": self.USER_AGENT})
        self._last_request_time = 0.0

    def _rate_limit(self):
        if self.REQUEST_DELAY > 0:
            now = time.time()
            elapsed = now - self._last_request_time
            if elapsed < self.REQUEST_DELAY:
                time.sleep(self.REQUEST_DELAY - elapsed)
            self._last_request_time = time.time()

    def _get(self, endpoint: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        self._rate_limit()
        url = self.BASE_URL + endpoint.lstrip('/')
        try:
            resp = self.session.get(url, params=params, timeout=10)  # Add timeout to avoid hanging
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, list):
                return {"data": data}
            return data
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"LrcLib API error: {e}")

    def _clean_dict(self, d: Dict) -> Dict:
        return {k: v for k, v in d.items() if v is not None and v != ""}

    def _normalize_query(self, query: str) -> str:
        """Remove punctuation that may break LrcLib search."""
        normalized = re.sub(r'[^\w\s]', '', query)
        normalized = re.sub(r'\s+', '', normalized).strip()
        return normalized

    # ---------- Song methods ----------

    def search_songs(self, query: str, limit: int = 5, include_coverart: Optional[bool] = None) -> List[Dict[str, Any]]:
        try:
            # First attempt with original query
            data = self._get("search", params={"q": query})
            items = data.get("data", [])

            # If no results, try a normalized version
            if not items:
                normalized = self._normalize_query(query)
                if normalized != query:
                    data = self._get("search", params={"q": normalized})
                    items = data.get("data", [])

            items = items[:limit]
            results = []
            for item in items:
                results.append(self._clean_dict({
                    "id": str(item.get("id")),
                    "title": item.get("trackName", "Unknown"),
                    "artist": item.get("artistName", "Unknown"),
                }))
            return results
        except Exception as e:
            return []

    def fetch_song_metadata(self, song_id: str, album_data: Dict = None) -> Dict[str, Any]:
        try:
            data = self._get(f"get/{song_id}")
            if not data or "id" not in data:
                raise RuntimeError(f"No lyrics found for track {song_id}")
            track = {
                "unsyncedLyrics": data.get("plainLyrics", ""),
                "syncedLyrics": data.get("syncedLyrics", ""),
            }
            return self._clean_dict(track)
        except Exception as e:
            # Re-raise for fetch
            raise RuntimeError(f"Failed to fetch lyrics for song {song_id}: {e}")