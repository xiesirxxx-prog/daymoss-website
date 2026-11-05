#!/usr/bin/env python3
"""Check preview and release builds without weakening either gate."""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from build import (
    CONFIRMED_EFFECTIVE_DATES,
    CONFIRMED_UPDATED_DATES,
    UNPUBLISHED_MARKERS,
    release_errors,
)

ALLOWED_EXTERNAL = {
    "https://www.apple.com/legal/privacy/",
    "https://www.apple.com/legal/internet-services/itunes/dev/stdeula/",
}

EXPECTED = [
    "/daymoss/privacy",
    "/daymoss/terms",
    "/daymoss/support",
    "/zh/daymoss/privacy",
    "/zh/daymoss/terms",
    "/zh/daymoss/support",
]
EMBED = [
    "/daymoss/embed/privacy",
    "/daymoss/embed/terms",
    "/daymoss/embed/support",
    "/zh/daymoss/embed/privacy",
    "/zh/daymoss/embed/terms",
    "/zh/daymoss/embed/support",
]
ALL_PATHS = EXPECTED + EMBED


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format, *args):  # noqa: A003
        return


def fail(message: str) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(1)


def check_site(dist: Path, pages: list) -> None:
    errors = release_errors(pages)
    if not errors:
        fail("expected the placeholder release gate to refuse publication")
    assert_confirmed_dates(pages)
    if not (dist / "PLACEHOLDER_DO_NOT_PUBLISH.txt").is_file():
        fail("preview output is missing the do-not-publish marker")
    robots = (dist / "robots.txt").read_text(encoding="utf-8")
    if "Disallow: /" not in robots or "Allow: /" in robots:
        fail("preview robots.txt must disallow crawlers and must not allow the site")
    pages_html, assets_css = fetch_site(dist)
    for href, page in pages_html.items():
        if href in EMBED:
            inspect_embed_page(href, page, pages, preview=True)
        else:
            inspect_page(href, page, pages_html, preview=True)
    assert_same_prose(pages_html)
    assert_parallel_sections(pages_html)
    inspect_assets(assets_css)
    print("preview link check passed for 12 pages")


def check_release_site(dist: Path, pages: list) -> None:
    errors = release_errors(pages)
    if errors:
        fail("release check refused:\n- " + "\n- ".join(errors))
    assert_confirmed_dates(pages)
    if (dist / "PLACEHOLDER_DO_NOT_PUBLISH.txt").is_file():
        fail("release output still contains the do-not-publish marker")
    robots = (dist / "robots.txt").read_text(encoding="utf-8")
    if robots != "User-agent: *\nAllow: /\n" or "Disallow" in robots:
        fail("release robots.txt is not the public allow rule")
    pages_html, assets_css = fetch_site(dist)
    for href, page in pages_html.items():
        if href in EMBED:
            inspect_embed_page(href, page, pages, preview=False)
        else:
            inspect_page(href, page, pages_html, preview=False)
    assert_same_prose(pages_html)
    assert_parallel_sections(pages_html)
    inspect_assets(assets_css)
    print("release link check passed for 12 pages")


def check_release_copy(website_root: Path) -> None:
    """Build a throwaway tree with placeholder false. The main site stays locked."""
    sources = [website_root / "content" / lang / f"{page_id}.md"
               for lang in ("en", "zh") for page_id in ("privacy", "terms", "support")]
    before = {path: path.read_text(encoding="utf-8") for path in sources}
    if any("placeholder: true" not in text for text in before.values()):
        fail("main site is missing placeholder: true; release-copy test aborted")
    with tempfile.TemporaryDirectory(prefix="daymoss-release-copy-") as raw:
        temp_root = Path(raw)
        shutil.copytree(website_root / "content", temp_root / "content")
        shutil.copytree(website_root / "assets", temp_root / "assets")
        shutil.copy2(website_root / "build.py", temp_root / "build.py")
        shutil.copy2(website_root / "check_site.py", temp_root / "check_site.py")
        for path in sources:
            target = temp_root / path.relative_to(website_root)
            target.write_text(
                target.read_text(encoding="utf-8").replace("placeholder: true", "placeholder: false", 1),
                encoding="utf-8",
            )
        completed = subprocess.run(
            [sys.executable, "build.py", "--release-check"],
            cwd=temp_root,
            check=False,
        )
        if completed.returncode != 0:
            fail("temporary release copy failed its release check")
    after = {path: path.read_text(encoding="utf-8") for path in sources}
    if after != before:
        fail("release-copy test changed the main site")
    print("temporary release copy passed; main site remains placeholder: true")


def assert_confirmed_dates(pages: list) -> None:
    for page in pages:
        expected = CONFIRMED_EFFECTIVE_DATES[page["lang"]]
        updated = CONFIRMED_UPDATED_DATES[page["lang"]]
        if page["effective_date"] != expected:
            fail(f"{page['href']} effective date is {page['effective_date']!r}, expected {expected!r}")
        if page["updated_date"] != updated:
            fail(f"{page['href']} last updated date is {page['updated_date']!r}, expected {updated!r}")
    if {page["effective_date"] for page in pages} != set(CONFIRMED_EFFECTIVE_DATES.values()):
        fail("the six pages do not share the confirmed English and Chinese effective dates")
    if {page["updated_date"] for page in pages} != set(CONFIRMED_UPDATED_DATES.values()):
        fail("the six pages do not share the confirmed English and Chinese last-updated dates")


def fetch_site(dist: Path) -> tuple:
    directory = str(dist)

    class Handler(QuietHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=directory, **kwargs)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        pages_html = {href: fetch(f"{base}{href}/") for href in ALL_PATHS}
        assets_css = fetch(f"{base}/assets/site.css")
        fetch(f"{base}/assets/favicon.svg")
        fetch(f"{base}/robots.txt")
    finally:
        server.shutdown()
    return pages_html, assets_css


def inspect_assets(assets_css: str) -> None:
    if re.search(r"https?://", assets_css):
        fail("site.css references an external URL")
    if "<script" in assets_css.lower():
        fail("site.css contains a script")


def fetch(url: str) -> str:
    try:
        with urlopen(url, timeout=5) as response:
            if response.status != 200:
                fail(f"{url} returned {response.status}")
            content_type = response.headers.get("Content-Type", "")
            body = response.read().decode("utf-8")
    except URLError as error:
        fail(f"{url} failed: {error}")
    else:
        if "text/html" in content_type and "<html" not in body.lower():
            fail(f"{url} is not an HTML document")
        return body
    return ""


def inspect_page(href: str, page: str, pages_html: dict, preview: bool) -> None:
    lowered = page.lower()
    if "<script" in lowered or "<iframe" in lowered:
        fail(f"{href} contains a script or frame")
    if preview:
        if "noindex" not in lowered:
            fail(f"{href} is missing the noindex marker")
        if "development placeholder" not in lowered and "开发占位页" not in page:
            fail(f"{href} is missing the placeholder banner")
    else:
        if "noindex" in lowered or 'class="banner"' in page:
            fail(f"{href} still contains a preview banner or noindex marker")
        for marker in UNPUBLISHED_MARKERS:
            if marker in page:
                fail(f"{href} still contains internal review text: {marker}")
        if "do not publish" in lowered or "不要公开发布" in page:
            fail(f"{href} still contains a do-not-publish notice")
    if "developer@yunostudio.cc" not in page or "mailto:developer@yunostudio.cc" not in page:
        fail(f"{href} is missing the contact email link")
    if "Legal name" in page or "法定姓名" in page:
        fail(f"{href} still displays a legal-name field")
    if "Yuno Studio" in page:
        fail(f"{href} still displays Yuno Studio as the page brand")
    lang = "zh" if href.startswith("/zh/") else "en"
    if CONFIRMED_EFFECTIVE_DATES[lang] not in page:
        fail(f"{href} does not show {CONFIRMED_EFFECTIVE_DATES[lang]}")
    if CONFIRMED_UPDATED_DATES[lang] not in page:
        fail(f"{href} does not show {CONFIRMED_UPDATED_DATES[lang]}")
    for link in re.findall(r'href="([^"]+)"', page):
        if link.startswith("mailto:developer@yunostudio.cc"):
            continue
        if link in ALLOWED_EXTERNAL:
            continue
        if link.startswith("http://") or link.startswith("https://") or link.startswith("//"):
            fail(f"{href} links to an external URL: {link}")
        if link.startswith("/assets/"):
            continue
        normalized = link.rstrip("/") or "/"
        if normalized not in pages_html:
            fail(f"{href} links to an unknown page: {link}")
    if "/embed/" in page:
        fail(f"{href} links into the in-app embed presentation")
    page_id = href.rstrip("/").split("/")[-1]
    counterpart = f"/zh/daymoss/{page_id}" if lang == "en" else f"/daymoss/{page_id}"
    if f'href="{counterpart}"' not in page:
        fail(f"{href} does not link to {counterpart}")
    for sibling in ("privacy", "terms", "support"):
        sibling_href = f"/zh/daymoss/{sibling}" if lang == "zh" else f"/daymoss/{sibling}"
        if f'href="{sibling_href}"' not in page:
            fail(f"{href} does not link to {sibling_href}")


def inspect_embed_page(href: str, page: str, pages: list, preview: bool) -> None:
    lowered = page.lower()
    if "<script" in lowered or "<iframe" in lowered or "javascript:" in lowered:
        fail(f"{href} contains a script or frame")
    if 'onload=' in lowered or 'onerror=' in lowered:
        fail(f"{href} contains an inline event handler")
    source = next(item for item in pages if embed_href_for(item) == href)
    if preview:
        if "noindex" not in lowered:
            fail(f"{href} is missing the noindex marker")
        if "development placeholder" not in lowered and "开发占位页" not in page:
            fail(f"{href} is missing the placeholder banner")
    else:
        if "noindex" in lowered or 'class="banner"' in page:
            fail(f"{href} still contains a preview banner or noindex marker")
        for marker in UNPUBLISHED_MARKERS:
            if marker in page:
                fail(f"{href} still contains internal review text: {marker}")
        if "do not publish" in lowered or "不要公开发布" in page:
            fail(f"{href} still contains a do-not-publish notice")
    for chrome in ('class="brand"', 'class="product"', 'class="docs"', 'class="top"', 'class="foot"'):
        if chrome in page:
            fail(f"{href} still contains public-site chrome: {chrome}")
    if "developer@yunostudio.cc" not in page or "mailto:developer@yunostudio.cc" not in page:
        fail(f"{href} is missing the contact email link")
    if "Legal name" in page or "法定姓名" in page:
        fail(f"{href} still displays a legal-name field")
    if "Yuno Studio" in page:
        fail(f"{href} still displays Yuno Studio as the page brand")
    lang = source["lang"]
    if CONFIRMED_EFFECTIVE_DATES[lang] not in page:
        fail(f"{href} does not show {CONFIRMED_EFFECTIVE_DATES[lang]}")
    if CONFIRMED_UPDATED_DATES[lang] not in page:
        fail(f"{href} does not show {CONFIRMED_UPDATED_DATES[lang]}")
    if f'<html lang="{"zh-Hans" if lang == "zh" else "en"}">' not in page:
        fail(f"{href} has the wrong document language")
    headings = re.findall(r"<h([1-6])\b[^>]*>(.*?)</h\1>", page, re.S)
    if len(headings) < 2 or headings[0][0] != "1" or any(level != "2" for level, _ in headings[1:]):
        fail(f"{href} heading hierarchy is not one h1 followed by h2 sections")
    if headings[0][1].strip() != source["title"]:
        fail(f"{href} document title is {headings[0][1]!r}, expected {source['title']!r}")
    public_href = source["href"]
    if page.count(f'href="{public_href}"') != 1 or f'rel="canonical" href="{public_href}"' not in page:
        fail(f"{href} must canonicalize once to {public_href}")
    counterpart = embed_href_for({"lang": "zh" if lang == "en" else "en", "id": source["id"]})
    if f'href="{counterpart}"' not in page:
        fail(f"{href} does not link to {counterpart}")
    if 'aria-label="Language"' not in page and 'aria-label="语言"' not in page:
        fail(f"{href} is missing the language switch")
    for link in re.findall(r'href="([^"]+)"', page):
        if link.startswith("mailto:developer@yunostudio.cc"):
            continue
        if link in ALLOWED_EXTERNAL:
            continue
        if link.startswith("/assets/"):
            continue
        if link == public_href:
            continue
        normalized = link.rstrip("/") or "/"
        if normalized not in EMBED:
            fail(f"{href} links to an unknown page: {link}")
    for sibling in ("privacy", "terms", "support"):
        sibling_href = f"/zh/daymoss/embed/{sibling}" if lang == "zh" else f"/daymoss/embed/{sibling}"
        if f'href="{sibling_href}"' not in page:
            fail(f"{href} does not link to {sibling_href}")


def embed_href_for(page: dict) -> str:
    if page["lang"] == "en":
        return f"/daymoss/embed/{page['id']}"
    return f"/zh/daymoss/embed/{page['id']}"


def assert_parallel_sections(pages_html: dict) -> None:
    for page_id in ("privacy", "terms", "support"):
        english = re.findall(r"<h2\b", pages_html[f"/daymoss/{page_id}"])
        chinese = re.findall(r"<h2\b", pages_html[f"/zh/daymoss/{page_id}"])
        if len(english) != len(chinese):
            fail(
                f"{page_id} has {len(english)} English sections and {len(chinese)} Chinese sections"
            )


def assert_same_prose(pages_html: dict) -> None:
    for href in EXPECTED:
        embed = href.replace("/daymoss/", "/daymoss/embed/", 1)
        if prose_text(pages_html[href]) != prose_text(pages_html[embed]):
            fail(f"{embed} prose differs from {href}")


def prose_text(page: str) -> str:
    match = re.search(r'<div class="prose">(.*?)</div>', page, re.S)
    if match is None:
        fail("a page is missing its prose")
    text = re.sub(r'\s+href="[^"]*"', "", match.group(1))
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text
