#!/usr/bin/env python3
"""Keep the root of the gh-pages branch in line with the default version.

mike owns the version directories, versions.json and index.html (the
redirect to latest/). The deploy workflow runs this script after mike, on
a checkout of gh-pages, for everything else at the root:

- the files in site-root/ (robots.txt, and any search engine
  verification file added later) are copied as they are;
- llms.txt and llms-full.txt are copies of the default version's, since
  tools look for them at the root;
- sitemap.xml is a sitemap index pointing at <version>/sitemap.xml;
- 404.html is the default version's 404 page with one addition: GitHub
  Pages serves it for every missing path, so an address without a
  version (/operations/config/) is sent to the same page under latest/;
- anything else at the root is left over from the site as it was
  published before mike (May 2026). Each of its pages becomes a redirect
  to the same page under latest/, or the nearest one that still exists,
  and the rest of it (old assets, the old search index) is removed.

The script is idempotent: a second run changes nothing.

Usage: publish_root.py <gh-pages checkout> <site-root dir> [version]
"""

from __future__ import annotations

import html
import json
import os
import re
import shutil
import sys

MIKE_FILES = {".git", ".nojekyll", "CNAME", "index.html", "versions.json"}
GENERATED = {"llms.txt", "llms-full.txt", "sitemap.xml", "404.html"}

REDIRECT = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Moved to {url}</title>
  <link rel="canonical" href="{url}">
  <meta http-equiv="refresh" content="0; url={path}">
  <script>window.location.replace("{path}" + window.location.hash);</script>
</head>
<body>
  <p>This page moved to <a href="{path}">{url}</a>.</p>
</body>
</html>
"""


def main(root: str, extras: str, version: str = "latest") -> None:
    with open(os.path.join(root, "CNAME"), encoding="utf-8") as f:
        site = f"https://{f.read().strip()}/"
    with open(os.path.join(root, "versions.json"), encoding="utf-8") as f:
        versions = json.load(f)
    prefixes = {v["version"] for v in versions} | {a for v in versions for a in v["aliases"]}
    default = os.path.join(root, version)
    if not os.path.isfile(os.path.join(default, "index.html")):
        sys.exit(f"publish_root: {version}/index.html is missing, refusing to touch the root")

    own = set(os.listdir(extras))
    keep = MIKE_FILES | prefixes | GENERATED | own

    # Leftovers from before mike: redirect their pages, drop the rest.
    moved = []
    for name in sorted(os.listdir(root)):
        if name in keep:
            continue
        path = os.path.join(root, name)
        pages = []
        if os.path.isdir(path):
            for dirpath, _, files in os.walk(path):
                if "index.html" in files:
                    pages.append(os.path.relpath(dirpath, root).replace(os.sep, "/"))
            shutil.rmtree(path)
        else:
            os.remove(path)
        for rel in pages:
            target = _nearest(default, rel)
            dest = os.path.join(root, rel, "index.html")
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with open(dest, "w", encoding="utf-8") as f:
                f.write(REDIRECT.format(url=html.escape(site + f"{version}/{target}"),
                                        path=html.escape(f"/{version}/{target}")))
            moved.append(f"/{rel}/ -> /{version}/{target}")

    for name in own:
        shutil.copy2(os.path.join(extras, name), os.path.join(root, name))

    for name in ("llms.txt", "llms-full.txt"):
        src = os.path.join(default, name)
        if os.path.isfile(src):
            shutil.copy2(src, os.path.join(root, name))

    with open(os.path.join(default, "sitemap.xml"), encoding="utf-8") as f:
        dates = re.findall(r"<lastmod>([^<]+)</lastmod>", f.read())
    lastmod = f"<lastmod>{max(dates)}</lastmod>" if dates else ""
    with open(os.path.join(root, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write(
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            f"  <sitemap><loc>{site}{version}/sitemap.xml</loc>{lastmod}</sitemap>\n"
            "</sitemapindex>\n"
        )

    with open(os.path.join(default, "404.html"), encoding="utf-8") as f:
        page = f.read()
    known = "|".join(re.escape(p) for p in sorted(prefixes))
    script = (
        "<script>(function () {"
        f'if (!/^\\/({known})\\//.test(window.location.pathname)) {{'
        f'window.location.replace("/{version}" + window.location.pathname'
        " + window.location.search + window.location.hash);"
        "}})();</script>"
    )
    with open(os.path.join(root, "404.html"), "w", encoding="utf-8") as f:
        f.write(page.replace("</head>", script + "\n</head>", 1))

    for line in moved:
        print(f"redirect {line}")


def _nearest(default: str, rel: str) -> str:
    """The page under the default version for an old path: the same path
    if it still exists, else its closest existing parent."""
    parts = rel.split("/")
    while parts:
        candidate = "/".join(parts)
        if os.path.isfile(os.path.join(default, candidate, "index.html")):
            return candidate + "/"
        parts.pop()
    return ""


if __name__ == "__main__":
    if len(sys.argv) not in (3, 4):
        sys.exit(__doc__.strip().splitlines()[-1])
    main(*sys.argv[1:])
