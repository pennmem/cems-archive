# CEMS Archive

Static archive of the Context and Episodic Memory Symposium (CEMS) pages that used to live on the Computational Memory Lab wiki at `memory.psych.upenn.edu/CEMS` (2009–2026, plus MBC 2023). That server went offline in 2026.

The site is in `docs/` and is served by GitHub Pages (Settings → Pages → Deploy from branch → `main` / `docs`).

## Where the content came from

- Most pages: raw Internet Archive snapshots of the original wiki pages (2025–2026 captures). Each page's banner links to the snapshot it came from.
- CEMS 2016 and MBC 2023 were never captured by the Internet Archive; they are rebuilt from the lab's markdown export of the public wiki, so a few photos and maps are missing.
- Images, program PDFs and photos were recovered from the Internet Archive. For eight photos, only the on-page thumbnail survived, not the full-resolution original.
- The home page (`docs/index.html`) is generated, not archived: it lists 2026 as past and CEMS 2027 (Drexel, May 13–14, 2027) as upcoming. Edit `PAST` and `UPCOMING` in `_build/build.py` to change it.

## Rebuilding

```sh
python _build/fetch_pages.py RAW_DIR                 # download raw page snapshots
python _build/build.py RAW_DIR WIKI_MD_DIR docs      # build the site; caches assets in RAW_DIR/assets
```

`WIKI_MD_DIR` is the `public/` corpus of the lab's wiki-search export. Needs `requests`, `beautifulsoup4` and `markdown`.
