"""Search engine and AI assistant discoverability (MkDocs hook).

Registered in mkdocs.yml under `hooks:`. Standard library only, so it
adds nothing to requirements.txt.

- Dates: each page's last commit date becomes `page.update_date` (the
  sitemap's <lastmod>) and the TechArticle `dateModified`. Without git
  history (a shallow clone, a file not committed yet) MkDocs keeps the
  build date.
- Structured data: one JSON-LD graph per page in `page.meta["_jsonld"]`,
  printed by overrides/main.html. The home page describes the
  Organization, the WebSite and the software; every other page is a
  TechArticle with a BreadcrumbList; a page with `schema: faq` in its
  frontmatter also gets an FAQPage built from its `## Question?`
  headings.
- Markdown: every page's source is published next to its HTML, at its
  source path (overview/architecture.md is served at
  <site_url>overview/architecture.md), and the site root gets llms.txt
  and llms-full.txt in the https://llmstxt.org format.
"""

from __future__ import annotations

import html
import json
import os
import posixpath
import re
import subprocess
from urllib.parse import urlsplit

_nav = None
_pages: dict[str, dict] = {}

# Sections an assistant can skip when it is short of context (the
# llms.txt "Optional" section).
_OPTIONAL_SECTIONS = {"Design system"}

_HTML_TAG = re.compile(
    r"</?(?:div|section|aside|p|h[1-6]|ul|ol|li|a|span|br|img|figure|figcaption|"
    r"details|summary|strong|em|small|nav|header|footer|svg|path|g|text)\b[^>]*>",
    re.I,
)
_HEADING = re.compile(r"<h([1-6])\b[^>]*>(.*?)</h\1>", re.I)
_LIST_ITEM = re.compile(r"<li\b[^>]*>(.*?)</li>", re.I)
_SNIPPET = re.compile(r'^\s*--8<--\s+"[^"]+"\s*$', re.M)
_ATTR_LIST = re.compile(r"\{\s*[.#:][^}\n]*\}")
_MD_LINK = re.compile(r"(\]\()([^)\s]+)(\))")
_FENCE = re.compile(r"^(```|~~~)")


def _site_url(config) -> str:
    """site_url with its trailing slash. mike sets it to <site_url><version>
    without one; MkDocs adds it back for canonical URLs, so must we."""
    url = config["site_url"] or ""
    return url if url.endswith("/") else url + "/"


def _site_root(config) -> str:
    """The domain root (https://host/), whatever version path mike adds."""
    parts = urlsplit(config["site_url"] or "")
    return f"{parts.scheme}://{parts.netloc}/" if parts.netloc else ""


def _git_date(path: str, cwd: str) -> str | None:
    try:
        out = subprocess.run(
            ["git", "log", "-1", "--format=%cI", "--", path],
            cwd=cwd, capture_output=True, text=True, timeout=20, check=False,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None
    return out or None


def _plain(fragment: str) -> str:
    text = re.sub(r'<a class="headerlink"[^>]*>.*?</a>', "", fragment, flags=re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def _clean_markdown(markdown: str) -> str:
    """Markdown as an assistant should read it: no layout HTML, no
    snippet includes (the home page's diagram), no attribute lists.
    Fenced code is left exactly as written."""
    out, in_fence = [], False
    for line in markdown.splitlines():
        if _FENCE.match(line.strip()):
            in_fence = not in_fence
            out.append(line)
            continue
        if in_fence:
            out.append(line)
            continue
        if _SNIPPET.match(line):
            continue
        line = _HEADING.sub(lambda m: "#" * int(m.group(1)) + " " + m.group(2), line)
        line = _LIST_ITEM.sub(r"- \1", line)
        line = _ATTR_LIST.sub("", _HTML_TAG.sub("", line))
        out.append(line.rstrip())
    text = "\n".join(out)
    return re.sub(r"\n{3,}", "\n\n", text).strip() + "\n"


def _absolute_links(markdown: str, src_uri: str, site_url: str) -> str:
    """Relative .md links become the pages' absolute HTML URLs, so the
    links still work once every page sits in one llms-full.txt."""
    base = posixpath.dirname(src_uri)

    def fix(m):
        target = m.group(2)
        if re.match(r"^(?:[a-z][a-z0-9+.-]*:|#|/)", target, re.I):
            return m.group(0)
        path, _, anchor = target.partition("#")
        resolved = posixpath.normpath(posixpath.join(base, path))
        if resolved.endswith(".md"):
            stem = resolved[:-3]
            resolved = stem[: -len("index")] if posixpath.basename(stem) == "index" else stem + "/"
        url = site_url + resolved.lstrip("./") + (f"#{anchor}" if anchor else "")
        return f"{m.group(1)}{url}{m.group(3)}"

    out, in_fence = [], False
    for line in markdown.splitlines():
        if _FENCE.match(line.strip()):
            in_fence = not in_fence
        out.append(line if in_fence else _MD_LINK.sub(fix, line))
    return "\n".join(out)


def _faq(page_html: str) -> list[dict]:
    parts = re.split(r"<h2[^>]*>(.*?)</h2>", page_html, flags=re.S)
    items = []
    for q_html, a_html in zip(parts[1::2], parts[2::2]):
        question, answer = _plain(q_html), _plain(a_html)
        if question.endswith("?") and answer:
            items.append({
                "@type": "Question",
                "name": question,
                "acceptedAnswer": {"@type": "Answer", "text": answer},
            })
    return items


def _index_page(section):
    for child in getattr(section, "children", None) or []:
        if getattr(child, "is_page", False) and getattr(child, "is_index", False):
            return child
    return None


def _jsonld(page, config, nav) -> str:
    root = _site_root(config)
    org_id, site_id = root + "#organization", root + "#website"
    brand = config["extra"].get("brand", {})
    name = brand.get("name") or config["site_name"]
    home = nav.homepage.canonical_url if nav and nav.homepage else _site_url(config)
    url = page.canonical_url or _site_url(config)
    description = page.meta.get("description") or config["site_description"]
    logo = home + "assets/apple-touch-icon.png"
    org = {
        "@type": "Organization", "@id": org_id, "name": name,
        "url": root, "logo": {"@type": "ImageObject", "url": logo, "width": 180, "height": 180},
        "sameAs": [config["repo_url"]] if config.get("repo_url") else [],
    }

    if page.is_homepage:
        graph = [
            org,
            {
                "@type": "WebSite", "@id": site_id, "name": name,
                "alternateName": ["SecretsBridge", f"{name} documentation"],
                "url": root, "description": config["site_description"],
                "inLanguage": config["theme"]["language"], "publisher": {"@id": org_id},
            },
            {
                "@type": "SoftwareApplication", "name": name,
                "applicationCategory": "SecurityApplication",
                "applicationSubCategory": "Secrets access control",
                "operatingSystem": "Kubernetes, Linux",
                "description": description, "url": url,
                "softwareHelp": {"@type": "CreativeWork", "url": url},
                "isAccessibleForFree": True,
                "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"},
                "publisher": {"@id": org_id},
            },
        ]
    else:
        article = {
            "@type": "TechArticle", "headline": page.meta.get("seo_title") or page.title,
            "description": description, "url": url, "mainEntityOfPage": url,
            "image": home + brand.get("og_image", ""),
            "inLanguage": config["theme"]["language"],
            "isPartOf": {"@type": "WebSite", "@id": site_id, "name": name, "url": root},
            "author": {"@type": "Organization", "name": config.get("site_author") or name,
                       "url": config.get("repo_url") or root},
            "publisher": org,
        }
        modified = page.meta.get("_git_date")
        if modified:
            article["dateModified"] = modified
        crumbs = [{"name": name, "item": home}]
        for section in reversed(page.ancestors):
            index = _index_page(section)
            if index is None or index is page:
                continue
            crumbs.append({"name": section.title, "item": index.canonical_url})
        crumbs.append({"name": page.title, "item": url})
        graph = [article, {
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": i, **c} for i, c in enumerate(crumbs, 1)
            ],
        }]
        faq = page.meta.get("_faq")
        if faq:
            graph.append({"@type": "FAQPage", "url": url, "mainEntity": faq})

    doc = {"@context": "https://schema.org", "@graph": graph}
    # "</" closes the <script> element in HTML; JSON allows "<\/".
    return json.dumps(doc, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


# ---- hook events -----------------------------------------------------------

def on_config(config, **kwargs):
    _pages.clear()
    return config


def on_nav(nav, config, files, **kwargs):
    global _nav
    _nav = nav
    return nav


def on_page_markdown(markdown, page, config, files, **kwargs):
    # mike passes --config-file mkdocs.yml, a relative path.
    repo = os.path.dirname(os.path.abspath(config["config_file_path"]))
    date = _git_date(os.path.relpath(page.file.abs_src_path, repo), repo)
    if date:
        page.meta["_git_date"] = date
        page.update_date = date[:10]
    _pages[page.file.src_uri] = {"markdown": markdown}
    return markdown


def on_page_content(page_html, page, config, files, **kwargs):
    if page.meta.get("schema") == "faq":
        page.meta["_faq"] = _faq(page_html)
    return page_html


def on_page_context(context, page, config, nav, **kwargs):
    page.meta["_jsonld"] = _jsonld(page, config, nav)
    page.meta["_md_url"] = _site_url(config) + page.file.src_uri
    _pages[page.file.src_uri].update(
        title=page.meta.get("seo_title") if page.is_homepage else page.title,
        nav_title=page.title,
        description=page.meta.get("description", ""),
        url=page.canonical_url or _site_url(config),
        md_url=page.meta["_md_url"],
    )
    return context


def _walk(items, depth=0):
    for item in items:
        if getattr(item, "is_page", False):
            yield depth, item
        elif getattr(item, "children", None):
            yield from _walk(item.children, depth + 1)


def on_post_build(config, **kwargs):
    site_dir, site_url = config["site_dir"], _site_url(config)
    for src_uri, info in _pages.items():
        dest = os.path.join(site_dir, src_uri)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "w", encoding="utf-8") as f:
            f.write(_clean_markdown(info["markdown"]))

    brand = config["extra"].get("brand", {})
    name = brand.get("name") or config["site_name"]
    header = [
        f"# {name}",
        "",
        f"> {config['site_description'].strip()}",
        "",
        f"{name} is a secrets control plane. It adds access requests, approvals, RBAC, "
        "policy, audit and agent execution around the secrets a team already keeps in AWS "
        "Secrets Manager or HashiCorp Vault. It keeps requests, approvals and audit metadata; "
        "secret values stay in the provider, and the agent runs inside the team's "
        "infrastructure and only connects out. Azure Key Vault and GCP Secret Manager are on "
        "the roadmap. It is open source and pre-1.0: see Product status for what works today.",
        "",
        f"Every page below is also available as Markdown at the linked URL, and {site_url}llms-full.txt "
        "has all of them in one file.",
    ]

    sections: list[tuple[str, list[str]]] = []
    optional: list[str] = []
    full = list(header)
    for item in _nav.items if _nav else []:
        group = item.title if getattr(item, "children", None) else "Start here"
        lines = []
        for depth, page in _walk([item]):
            info = _pages.get(page.file.src_uri)
            if not info or "url" not in info:
                continue
            desc = f": {info['description']}" if info["description"] else ""
            lines.append(f"- [{info['nav_title']}]({info['md_url']}){desc}")
            body = _absolute_links(_clean_markdown(info["markdown"]), page.file.src_uri, site_url)
            full += ["", "---", "", f"Source: {info['url']}", "", body.strip()]
        if group in _OPTIONAL_SECTIONS:
            optional += lines
        elif lines:
            sections.append((group, lines))

    out = list(header)
    for group, lines in sections:
        out += ["", f"## {group}", "", *lines]
    if optional:
        out += ["", "## Optional", "", *optional]
    with open(os.path.join(site_dir, "llms.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")
    with open(os.path.join(site_dir, "llms-full.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(full) + "\n")
