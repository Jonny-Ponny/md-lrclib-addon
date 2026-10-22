# md-lrclib-addon

Addon for [metadata-docker](https://github.com/Jonny-Ponny/metadata-docker) that uses the [LrcLib](https://lrclib.net/) API to fetch plain-text and synced (LRC) lyrics for individual songs.

Current addon version: `1.1.0`. Source: [md-lrclib-addon](https://github.com/Jonny-Ponny/md-lrclib-addon).

This addon supports single-song search and fetch only. Album search and album fetch are intentionally not implemented because LrcLib does not provide a dedicated album lyrics endpoint.

## Addon structure

The addon inherits from `MetadataFetcher` and implements two methods:

- `search_songs(query, limit=5)` - returns matching songs with the LrcLib track ID and basic display metadata.
- `fetch_song_metadata(song_id)` - retrieves plain and synced lyrics for one LrcLib track.

It also sets the current metadata-docker addon attributes: `name`, `id`, `description`, `version`, `github`, and `required_env_vars`.

## Environment Variables

| Variable | Purpose | Allowed Values | Default |
|----------|---------|----------------|---------|
| `MD_LRCLIB_REQUEST_DELAY` | Delay in seconds between API requests. Set to `0` to disable. Invalid values fall back to `0.0`. | Float | `0.0` |

The delay state is class-level because metadata-docker creates a new fetcher instance for each API request. This makes the delay apply across requests, not just within one instance.

## Implementation Notes

- **Query normalisation**: Search first uses the query exactly as entered. If it returns no results, the addon retries with punctuation removed and whitespace collapsed, while preserving word boundaries. Apostrophes are removed so contractions such as `don't` become `dont` instead of `don t`.
- **Search results**: Include the LrcLib track ID, title, artist, and the album name when available. A display-only `extraInfo` value shows the album, duration, and whether the track is instrumental.
- **Lyrics-only fetch**: Fetched metadata contains only the lyrics fields and display-only `extraInfo`. It does not return title, artist, or album fields, so applying it will not overwrite existing tags with data from LrcLib.
- **Missing lyrics**: If a track has neither plain nor synced lyrics, fetch raises a clear error. Instrumental tracks are reported as instrumental in the error message.
- **Limits**: Search results are capped at 50. A non-positive `limit` returns no results.
- **HTTP handling**: Requests use a 20-second timeout and a versioned User-Agent with the GitHub URL. Temporary `429`/`503` responses are retried up to two times, respecting a numeric `Retry-After` header.
- **Album support**: `search_albums` and `fetch_album_metadata` are not overridden, so metadata-docker correctly reports that album operations are unsupported.

## Metadata Fields

### Search results (`search_songs`)

- `id` - LrcLib track ID (string), passed back to `fetch_song_metadata`
- `title` - track name
- `artist` - artist name
- `album` - album name, when available
- `extraInfo` - display-only album, duration, and instrumental status

### Fetched song metadata (`fetch_song_metadata`)

- `unsyncedLyrics` - plain-text lyrics, when available
- `lyrics` - synced lyrics in LRC format, when available
- `extraInfo` - display-only album and duration

Unavailable lyric fields are omitted rather than returned as empty strings. At least one lyrics field must be available, otherwise the fetch fails. `extraInfo` is never offered as a tag and is never written to a file.

## Using This Addon

1. Place `LrcLib.py` and `LrcLib_requirements.txt` in the metadata-docker `/addons` folder.
2. Restart the container. The addon is discovered automatically.
3. Optionally, set `MD_LRCLIB_REQUEST_DELAY` in your `docker-compose.yml`, for example:

```yaml
environment:
  MD_LRCLIB_REQUEST_DELAY: "0.5"
```

## Troubleshooting

- **No results**: Try searching with both the track title and artist name. The addon automatically retries with punctuation removed if the exact query finds nothing.
- **Fetch fails**: The track may be instrumental, may not have lyrics in LrcLib, or the ID may be invalid.
- **Temporary API errors**: LrcLib can return `429` or `503` responses when busy. The addon retries briefly; increasing `MD_LRCLIB_REQUEST_DELAY` can help avoid rate limiting.
