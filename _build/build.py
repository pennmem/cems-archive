"""Build a static CEMS archive site from Wayback snapshots + the lab wiki markdown export.

Usage: python build.py RAW_DIR MD_DIR OUT_DIR
  RAW_DIR  output of fetch_pages.py (raw MediaWiki HTML + pages.json); assets are cached in RAW_DIR/assets
  MD_DIR   wiki-search public corpus (used for pages Wayback never captured)
  OUT_DIR  site root (docs/ for GitHub Pages)
"""
import hashlib
import html
import re
import sys
import time
from pathlib import Path
from urllib.parse import unquote, urlparse

import markdown
import requests
from bs4 import BeautifulSoup, Comment

HOST = "memory.psych.upenn.edu"
SITE = f"https://{HOST}"
UA = {"User-Agent": "cems-archive-restore/1.0"}

# wiki page name -> (output slug, nav label). Slug "" is the site index.
PAGES = {"CEMS": ("", "Home")}
for y in list(range(2009, 2025)) + [2026]:
    PAGES[f"CEMS_{y}"] = (str(y), str(y))
PAGES["CEMS_2015_registration"] = ("2015-registration", "2015 registration")
PAGES["MBC2023"] = ("mbc2023", "MBC 2023")
NAV = [p for p in PAGES if re.fullmatch(r"CEMS_\d{4}", p)]

# Index content. Pre-2009 meetings never had their own pages.
PAST = [
    ("2002", None, "November 6, Orlando, FL", "Satellite symposium at the Society for Neuroscience Meeting"),
    ("2003", None, "November 13, New Orleans, LA", "Satellite symposium at the Society for Neuroscience Meeting"),
    ("2005", None, "March 19–21, Philadelphia, PA", None),
    ("2008", None, "January 3–4, Tampa, FL", None),
    ("2009", "CEMS_2009", "January 2–3, Palm Beach, FL", None),
    ("2010", "CEMS_2010", "April 28–29, Philadelphia, PA", None),
    ("2011", "CEMS_2011", "May 5–6, Philadelphia, PA", None),
    ("2012", "CEMS_2012", "May 10, Bloomington, IN", None),
    ("2013", "CEMS_2013", "May 9–10, Philadelphia, PA", None),
    ("2014", "CEMS_2014", "May 8–9, Philadelphia, PA", None),
    ("2015", "CEMS_2015", "May 7–8, Philadelphia, PA", None),
    ("2016", "CEMS_2016", "May 5–6, Philadelphia, PA", None),
    ("2017", "CEMS_2017", "May 4–5, Philadelphia, PA", None),
    ("2018", "CEMS_2018", "May 7–8, Philadelphia, PA", None),
    ("2019", "CEMS_2019", "May 13–14, Philadelphia, PA", None),
    ("2020", "CEMS_2020", "May 7–8, Philadelphia, PA", None),
    ("2021", "CEMS_2021", "August 16–17, Philadelphia, PA", None),
    ("2022", "CEMS_2022", "May 12–13, Philadelphia, PA", None),
    ("2023", "CEMS_2023", "June 1–2, Orlando, FL", "MBC2023"),
    ("2024", "CEMS_2024", "May 30–31, Philadelphia, PA", None),
    ("2026", "CEMS_2026", "May 28–29, Philadelphia, PA", None),
]
UPCOMING = ("CEMS 2027", "May 13–14, 2027, Drexel University, Philadelphia, PA")


class Assets:
    """Fetches files from the dead wiki via Wayback, caches them, and copies them into the site."""

    def __init__(self, cache, out):
        self.cache, self.out = cache, out
        self.cache.mkdir(parents=True, exist_ok=True)
        (out / "assets").mkdir(parents=True, exist_ok=True)
        self.missing = set()
        self.done = {}

    def get(self, path):
        """path like /mediawiki/images/...; returns site-root-relative 'assets/<name>' or None."""
        path = unquote(path)
        if path in self.done:
            return self.done[path]
        name = path.rstrip("/").split("/")[-1]
        cached = self.cache / name
        if not cached.exists() and path not in self.missing:
            data = None
            for scheme in ("https", "http"):
                url = f"https://web.archive.org/web/2026id_/{scheme}://{HOST}{path}"
                for attempt in range(3):
                    try:
                        r = requests.get(url, headers=UA, timeout=90)
                        if r.status_code == 404:
                            break
                        r.raise_for_status()
                        # Wayback sometimes serves an HTML error page with 200; never accept HTML for a file.
                        if not r.content.lstrip()[:15].lower().startswith((b"<!doctype", b"<html")):
                            data = r.content
                        break
                    except Exception:
                        time.sleep(4 * (attempt + 1))
                if data:
                    break
                time.sleep(1)
            if data:
                cached.write_bytes(data)
                print(f"  asset ok   {path} ({len(data)} B)")
            else:
                print(f"  asset MISS {path}")
                self.missing.add(path)
        result = None
        if cached.exists():
            (self.out / "assets" / name).write_bytes(cached.read_bytes())
            result = f"assets/{name}"
        self.done[path] = result
        return result


def file_path(name):
    """MediaWiki hashed upload path for File:<name>."""
    name = unquote(name).replace(" ", "_")
    name = name[0].upper() + name[1:]
    h = hashlib.md5(name.encode()).hexdigest()
    return f"/mediawiki/images/{h[0]}/{h[:2]}/{name}"


def page_href(page, depth):
    slug = PAGES[page][0]
    return ("../" * depth) + (f"{slug}/" if slug else "")


def rewrite(content, assets, depth):
    """Point every link/image at local copies; unwrap dead wiki-internal links."""
    up = "../" * depth
    for img in content.find_all("img"):
        src = img.get("src", "")
        u = urlparse(src)
        img.attrs.pop("srcset", None)
        if u.netloc in ("", HOST) and u.path.startswith(("/mediawiki/", "/files/")):
            local = assets.get(u.path)
            if local:
                img["src"] = up + local
                img["loading"] = "lazy"
                continue
        # Google static maps (needs an API key) and anything unrecoverable
        (img.find_parent("div", class_="thumb") or img).decompose()
    for a in content.find_all("a", href=True):
        href = a["href"]
        if href.startswith(("#", "mailto:")):
            continue
        u = urlparse(href)
        if u.netloc not in ("", HOST):
            continue
        path = unquote(u.path)
        frag = f"#{u.fragment}" if u.fragment else ""
        page = path.lstrip("/")
        if page in PAGES:
            a["href"] = page_href(page, depth) + frag
        elif "redlink=1" in u.query or "action=edit" in u.query:
            a.unwrap()
        elif page.startswith("File:"):
            local = assets.get(file_path(page[5:]))
            if local:
                a["href"] = up + local
            else:
                a.unwrap()
        elif path.startswith(("/mediawiki/images/", "/files/")):
            local = assets.get(path)
            a["href"] = up + local if local else f"https://web.archive.org/web/2026/{SITE}{path}"
        else:
            a["href"] = f"https://web.archive.org/web/2026/{SITE}{path}" + (f"?{u.query}" if u.query else "")
    for a in content.find_all("a", href=re.compile(r"^https?://")):
        a["rel"] = "noopener"


def from_wayback(raw):
    soup = BeautifulSoup(raw, "html.parser")
    content = soup.select_one("#mw-content-text")
    for sel in ["span.mw-editsection", "div.magnify", "div.printfooter", "#toc"]:
        for el in content.select(sel):
            el.decompose()
    for c in content.find_all(string=lambda s: isinstance(s, Comment)):
        c.extract()
    return content


def from_markdown(text):
    text = re.sub(r"^---\n.*?\n---\n", "", text, flags=re.S)
    # "[!](.../File:X)" is an image the export flattened; restore it as an image.
    text = re.sub(r"\[!\]\((https?://[^)]*?/File:([^)\s]+))\)",
                  lambda m: f"![]({SITE}{file_path(m.group(2))})", text)
    text = re.sub(r"(?m)^!\s*$", "", text)  # images the export lost entirely (Google static maps)
    body = markdown.markdown(text, extensions=["tables", "sane_lists"])
    return BeautifulSoup(f"<div>{body}</div>", "html.parser").div


def tidy(content):
    # Some original pages link "#schedule" to a heading id like "Schedule_.26_Spoken_Presentations".
    ids = [e["id"] for e in content.find_all(id=True)]
    for a in content.find_all("a", href=re.compile(r"^#.")):
        frag = a["href"][1:]
        if frag not in ids:
            match = next((i for i in ids if i.lower().startswith(frag.lower())), None)
            if match:
                a["href"] = f"#{match}"
    for p in content.find_all("p"):
        if not p.get_text(strip=True) and not p.find("img"):
            p.decompose()
    for t in content.find_all("table"):
        for attr in ("width", "border", "cellpadding", "cellspacing", "style"):
            t.attrs.pop(attr, None)
        t.wrap(BeautifulSoup("", "html.parser").new_tag("div", attrs={"class": "table-wrap"}))
    return content


def shell(title, body, depth, current):
    up = "../" * depth
    nav = "".join(
        f'<a href="{page_href(p, depth)}"{" aria-current=page" if p == current else ""}>{PAGES[p][1]}</a>'
        for p in NAV)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<link rel="stylesheet" href="{up}style.css">
</head>
<body>
<header class="site">
  <a class="brand" href="{up or './'}">CEMS <span>Archive</span></a>
  <p class="tag">Context and Episodic Memory Symposium, 2002–2026</p>
  <nav aria-label="Years">{nav}</nav>
</header>
<main>
<h1>{html.escape(title)}</h1>
{body}
</main>
</body>
</html>
"""


def build_index(out):
    rows = []
    for year, page, when, extra in PAST:
        label = f'<a href="{page_href(page, 0)}">CEMS {year}</a>' if page else f"CEMS {year}"
        sub = ""
        if extra == "MBC2023":
            sub = f'<span class="sub">Followed by <a href="{page_href("MBC2023", 0)}">MBC 2023</a>, June 3, Orlando, FL</span>'
        elif extra:
            sub = f'<span class="sub">{extra}</span>'
        rows.append(f"<li><span class=year>{label}</span><span class=when>{when}</span>{sub}</li>")
    body = f"""
<p class="lede">The Context and Episodic Memory Symposium (CEMS), first held in 2002, is designed to be a forum for the
exchange of ideas among colleagues working on theoretical and empirical approaches to the study of context and
episodic memory, broadly construed.</p>
<section class="upcoming"><h2>Upcoming</h2><p><strong>{UPCOMING[0]}</strong>: {UPCOMING[1]}</p></section>
<h2>Past symposia</h2>
<ul class="years">{''.join(reversed(rows))}</ul>
"""
    (out / "index.html").write_text(shell("Context and Episodic Memory Symposium", body, 0, "CEMS"))


def main(raw_dir, md_dir, out_dir):
    raw, md, out = Path(raw_dir), Path(md_dir), Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    assets = Assets(raw / "assets", out)
    for page, (slug, _) in PAGES.items():
        if page == "CEMS":
            continue
        print(page)
        depth = 1
        title = page.replace("_", " ").replace("MBC2023", "MBC 2023").replace("registration", "Registration")
        src = raw / f"{page}.html"
        if src.exists():
            content = from_wayback(src.read_bytes())
        else:
            content = from_markdown((md / f"{page.replace('_', ' ')}.md").read_text())
        rewrite(content, assets, depth)
        tidy(content)
        body = "".join(str(c) for c in content.contents)
        d = out / slug
        d.mkdir(exist_ok=True)
        (d / "index.html").write_text(shell(title, body, depth, page))
    build_index(out)
    print("missing assets:", sorted(assets.missing) or "none")


if __name__ == "__main__":
    main(*sys.argv[1:4])
