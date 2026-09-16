#!/bin/sh
""":"
# 1. Try Unix venv
PYTHON_EXEC="$(dirname "$0")/.venv/bin/python"

# 2. If not found, try Windows venv
if [ ! -f "$PYTHON_EXEC" ]; then
    PYTHON_EXEC="$(dirname "$0")/.venv/Scripts/python"
fi

# 3. If still not found, try system PATH
if [ ! -f "$PYTHON_EXEC" ]; then
    if command -v python3 >/dev/null 2>&1; then
        PYTHON_EXEC="python3"
    elif command -v python >/dev/null 2>&1; then
        PYTHON_EXEC="python"
    else
        echo "gen_gallery: Neither virtualenv nor system Python found." >&2
        exit 1
    fi
fi

exec "$PYTHON_EXEC" "$0" "$@"
"""

# Regenerates gallery.qmd (the "Figures, Tables, and Apps" index) straight from
# the labels and captions already in the chapter .qmd files, so the gallery
# can never drift out of sync with the book. Run it after adding, removing, or
# relabeling any fig-/tbl- chunk or shinylive app section:
#
#   ./gen_gallery.py
#
# It reads chapter order from _quarto.yml, so no chapter list is hardcoded here.

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
QUARTO_YML = ROOT / "_quarto.yml"
OUTPUT = ROOT / "gallery.qmd"
SKIP = {"index.qmd", "gallery.qmd"}

HEADING_RE = re.compile(r'^(#{1,6})\s+(.*)$')
HEADING_ID_RE = re.compile(r'\{#([\w-]+)\}')
SPAN_ID_RE = re.compile(r'^\[\]\{#([\w-]+)\}\s*$')
CHUNK_START_RE = re.compile(r'^```\{(r|shinylive-r)[^}]*\}')
KABLE_CAPTION_RE = re.compile(r'caption\s*=\s*(["\'])(.*?)\1')
# A real chunk option always has exactly one space after "#|" (knitr/quarto
# convention: "#| key: value"). A continuation line of a multi-line quoted
# value is indented further ("#|   more text") to align under the value, and
# must be checked first -- otherwise a continuation that happens to start
# with "Word:" (e.g. captions with "Left: ... / Right: ...") would be
# misparsed as a brand-new option.
OPTION_RE = re.compile(r'^#\| ([\w.-]+):\s*(.*)$')
CONTINUATION_RE = re.compile(r'^#\|\s{2,}(.*)$')
TITLE_RE = re.compile(r'^title:\s*(.+)$', re.M)


def get_chapter_order():
    text = QUARTO_YML.read_text(encoding="utf-8")
    lines = text.splitlines()
    chapters = []
    in_chapters = False
    for line in lines:
        if re.match(r'^\s*chapters:\s*$', line):
            in_chapters = True
            continue
        if in_chapters:
            m = re.match(r'^\s*-\s*(\S+\.qmd)\s*$', line)
            if m:
                chapters.append(m.group(1))
                continue
            if re.match(r'^\s*-\s', line):
                continue  # tolerate other list forms
            if re.match(r'^\S', line) or re.match(r'^\s*\w+:', line):
                break  # dedented to a new top-level/sibling key: chapters block ended
    return [c for c in chapters if c not in SKIP]


def get_title(path):
    text = path.read_text(encoding="utf-8")
    m = TITLE_RE.search(text)
    return m.group(1).strip().strip('"').strip("'") if m else path.stem


def clean_caption(raw):
    raw = raw.strip()
    if not raw:
        return raw
    quote = raw[0] if raw[0] in "\"'" else None
    if quote and raw.endswith(quote):
        raw = raw[1:-1]
        if quote == '"':
            raw = raw.replace('\\\\', '\\')
        else:
            raw = raw.replace("''", "'")
    return raw.strip()


SENTENCE_SPLIT_RE = re.compile(r'(?<=[.!?])\s+(?=[A-Z(])')
APP_HINT_RE = re.compile(r'\b(interactive|app|below|widget)\b', re.IGNORECASE)


def split_sentences(text):
    text = re.sub(r'\s+', ' ', text).strip()
    if not text:
        return []
    return [s.strip() for s in SENTENCE_SPLIT_RE.split(text) if s.strip()]


def pick_app_description(sentences, fallback_paragraph):
    for s in sentences:
        if APP_HINT_RE.search(s):
            return s
    if fallback_paragraph:
        found = split_sentences(fallback_paragraph)
        if found:
            return found[0]
    return None


def strip_heading_text(raw_heading):
    text = raw_heading.lstrip('#').strip()
    text = HEADING_ID_RE.sub('', text).strip()
    return text


def parse_chapter(path):
    title = get_title(path)
    lines = path.read_text(encoding="utf-8").splitlines()
    n = len(lines)

    figs, tbls, apps = [], [], []

    last_heading_raw = ""
    last_heading_id = None
    pending_span_id = None
    paragraph_buffer = []
    last_paragraph = None
    sentences_since_heading = []

    def flush_paragraph():
        nonlocal last_paragraph
        if paragraph_buffer:
            last_paragraph = ' '.join(paragraph_buffer).strip()
            sentences_since_heading.extend(split_sentences(last_paragraph))
            paragraph_buffer.clear()

    i = 0
    while i < n:
        line = lines[i]

        hm = HEADING_RE.match(line)
        if hm:
            flush_paragraph()
            last_paragraph = None
            sentences_since_heading = []
            last_heading_raw = line
            idm = HEADING_ID_RE.search(line)
            last_heading_id = idm.group(1) if idm else None
            pending_span_id = None
            i += 1
            continue

        sm = SPAN_ID_RE.match(line)
        if sm:
            pending_span_id = sm.group(1)
            i += 1
            continue

        cm = CHUNK_START_RE.match(line)
        if cm:
            flush_paragraph()
            engine = cm.group(1)
            start = i
            i += 1
            opts = {}
            current_key = None
            code_lines = []
            while i < n and lines[i].rstrip() != '```':
                contm = CONTINUATION_RE.match(lines[i])
                if contm and current_key:
                    opts[current_key] = opts[current_key] + ' ' + contm.group(1)
                else:
                    om = OPTION_RE.match(lines[i])
                    if om:
                        current_key = om.group(1)
                        opts[current_key] = om.group(2)
                    else:
                        current_key = None
                        code_lines.append(lines[i])
                i += 1
            label = opts.get('label', '')

            if label.startswith('fig-') and 'fig-cap' in opts:
                figs.append((label, clean_caption(opts['fig-cap'])))
            elif label.startswith('tbl-'):
                if 'tbl-cap' in opts:
                    tbls.append((label, clean_caption(opts['tbl-cap'])))
                else:
                    # kable()/gt() etc. sometimes carry the caption as a call
                    # argument (caption = "...") instead of a #| tbl-cap option.
                    cm = KABLE_CAPTION_RE.search('\n'.join(code_lines))
                    if cm:
                        tbls.append((label, cm.group(2)))
                    else:
                        print(f"WARNING: {path.name}: table '{label}' has no "
                              f"tbl-cap option or caption= argument; skipped in gallery.",
                              file=sys.stderr)

            if engine == 'shinylive-r':
                sec_id = last_heading_id or pending_span_id
                if sec_id:
                    desc = pick_app_description(sentences_since_heading, last_paragraph)
                    if desc is None:
                        desc = strip_heading_text(last_heading_raw)
                    apps.append((sec_id, desc))
                else:
                    print(f"WARNING: {path.name}: shinylive app '{label}' near line "
                          f"{start+1} has no #sec- anchor on its heading; skipped in gallery.",
                          file=sys.stderr)
            i += 1
            continue

        if line.strip().startswith(':::'):
            i += 1
            continue

        if line.strip() == '':
            flush_paragraph()
        else:
            paragraph_buffer.append(line.strip())
        i += 1

    return title, figs, tbls, apps


def render_gallery(chapters_data):
    lines = []
    lines.append("# Figures, Tables, and Apps {.unnumbered}")
    lines.append("")
    lines.append("A consolidated index of every numbered figure and table in the book, plus "
                  "the interactive Shiny apps. Click any entry to jump to it in context.")
    lines.append("")
    lines.append("## Interactive apps")
    lines.append("")
    for title, figs, tbls, apps in chapters_data:
        for sec_id, desc in apps:
            lines.append(f"* @{sec_id} (in *{title}*) — {desc}")
    lines.append("")

    lines.append("## Figures")
    lines.append("")
    for title, figs, tbls, apps in chapters_data:
        if not figs:
            continue
        lines.append(f"### {title}")
        lines.append("")
        for label, cap in figs:
            lines.append(f"* @{label} — {cap}")
        lines.append("")

    lines.append("## Tables")
    lines.append("")
    for title, figs, tbls, apps in chapters_data:
        if not tbls:
            continue
        lines.append(f"### {title}")
        lines.append("")
        for label, cap in tbls:
            lines.append(f"* @{label} — {cap}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main():
    chapter_files = get_chapter_order()
    if not chapter_files:
        print("gen_gallery: no chapters found in _quarto.yml", file=sys.stderr)
        sys.exit(1)

    chapters_data = []
    n_fig = n_tbl = n_app = 0
    for rel in chapter_files:
        path = ROOT / rel
        if not path.exists():
            print(f"WARNING: {rel} listed in _quarto.yml but not found on disk; skipped.",
                  file=sys.stderr)
            continue
        title, figs, tbls, apps = parse_chapter(path)
        chapters_data.append((title, figs, tbls, apps))
        n_fig += len(figs); n_tbl += len(tbls); n_app += len(apps)

    OUTPUT.write_text(render_gallery(chapters_data), encoding="utf-8")
    print(f"gen_gallery: wrote {OUTPUT.name} — {n_fig} figures, {n_tbl} tables, "
          f"{n_app} interactive apps across {len(chapters_data)} chapters.", file=sys.stderr)


if __name__ == "__main__":
    main()
