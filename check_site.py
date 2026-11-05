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

from build import CONFIRMED_EFFECTIVE_DATES, UNPUBLISHED_MARKERS, release_errors

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
        inspect_page(href, page, pages_html, preview=True)
    inspect_assets(assets_css)
    print("preview link check passed for 6 pages")


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
        inspect_page(href, page, pages_html, preview=False)
    inspect_assets(assets_css)
    print("release link check passed for 6 pages")


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
        if page["effective_date"] != expected:
            fail(f"{page['href']} date is {page['effective_date']!r}, expected {expected!r}")
    if {page["effective_date"] for page in pages} != set(CONFIRMED_EFFECTIVE_DATES.values()):
        fail("the six pages do not share the confirmed English and Chinese dates")


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
        pages_html = {href: fetch(f"{base}{href}/") for href in EXPECTED}
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
    page_id = href.rstrip("/").split("/")[-1]
    counterpart = f"/zh/daymoss/{page_id}" if lang == "en" else f"/daymoss/{page_id}"
    if f'href="{counterpart}"' not in page:
        fail(f"{href} does not link to {counterpart}")
    for sibling in ("privacy", "terms", "support"):
        sibling_href = f"/zh/daymoss/{sibling}" if lang == "zh" else f"/daymoss/{sibling}"
        if f'href="{sibling_href}"' not in page:
            fail(f"{href} does not link to {sibling_href}")
