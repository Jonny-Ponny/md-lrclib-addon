# md-lrclib-addon

Addon for [metadata-docker](https://github.com/Jonny-Ponny/metadata-docker) that uses the [LrcLib](https://lrclib.net/) API to fetch lyrics (both plain text and synced LRC) for songs.

This addon supports single‑song search and fetch only.

## Addon structure

This addon follows the same base class structure as described in the [metadata-docker](https://github.com/Jonny-Ponny/metadata-docker). It inherits from `MetadataFetcher` and implements two core methods:

- `search_songs(query, limit)` - returns a list of matching songs with basic metadata.
- `fetch_song_metadata(song_id)` - retrieves full lyrics (plain and synced) for a given song ID.

## Environment Variables

| Variable | Purpose | Allowed Values | Default |
|----------|---------|----------------|---------|
| `MD_LRCLIB_REQUEST_DELAY` | Delay in seconds between API requests. Helps avoid hitting rate limits. | Float | `0.0` |

## Implementation Notes

- Query normalisation: If a search query returns zero results, the addon automatically retries with a normalized version where punctuation (e.g., `.`, `/`, `,`, `'`) is removed and multiple spaces are collapsed. This improves the chance of finding songs that have punctuation in their titles.
- Album support: Album search and fetch are intentionally disabled because LrcLib does not provide a dedicated album lyrics endpoint.

## Metadata Fields

The addon returns the following fields for search results and fetched song metadata:

### Search results (`search_songs`)

- `id` - LrcLib track ID (string)
- `title` - track name
- `artist` - artist name

### Fetched song metadata (`fetch_song_metadata`)

All search fields plus:

- `unsyncedLyrics` - plain text lyrics (if available)
- `syncedLyrics` - LRC formatted synced lyrics (if available)

If lyrics are not available, the respective field will be an empty string.

## Using This Addon

1. Place the addon file `LrcLib.py` and `LrcLib_requirements.txt` in metadata-docker `/addons` folder.
2. Restart the container. The addon will be discovered automatically.
3. Optionally, set the `MD_LRCLIB_REQUEST_DELAY` environment variable in your `docker-compose.yml`.

## Troubleshooting

- **No results**: The addon automatically retries with punctuation removed. If that still fails, the query may not exist in the LrcLib database.
- **Fetch fails**: The song ID may be incorrect or the track may not have lyrics on LrcLib.