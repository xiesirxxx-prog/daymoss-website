#!/usr/bin/env python3
"""Build the Daymoss legal site from Markdown.

Preview builds keep the development placeholder and are not for publication.
`python3 build.py --release` refuses to write a site while any page is still
marked placeholder: true.
"""

from __future__ import annotations

import html
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONTENT = ROOT / "content"
ASSETS = ROOT / "assets"
DIST = ROOT / "dist"

PAGES = ("privacy", "terms", "support")
CONFIRMED_EFFECTIVE_DATES = {
    "en": "November 4, 2026",
    "zh": "2026 年 11 月 4 日",
}
CONFIRMED_UPDATED_DATES = {
    "en": "November 5, 2026",
    "zh": "2026 年 11 月 5 日",
}
FACT_KEYS = ("effective_date", "updated_date", "contact_email")
UNPUBLISHED_MARKERS = ("PRE-PUBLICATION", "发布前待确认")
FIELD_LABELS = {
    "en": {
        "effective_date": "Original effective date",
        "updated_date": "Last updated",
        "contact_email": "Contact email",
        "empty": {
            "effective_date": "[Original effective date]",
            "updated_date": "[Last updated]",
            "contact_email": "[Contact email]",
        },
        "banner": "Development placeholder. Do not publish this page.",
        "other_lang": "中文",
        "language_nav": "Language",
        "html_lang": "en",
    },
    "zh": {
        "effective_date": "生效日期",
        "updated_date": "最后更新",
        "contact_email": "联系邮箱",
        "empty": {
            "effective_date": "[生效日期]",
            "updated_date": "[最后更新]",
            "contact_email": "[联系邮箱]",
        },
        "banner": "开发占位页。不要公开发布本页。",
        "other_lang": "English",
        "language_nav": "语言",
        "html_lang": "zh-Hans",
    },
}


def fail(message: str) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(1)


def parse_document(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        fail(f"{path} is missing front matter")
    end = text.find("\n---\n", 4)
    if end < 0:
        fail(f"{path} front matter is not closed")
    meta = {}
    for line in text[4:end].splitlines():
        if not line.strip():
            continue
        if ":" not in line:
            fail(f"{path} has an unreadable front-matter line: {line}")
        key, value = line.split(":", 1)
        meta[key.strip()] = value.strip().strip('"')
    if meta.get("placeholder") not in {"true", "false"}:
        fail(f"{path} must set placeholder: true or placeholder: false")
    meta["placeholder"] = meta["placeholder"] == "true"
    meta["body"] = text[end + 5 :].strip()
    meta["source"] = path
    return meta


def load_pages() -> list:
    pages = []
    for lang in ("en", "zh"):
        for page_id in PAGES:
            path = CONTENT / lang / f"{page_id}.md"
            if not path.is_file():
                fail(f"missing content file: {path.relative_to(ROOT)}")
            doc = parse_document(path)
            if doc.get("id") != page_id or doc.get("lang") != lang:
                fail(f"{path} id/lang does not match its path")
            for key in ("title", "contact_email", "effective_date", "updated_date"):
                if key not in doc:
                    fail(f"{path} is missing {key}")
            doc["href"] = page_href(lang, page_id)
            pages.append(doc)
    if len(pages) != 6:
        fail("expected exactly six pages")
    return pages


def page_href(lang: str, page_id: str) -> str:
    if lang == "en":
        return f"/daymoss/{page_id}"
    if lang == "zh":
        return f"/zh/daymoss/{page_id}"
    fail(f"unknown language: {lang}")
    return ""


def embed_href(lang: str, page_id: str) -> str:
    if lang == "en":
        return f"/daymoss/embed/{page_id}"
    if lang == "zh":
        return f"/zh/daymoss/embed/{page_id}"
    fail(f"unknown language: {lang}")
    return ""


def rewrite_embed_links(markup: str) -> str:
    """Point in-body legal links at the embed presentation. The Markdown stays unchanged."""
    for page_id in PAGES:
        for lang in ("zh", "en"):
            markup = markup.replace(
                f'href="{page_href(lang, page_id)}"',
                f'href="{embed_href(lang, page_id)}"',
            )
    return markup


def release_errors(pages: list) -> list:
    errors = []
    for page in pages:
        if page["placeholder"]:
            errors.append(f"{page['source'].relative_to(ROOT)} is still placeholder: true")
        expected_date = CONFIRMED_EFFECTIVE_DATES[page["lang"]]
        if page["effective_date"] != expected_date:
            errors.append(
                f"{page['href']} effective date is {page['effective_date']!r}, expected {expected_date!r}"
            )
        expected_updated = CONFIRMED_UPDATED_DATES[page["lang"]]
        if page["updated_date"] != expected_updated:
            errors.append(
                f"{page['href']} last updated date is {page['updated_date']!r}, expected {expected_updated!r}"
            )
        if page["contact_email"] != "developer@yunostudio.cc":
            errors.append(f"{page['href']} contact email is not developer@yunostudio.cc")
        for marker in UNPUBLISHED_MARKERS:
            if marker in page["body"]:
                errors.append(f"{page['href']} still contains {marker}")
    dates = {page["effective_date"] for page in pages}
    if dates != set(CONFIRMED_EFFECTIVE_DATES.values()):
        errors.append(f"effective dates are not the confirmed pair: {sorted(dates)}")
    updated = {page["updated_date"] for page in pages}
    if updated != set(CONFIRMED_UPDATED_DATES.values()):
        errors.append(f"last-updated dates are not the confirmed pair: {sorted(updated)}")
    return errors


def render_markdown(source: str) -> str:
    lines = source.replace("\r\n", "\n").split("\n")
    blocks = []
    paragraph = []
    list_items = []
    list_kind = None

    def flush_paragraph() -> None:
        nonlocal paragraph
        if paragraph:
            blocks.append(("p", inline(" ".join(paragraph))))
            paragraph = []

    def flush_list() -> None:
        nonlocal list_items, list_kind
        if list_items:
            blocks.append((list_kind, list_items[:]))
            list_items = []
            list_kind = None

    for raw in lines:
        line = raw.rstrip()
        if not line.strip():
            flush_paragraph()
            flush_list()
            continue
        if line.startswith("> "):
            flush_paragraph()
            flush_list()
            blocks.append(("quote", inline(line[2:])))
            continue
        if line.startswith("## "):
            flush_paragraph()
            flush_list()
            blocks.append(("h2", inline(line[3:])))
            continue
        unordered = re.match(r"^[-*] ", line)
        ordered = re.match(r"^\d+\. ", line)
        if unordered or ordered:
            flush_paragraph()
            kind = "ul" if unordered else "ol"
            if list_kind not in (None, kind):
                flush_list()
            list_kind = kind
            list_items.append(inline(re.sub(r"^([-*]|\d+\.) ", "", line)))
            continue
        flush_list()
        paragraph.append(line.strip())
    flush_paragraph()
    flush_list()

    parts = []
    for kind, value in blocks:
        if kind == "p":
            parts.append(f"<p>{value}</p>")
        elif kind == "quote":
            parts.append(f"<blockquote><p>{value}</p></blockquote>")
        elif kind == "h2":
            parts.append(f"<h2>{value}</h2>")
        else:
            items = "".join(f"<li>{item}</li>" for item in value)
            parts.append(f"<{kind}>{items}</{kind}>")
    return "\n".join(parts)


def inline(text: str) -> str:
    escaped = html.escape(text, quote=True)
    escaped = re.sub(
        r"\[([^\]]+)\]\(([^)\s]+)\)",
        lambda match: f'<a href="{html.escape(match.group(2), quote=True)}">{match.group(1)}</a>',
        escaped,
    )
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)
    return escaped


def field_html(page: dict, key: str) -> str:
    labels = FIELD_LABELS[page["lang"]]
    value = page[key]
    label = html.escape(labels[key])
    if key == "contact_email" and value:
        shown = f'<a href="mailto:{html.escape(value, quote=True)}">{html.escape(value)}</a>'
    elif value:
        shown = html.escape(value)
    else:
        shown = f'<span class="slot-empty">{html.escape(labels["empty"][key])}</span>'
    return f"<div><dt>{label}</dt><dd>{shown}</dd></div>"


def render_page(page: dict, pages: list) -> str:
    labels = FIELD_LABELS[page["lang"]]
    others = [item for item in pages if item["lang"] == page["lang"]]
    nav = []
    for item in others:
        current = ' aria-current="page"' if item["id"] == page["id"] else ""
        nav.append(
            f'<a href="{item["href"]}"{current}>{html.escape(item["title"])}</a>'
        )
    other_lang = "zh" if page["lang"] == "en" else "en"
    counterpart = next(
        item["href"] for item in pages if item["lang"] == other_lang and item["id"] == page["id"]
    )
    banner = ""
    robots = ""
    title = html.escape(page["title"])
    if page["placeholder"]:
        banner = f'<p class="banner" role="note">{html.escape(labels["banner"])}</p>'
        robots = '<meta name="robots" content="noindex, nofollow">'
        title = f"{title} — Placeholder"
    facts = "\n".join(field_html(page, key) for key in FACT_KEYS)
    return f"""<!DOCTYPE html>
<html lang="{labels["html_lang"]}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  {robots}
  <title>{title} — Daymoss</title>
  <link rel="stylesheet" href="/assets/site.css">
  <link rel="icon" href="/assets/favicon.svg" type="image/svg+xml">
</head>
<body>
  <div class="frame">
    <header class="top">
      <p class="brand">Daymoss</p>
      <nav class="lang" aria-label="{html.escape(labels["language_nav"])}">
        <a href="{page["href"]}" aria-current="page">{ "English" if page["lang"] == "en" else "中文" }</a>
        <a href="{counterpart}" lang="{FIELD_LABELS[other_lang]["html_lang"]}">{html.escape(labels["other_lang"])}</a>
      </nav>
    </header>
    <main class="sheet">
      <p class="product">Daymoss</p>
      <nav class="docs" aria-label="Daymoss">
        {"".join(nav)}
      </nav>
      <h1>{html.escape(page["title"])}</h1>
      {banner}
      <dl class="facts">
        {facts}
      </dl>
      <div class="prose">
        {render_markdown(page["body"])}
      </div>
    </main>
    <footer class="foot">
      <p>Daymoss · <a href="mailto:developer@yunostudio.cc">developer@yunostudio.cc</a></p>
    </footer>
  </div>
</body>
</html>
"""


def render_embed_page(page: dict, pages: list) -> str:
    """In-app presentation of the same page. The native navigation bar supplies the visible title."""
    labels = FIELD_LABELS[page["lang"]]
    other_lang = "zh" if page["lang"] == "en" else "en"
    counterpart = next(
        embed_href(item["lang"], item["id"])
        for item in pages
        if item["lang"] == other_lang and item["id"] == page["id"]
    )
    current = embed_href(page["lang"], page["id"])
    banner = ""
    robots = ""
    title = html.escape(page["title"])
    if page["placeholder"]:
        banner = f'<p class="banner" role="note">{html.escape(labels["banner"])}</p>'
        robots = '<meta name="robots" content="noindex, nofollow">'
        title = f"{title} — Placeholder"
    current_label = "English" if page["lang"] == "en" else "中文"
    facts = "\n".join(field_html(page, key) for key in FACT_KEYS)
    prose = rewrite_embed_links(render_markdown(page["body"]))
    return f"""<!DOCTYPE html>
<html lang="{labels["html_lang"]}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  {robots}
  <title>{title} — Daymoss</title>
  <link rel="canonical" href="{page["href"]}">
  <link rel="stylesheet" href="/assets/site.css">
  <link rel="icon" href="/assets/favicon.svg" type="image/svg+xml">
</head>
<body class="embed">
  <div class="embed-frame">
    <main>
      <h1 class="document-title">{html.escape(page["title"])}</h1>
      <nav class="lang" aria-label="{html.escape(labels["language_nav"])}">
        <a href="{current}" aria-current="page">{current_label}</a>
        <a href="{counterpart}" lang="{FIELD_LABELS[other_lang]["html_lang"]}">{html.escape(labels["other_lang"])}</a>
      </nav>
      {banner}
      <dl class="facts">
        {facts}
      </dl>
      <div class="prose">
        {prose}
      </div>
    </main>
  </div>
</body>
</html>
"""


def write_site(pages: list, release: bool) -> None:
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir()
    shutil.copytree(ASSETS, DIST / "assets")
    for page in pages:
        destination = DIST / page["href"].lstrip("/") / "index.html"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(render_page(page, pages), encoding="utf-8")
        embed_destination = DIST / embed_href(page["lang"], page["id"]).lstrip("/") / "index.html"
        embed_destination.parent.mkdir(parents=True, exist_ok=True)
        embed_destination.write_text(render_embed_page(page, pages), encoding="utf-8")
    if release:
        (DIST / "robots.txt").write_text("User-agent: *\nAllow: /\n", encoding="utf-8")
        (DIST / "CNAME").write_text("yunostudio.cc\n", encoding="utf-8")
    else:
        (DIST / "robots.txt").write_text("User-agent: *\nDisallow: /\n", encoding="utf-8")
        (DIST / "PLACEHOLDER_DO_NOT_PUBLISH.txt").write_text(
            "This directory is a local preview. It contains development placeholder pages.\n"
            "Do not upload it and do not point yunostudio.cc at it.\n",
            encoding="utf-8",
        )
    print(f"wrote {DIST}")


def main() -> None:
    release = "--release" in sys.argv
    check = "--check" in sys.argv
    release_check = "--release-check" in sys.argv
    copy_check = "--check-release-copy" in sys.argv
    chosen = [name for name, enabled in (
        ("--release", release),
        ("--check", check),
        ("--release-check", release_check),
        ("--check-release-copy", copy_check),
    ) if enabled]
    if len(chosen) > 1:
        fail("use only one of " + ", ".join(chosen))
    if copy_check:
        from check_site import check_release_copy

        check_release_copy(ROOT)
        return
    pages = load_pages()
    publishing = release or release_check
    if publishing:
        errors = release_errors(pages)
        if errors:
            fail("release build refused:\n- " + "\n- ".join(errors))
    write_site(pages, release=publishing)
    if check:
        from check_site import check_site

        check_site(DIST, pages)
    if release_check:
        from check_site import check_release_site

        check_release_site(DIST, pages)


if __name__ == "__main__":
    main()
