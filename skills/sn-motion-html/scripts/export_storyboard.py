#!/usr/bin/env python3
"""Export a storyboard from the project's own story data.

Reads content/story.json and writes two review documents under exports/: a
Markdown storyboard to edit and a static HTML storyboard to read or print.
Both list the same shots in the same order with the same copy, so the whole
story can be reviewed at once instead of by scrolling the story page.

The story data stays the single source of truth: edit content/story.json and
export again rather than editing the exported files.
"""

from __future__ import annotations

import argparse
import posixpath
import re
import sys
from html import escape
from pathlib import Path, PurePosixPath
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from project_model import (  # noqa: E402
    LANGS,
    STORYBOARD_DIR,
    STORYBOARD_HTML,
    STORYBOARD_MD,
    ProjectError,
    chapters_of,
    load_story,
    resolve_media_mode,
    shot_of,
    validate_story,
)

CJK = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]")
SAFE_PROTOCOLS = ("http://", "https://")
HTML_LANG = {"zh": "zh-CN", "en": "en"}

STRINGS: dict[str, dict[str, str]] = {
    "zh": {
        "docTitle": "分镜稿",
        "shotCount": "{count} 个镜头",
        "source": "内容源：content/story.json",
        "shotNo": "镜号",
        "chapterId": "章节 ID",
        "navLabel": "导航标签",
        "intent": "镜头意图",
        "framing": "构图与景别",
        "motion": "运动意图（尚未生成）",
        "tags": "标签",
        "sources": "来源",
        "note": "说明",
        "generated": "本文件由 content/story.json 生成。修改内容请改故事数据后重新导出，不要直接编辑这里。",
        "motionNote": "镜头意图与运动意图只是拍摄或动画的说明，本技能不会据此生成视频。",
        "missing": "缺少静帧：{path}",
    },
    "en": {
        "docTitle": "Storyboard",
        "shotCount": "{count} shot(s)",
        "source": "Source of truth: content/story.json",
        "shotNo": "Shot",
        "chapterId": "Chapter ID",
        "navLabel": "Nav label",
        "intent": "Shot intent",
        "framing": "Framing",
        "motion": "Motion note (not generated)",
        "tags": "Tags",
        "sources": "Sources",
        "note": "Note",
        "generated": "Generated from content/story.json. Edit the story data and export again instead of editing this file.",
        "motionNote": "Shot intent and motion notes describe filming or animation only; this skill never generates video from them.",
        "missing": "missing still: {path}",
    },
}


class ExportError(RuntimeError):
    """A problem that must stop the export before anything is written."""


def detect_lang(story: dict[str, Any], chapters: list[dict[str, Any]]) -> str:
    """Resolve the document language, mirroring the page's own fallback."""
    meta = story.get("meta") if isinstance(story.get("meta"), dict) else {}
    declared = meta.get("lang")
    if declared in LANGS:
        return str(declared)
    parts: list[str] = [meta.get("title"), meta.get("subtitle"), meta.get("kicker")]
    for chapter in chapters:
        parts.extend([chapter.get("title"), chapter.get("label"), chapter.get("eyebrow")])
        paragraphs = chapter.get("paragraphs")
        if isinstance(paragraphs, list):
            parts.extend(str(item) for item in paragraphs)
    return "zh" if CJK.search(" ".join(str(part) for part in parts if part)) else "en"


def media_relative(still: str) -> str:
    """The still's path as seen from the exports directory."""
    return posixpath.relpath(
        PurePosixPath(still).as_posix(), PurePosixPath(STORYBOARD_DIR).as_posix()
    )


def safe_href(raw: Any) -> str | None:
    """Only http(s) sources become links, exactly as the story page does."""
    text = str(raw or "").strip()
    if text.lower().startswith(SAFE_PROTOCOLS):
        return text
    return None


def paragraph_text(chapter: dict[str, Any]) -> list[str]:
    paragraphs = chapter.get("paragraphs")
    if not isinstance(paragraphs, list):
        return []
    return [str(item).strip() for item in paragraphs if str(item).strip()]


def tag_text(chapter: dict[str, Any]) -> list[str]:
    tags = chapter.get("tags")
    if not isinstance(tags, list):
        return []
    return [str(item).strip() for item in tags if str(item).strip()]


def chapter_heading(chapter: dict[str, Any], index: int) -> str:
    return str(chapter.get("title") or chapter.get("label") or f"Shot {index + 1}").strip()


def chapter_subtitle(chapter: dict[str, Any]) -> str:
    parts = [
        str(chapter.get("eyebrow") or "").strip(),
        str(chapter.get("subtitle") or "").strip(),
    ]
    return " · ".join(part for part in parts if part)


def meta_rows(chapter: dict[str, Any], strings: dict[str, str]) -> list[tuple[str, str]]:
    """Label/value pairs for one shot, in a fixed order.

    The chapter ID is always listed: it is the shot's stable identity and the
    key back into the story data. The navigation label appears only when it
    differs from the title, so it is not repeated for every shot. The shot
    direction follows, and stays empty when the story declares none.
    """
    rows: list[tuple[str, str]] = [(strings["chapterId"], str(chapter.get("id") or ""))]
    label = str(chapter.get("label") or "").strip()
    if label and label != str(chapter.get("title") or "").strip():
        rows.append((strings["navLabel"], label))
    shot = shot_of(chapter)
    labels = (
        ("intent", strings["intent"]),
        ("framing", strings["framing"]),
        ("motionNote", strings["motion"]),
    )
    rows.extend((label_text, shot[key]) for key, label_text in labels if key in shot)
    return rows


def sources_of(story: dict[str, Any]) -> list[tuple[str, str]]:
    sources = story.get("sources")
    if not isinstance(sources, list):
        return []
    found: list[tuple[str, str]] = []
    for source in sources:
        if not isinstance(source, dict):
            continue
        label = str(source.get("label") or source.get("url") or "").strip()
        if label:
            found.append((label, str(source.get("url") or "").strip()))
    return found


def build_markdown(
    story: dict[str, Any], chapters: list[dict[str, Any]], strings: dict[str, str], lang: str
) -> str:
    meta = story.get("meta") if isinstance(story.get("meta"), dict) else {}
    title = str(meta.get("title") or "").strip()
    label_sep = "：" if lang == "zh" else ": "
    tag_sep = "、" if lang == "zh" else ", "
    lines: list[str] = [f"# {title} · {strings['docTitle']}", ""]

    deck = [strings["shotCount"].format(count=len(chapters)), strings["source"]]
    lines.extend([" · ".join(deck), ""])
    if str(meta.get("note") or "").strip():
        lines.extend([f"> {strings['note']}{label_sep}{str(meta['note']).strip()}", ""])
    lines.extend([f"> {strings['motionNote']}", ""])

    for index, chapter in enumerate(chapters):
        still = str(chapter.get("still") or "")
        # Brackets would end the image alt text early; the heading right above
        # already names the shot, so the alt text only has to stay valid.
        alt = f"{index + 1:02d} {chapter_heading(chapter, index)}".replace("[", "(").replace("]", ")")
        lines.extend(["---", "", f"## {index + 1:02d} · {chapter_heading(chapter, index)}", ""])
        subtitle = chapter_subtitle(chapter)
        if subtitle:
            lines.extend([f"*{subtitle}*", ""])
        lines.extend([f"![{alt}]({media_relative(still)})", ""])
        for label_text, value in meta_rows(chapter, strings):
            lines.append(f"- **{label_text}**{label_sep}{value}")
        lines.append("")
        for paragraph in paragraph_text(chapter):
            lines.extend([paragraph, ""])
        tags = tag_text(chapter)
        if tags:
            lines.extend([f"**{strings['tags']}**{label_sep}{tag_sep.join(tags)}", ""])

    sources = sources_of(story)
    if sources:
        lines.extend(["---", "", f"## {strings['sources']}", ""])
        for label, url in sources:
            href = safe_href(url)
            lines.append(f"- [{label}]({href})" if href else f"- {label}")
        lines.append("")

    lines.extend(["---", "", f"*{strings['generated']}*", ""])
    return "\n".join(lines)


STORYBOARD_CSS = """
:root {
  --paper: #f2ecdf; --ink: #211f1b; --muted: #716a61; --accent: #b45438;
  --line: #211f1b2e; --panel: #ffffff70;
  --display: Georgia, "Songti SC", "Noto Serif CJK SC", "Microsoft YaHei", serif;
  --body: Inter, ui-sans-serif, system-ui, "PingFang SC", "Microsoft YaHei", sans-serif;
  --mono: ui-monospace, SFMono-Regular, Consolas, monospace;
}
html[data-style="anime"] { --paper: #fff7e9; --ink: #172238; --muted: #5f6c83; --accent: #ed5f76;
  --display: "Arial Rounded MT Bold", "Hiragino Maru Gothic ProN", system-ui, sans-serif; }
html[data-style="cinematic"] { --paper: #eee7da; --ink: #211f1b; --muted: #6e675d; --accent: #a64f36; }
html[data-style="cgi"] { --paper: #e7eef1; --ink: #12232c; --muted: #566a74; --accent: #258095;
  --display: "Avenir Next", Inter, ui-sans-serif, system-ui, sans-serif; }
* { box-sizing: border-box; }
body { margin: 0; padding: clamp(28px, 6vw, 76px) clamp(20px, 5vw, 56px) 80px;
  background: var(--paper); color: var(--ink); font-family: var(--body); line-height: 1.6; }
main, .sb-head, .sb-foot { max-width: 1100px; margin: 0 auto; }
.sb-head { padding-bottom: 26px; border-bottom: 3px solid var(--ink); }
.sb-kicker { margin: 0 0 8px; color: var(--accent); font-size: .72rem; font-weight: 800;
  letter-spacing: .16em; text-transform: uppercase; }
.sb-head h1 { margin: 0; font: 700 clamp(1.9rem, 4.4vw, 3.1rem)/1.02 var(--display); letter-spacing: -.03em; }
.sb-sub { margin: 10px 0 0; color: var(--muted); font-size: .95rem; }
.sb-meta { margin: 16px 0 0; color: var(--muted); font: 600 .74rem/1.7 var(--mono); }
.sb-note { margin: 14px 0 0; padding-left: 14px; border-left: 3px solid var(--accent);
  color: var(--muted); font-size: .86rem; }
.sb-advisory { margin: 18px 0 0; color: var(--muted); font-size: .78rem; }
.sb-shot { padding: 34px 0 6px; border-bottom: 1px solid var(--line); break-inside: avoid; page-break-inside: avoid; }
.sb-shot__head { display: flex; align-items: baseline; gap: 16px; }
.sb-shot__no { color: var(--accent); font: 800 1.05rem/1 var(--mono); letter-spacing: .06em; }
.sb-shot h2 { margin: 0; font: 700 clamp(1.3rem, 2.4vw, 1.85rem)/1.15 var(--display); letter-spacing: -.02em; }
.sb-shot__deck { margin: 6px 0 0; color: var(--muted); font-size: .8rem; }
.sb-grid { display: grid; grid-template-columns: minmax(280px, 46%) 1fr; gap: clamp(20px, 3.5vw, 40px);
  align-items: start; margin-top: 18px; }
.sb-figure { margin: 0; }
.sb-figure img { display: block; width: 100%; height: auto; border-radius: 3px;
  border: 1px solid var(--line); background: var(--panel); }
.sb-figure figcaption { margin-top: 8px; color: var(--muted); font: 600 .68rem/1.5 var(--mono); overflow-wrap: anywhere; }
.sb-rows { display: grid; grid-template-columns: max-content 1fr; gap: 8px 16px; margin: 0 0 18px; }
.sb-rows dt { color: var(--accent); font-size: .68rem; font-weight: 800; letter-spacing: .1em; text-transform: uppercase; }
.sb-rows dd { margin: 0; font-size: .92rem; }
.sb-copy p { margin: 0 0 .7em; }
.sb-copy p:last-child { margin-bottom: 0; }
.sb-tags { display: flex; flex-wrap: wrap; gap: 6px 14px; margin: 18px 0 0; padding: 0; list-style: none; }
.sb-tags li { padding-top: 5px; border-top: 2px solid var(--accent); color: var(--muted);
  font-size: .66rem; font-weight: 750; letter-spacing: .05em; text-transform: uppercase; }
.sb-foot { margin-top: 44px; padding-top: 22px; border-top: 3px solid var(--ink); color: var(--muted); font-size: .84rem; }
.sb-foot h2 { margin: 0 0 10px; color: var(--ink); font: 700 1.05rem/1.2 var(--display); }
.sb-foot ol { margin: 0; padding-left: 20px; }
.sb-foot li { margin: 5px 0; }
.sb-generated { margin: 22px 0 0; font-size: .74rem; }
@media (max-width: 820px) {
  .sb-grid { grid-template-columns: 1fr; }
  .sb-rows { grid-template-columns: 1fr; gap: 2px; }
  .sb-rows dd { margin-bottom: 10px; }
}
@media print {
  body { padding: 0; background: #fff; }
  /* Keep the still beside its copy on paper as well. At paper width the screen
     breakpoint would stack them, and one shot would then spend a whole page,
     which defeats reviewing the whole sequence at once. */
  .sb-grid { grid-template-columns: minmax(210px, 40%) 1fr; gap: 18px; }
  .sb-rows { grid-template-columns: max-content 1fr; gap: 6px 12px; }
  .sb-rows dd { margin-bottom: 0; }
  .sb-shot { padding: 14px 0; }
  .sb-figure img { border: 0; }
  a { color: inherit; text-decoration: none; }
}
"""


def build_html(story: dict[str, Any], chapters: list[dict[str, Any]], strings: dict[str, str], lang: str) -> str:
    meta = story.get("meta") if isinstance(story.get("meta"), dict) else {}
    title = str(meta.get("title") or "").strip()
    deck = " · ".join(
        [strings["shotCount"].format(count=len(chapters)), strings["source"]]
    )
    parts: list[str] = [
        "<!doctype html>",
        f'<html lang="{HTML_LANG[lang]}" data-style="{escape(str(meta.get("style") or "cinematic"), quote=True)}">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"<title>{escape(title)} · {escape(strings['docTitle'])}</title>",
        f"<style>{STORYBOARD_CSS}</style>",
        "</head>",
        "<body>",
        '<header class="sb-head">',
    ]
    if str(meta.get("kicker") or "").strip():
        parts.append(f'<p class="sb-kicker">{escape(str(meta["kicker"]).strip())}</p>')
    parts.append(f"<h1>{escape(title)} · {escape(strings['docTitle'])}</h1>")
    if str(meta.get("subtitle") or "").strip():
        parts.append(f'<p class="sb-sub">{escape(str(meta["subtitle"]).strip())}</p>')
    parts.append(f'<p class="sb-meta">{escape(deck)}</p>')
    if str(meta.get("note") or "").strip():
        parts.append(f'<p class="sb-note">{escape(str(meta["note"]).strip())}</p>')
    parts.append(f'<p class="sb-advisory">{escape(strings["motionNote"])}</p>')
    parts.extend(["</header>", "<main>"])

    for index, chapter in enumerate(chapters):
        still = str(chapter.get("still") or "")
        shot_number = f"{index + 1:02d}"
        alt = f"{shot_number} {chapter_heading(chapter, index)}"
        parts.append(f'<article class="sb-shot" id="shot-{shot_number}">')
        parts.append('<div class="sb-shot__head">')
        parts.append(f'<span class="sb-shot__no">{shot_number}</span>')
        parts.append("<div>")
        parts.append(f"<h2>{escape(chapter_heading(chapter, index))}</h2>")
        subtitle = chapter_subtitle(chapter)
        if subtitle:
            parts.append(f'<p class="sb-shot__deck">{escape(subtitle)}</p>')
        parts.extend(["</div>", "</div>"])
        parts.append('<div class="sb-grid">')
        parts.append('<figure class="sb-figure">')
        parts.append(
            f'<img src="{escape(media_relative(still), quote=True)}" alt="{escape(alt, quote=True)}" loading="lazy">'
        )
        # The caption carries the shot number and the chapter ID, which is what
        # identifies the shot. The file path stays in the Markdown (where it is
        # needed for editing) and in the img src above, rather than being printed
        # as a long line that breaks mid-filename.
        parts.append(
            f"<figcaption>{escape(strings['shotNo'])} {shot_number} · "
            f"{escape(str(chapter.get('id') or ''))}</figcaption>"
        )
        parts.extend(["</figure>", '<div class="sb-body">'])
        rows = meta_rows(chapter, strings)
        if rows:
            parts.append("<dl class=\"sb-rows\">")
            for label_text, value in rows:
                parts.append(f"<dt>{escape(label_text)}</dt><dd>{escape(value)}</dd>")
            parts.append("</dl>")
        paragraphs = paragraph_text(chapter)
        if paragraphs:
            parts.append('<div class="sb-copy">')
            parts.extend(f"<p>{escape(text)}</p>" for text in paragraphs)
            parts.append("</div>")
        tags = tag_text(chapter)
        if tags:
            parts.append('<ul class="sb-tags">')
            parts.extend(f"<li>{escape(tag)}</li>" for tag in tags)
            parts.append("</ul>")
        parts.extend(["</div>", "</div>", "</article>"])

    parts.append("</main>")
    sources = sources_of(story)
    if sources:
        parts.append('<footer class="sb-foot">')
        parts.append(f"<h2>{escape(strings['sources'])}</h2>")
        parts.append("<ol>")
        for label, url in sources:
            href = safe_href(url)
            if href:
                parts.append(
                    f'<li><a href="{escape(href, quote=True)}" rel="noreferrer">{escape(label)}</a></li>'
                )
            else:
                parts.append(f"<li>{escape(label)}</li>")
        parts.append("</ol>")
        parts.append(f'<p class="sb-generated">{escape(strings["generated"])}</p>')
        parts.append("</footer>")
    else:
        parts.append(f'<footer class="sb-foot"><p class="sb-generated">{escape(strings["generated"])}</p></footer>')
    parts.extend(["</body>", "</html>", ""])
    return "\n".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_root", type=Path)
    args = parser.parse_args()

    root = args.project_root.expanduser().resolve()
    try:
        story = load_story(root)
        mode = resolve_media_mode(story)
        chapters = chapters_of(story)
        problems = validate_story(root, story, mode)
    except ProjectError as exc:
        print(f"FAIL {exc}")
        return 1
    if problems:
        print("FAIL story problems:")
        for problem in problems:
            print(f"- {problem}")
        return 1

    # Every declared still must exist before anything is written: an exported
    # storyboard that points at missing images is a broken deliverable, so this
    # export has no allow-missing option.
    strings_lang = detect_lang(story, chapters)
    strings = STRINGS[strings_lang]
    missing = [
        strings["missing"].format(path=chapter.get("still"))
        for chapter in chapters
        if not (root / str(chapter.get("still"))).is_file()
    ]
    if missing:
        print("FAIL missing media:")
        for item in missing:
            print(f"- {item}")
        return 2

    markdown_path = root / STORYBOARD_MD
    html_path = root / STORYBOARD_HTML
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    existing = [path.name for path in (markdown_path, html_path) if path.exists()]
    markdown_path.write_text(
        build_markdown(story, chapters, strings, strings_lang), encoding="utf-8", newline="\n"
    )
    html_path.write_text(build_html(story, chapters, strings, strings_lang), encoding="utf-8", newline="\n")

    if existing:
        print(f"Overwrote existing export(s): {', '.join(existing)}")
    print(f"Media mode: {mode}")
    print(f"Language: {strings_lang}")
    print(f"Shots: {len(chapters)}")
    print(markdown_path)
    print(html_path)
    print("Edit content/story.json and export again; do not edit the exports by hand.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
