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
        echo "gen_shinyapps: Neither virtualenv nor system Python found." >&2
        exit 1
    fi
fi

exec "$PYTHON_EXEC" "$0" "$@"
"""

# Regenerates the standalone Shinylive app archive straight from the app
# chunks already in the chapter .qmd files, so the archive can never drift out
# of sync with the book. Run it after adding, removing, or editing any
# {shinylive-r} app, then render:
#
#   ./gen_shinyapps.py && quarto render shinyapps_src
#
# What it writes (everything under shinyapps_src/ is generated -- do not edit
# by hand; edit the chapter the app lives in and re-run):
#
#   shinyapps_src/_quarto.yml                 website sub-project + left sidebar
#   shinyapps_src/shinyliveapps_compstat.qmd  the hub page
#   shinyapps_src/app_<slug>.qmd              one page per app
#
# The sub-project renders with `output-dir: ..`, so the .html files land at the
# repo root beside the book's own index.html and share the book's already-built
# site_libs/ and shinylive-sw.js. Website search is switched off deliberately:
# it would otherwise overwrite the book's root search.json.
#
# The chapter parser here is deliberately the same one gen_gallery.py uses --
# every app in this book is wrapped in a Pandoc Figure Div
#
#   ::: {#fig-foo-app}
#
#   ```{shinylive-r}
#   ...
#   ```
#
#   **Caption label.** Description...
#
#   :::
#
# so the div id gives the page its slug and its back-link anchor, and the
# bold run opening the trailing caption paragraph gives the page its title.

import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
QUARTO_YML = ROOT / "_quarto.yml"
SRC_DIR = ROOT / "shinyapps_src"
HUB_STEM = "shinyliveapps_compstat"
SKIP = {"index.qmd", "gallery.qmd"}

BOOK_TITLE = "Elements of Statistical Computation"
SITE_TITLE = "Shinylive Apps"

DIV_FENCE_RE = re.compile(r'^:{3,}')
DIV_OPEN_RE = re.compile(r'^:{3,}\s*\{([^}]*)\}\s*$')
DIV_ID_IN_ATTRS_RE = re.compile(r'#([\w-]+)')
CHUNK_START_RE = re.compile(r'^```\{(r|shinylive-r)[^}]*\}')
HEADING_RE = re.compile(r'^(#{1,6})\s+(.*)$')
HEADING_ID_RE = re.compile(r'\{#([\w-]+)\}')
TITLE_RE = re.compile(r'^title:\s*(.+)$', re.M)
# A real chunk option always has exactly one space after "#|"; a continuation
# line of a multi-line quoted value is indented further. See gen_gallery.py.
OPTION_RE = re.compile(r'^#\| ([\w.-]+):\s*(.*)$')
CONTINUATION_RE = re.compile(r'^#\|\s{2,}(.*)$')
LEADING_BOLD_RE = re.compile(r'^\*\*([^*]+)\*\*\s*[:.]?\s*')
# Every caption label in the book names its app the same way -- "Shinylive App
# Illustrating X", "A Shinylive App for Y". On a site that is nothing but
# Shinylive apps that prefix is pure noise repeated sixteen times down the
# sidebar, so it is trimmed away for the page title. A participle that carries
# meaning ("Comparing ...") survives; the empty connectives do not.
APP_PREFIX_RE = re.compile(r'^(?:an?|the)?\s*shinylive\s+app\s+', re.I)
APP_CONNECTIVE_RE = re.compile(r'^(?:illustrating|for|of|on|about|demonstrating)\s+', re.I)
MATH_RE = re.compile(r'\$([^$]*)\$')


def short_title(label):
    """Trim the repeated "Shinylive App ..." boilerplate off a caption label."""
    trimmed = APP_PREFIX_RE.sub('', label).strip()
    if not trimmed:
        return label
    trimmed = APP_CONNECTIVE_RE.sub('', trimmed).strip() or trimmed
    return trimmed[0].upper() + trimmed[1:] if trimmed else label


def plain_text(s):
    """Sidebar entries are plain text, not markdown: $t$ would show its dollars."""
    return MATH_RE.sub(r'\1', s)


def get_chapter_order():
    lines = QUARTO_YML.read_text(encoding="utf-8").splitlines()
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
                break  # dedented to a sibling key: the chapters block ended
    return [c for c in chapters if c not in SKIP]


def get_title(path):
    m = TITLE_RE.search(path.read_text(encoding="utf-8"))
    return m.group(1).strip().strip('"').strip("'") if m else path.stem


def strip_heading_text(raw_heading):
    text = raw_heading.lstrip('#').strip()
    return HEADING_ID_RE.sub('', text).strip()


def split_caption(text):
    """Split an app's Figure Div caption into (bold label, rest).

    The label is what the book's own cross-references show, so it becomes the
    archive page's title; the remainder is the page's lead paragraph.
    """
    if not text:
        return None, ""
    text = text.strip()
    m = LEADING_BOLD_RE.match(text)
    if not m:
        return None, text
    label = m.group(1).strip().rstrip(':.').strip()
    return (label or None), text[m.end():].strip()


def slug_for(fig_id):
    """fig-inverse-cdf-app -> inverse-cdf (the page becomes app_inverse-cdf.html)."""
    slug = re.sub(r'^fig-', '', fig_id)
    slug = re.sub(r'-app$', '', slug)
    return slug or fig_id


def parse_chapter(path):
    """Return (chapter title, [app dicts]) for one chapter file."""
    lines = path.read_text(encoding="utf-8").splitlines()
    n = len(lines)
    apps = []

    last_heading_raw = ""
    paragraph_buffer = []
    last_paragraph = None
    div_stack = []      # id (or None) of each open ::: div, innermost last
    pending = None      # app being collected, keyed by its fig- div id

    def flush_paragraph():
        nonlocal last_paragraph
        if paragraph_buffer:
            last_paragraph = ' '.join(paragraph_buffer).strip()
            paragraph_buffer.clear()

    def current_fig_div():
        for div_id in reversed(div_stack):
            if div_id and div_id.startswith('fig-'):
                return div_id
        return None

    i = 0
    while i < n:
        line = lines[i]

        hm = HEADING_RE.match(line)
        if hm:
            flush_paragraph()
            last_paragraph = None
            last_heading_raw = line
            i += 1
            continue

        if DIV_FENCE_RE.match(line.strip()):
            flush_paragraph()
            om = DIV_OPEN_RE.match(line.strip())
            if om:
                idm = DIV_ID_IN_ATTRS_RE.search(om.group(1))
                div_stack.append(idm.group(1) if idm else None)
            else:
                closed_id = div_stack.pop() if div_stack else None
                if pending is not None and closed_id == pending['fig_id']:
                    # Whatever paragraph immediately preceded this closing
                    # fence is the Figure Div's caption.
                    label, rest = split_caption(last_paragraph)
                    if label is None:
                        print(f"WARNING: {path.name}: app '{pending['fig_id']}' has no "
                              f"bold '**...**' label opening its Figure Div caption; "
                              f"falling back to the section heading.", file=sys.stderr)
                        label = strip_heading_text(pending['heading']) or pending['fig_id']
                        rest = last_paragraph or ""
                    pending['title'] = short_title(label)
                    pending['caption'] = label
                    pending['lead'] = rest
                    apps.append(pending)
                    pending = None
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

            if engine == 'shinylive-r':
                fig_id = current_fig_div()
                if not fig_id:
                    print(f"WARNING: {path.name}: shinylive app near line {start+1} is "
                          f"not inside a '::: {{#fig-...}}' div; skipped in the archive.",
                          file=sys.stderr)
                elif pending is not None:
                    print(f"WARNING: {path.name}: a second shinylive app appears inside "
                          f"'{fig_id}' before the first div closed; skipped.",
                          file=sys.stderr)
                else:
                    pending = {
                        'fig_id': fig_id,
                        'slug': slug_for(fig_id),
                        'chapter': path.name,
                        'heading': last_heading_raw,
                        'options': opts,
                        'code': '\n'.join(code_lines).strip('\n'),
                        'line': start + 1,
                    }
            i += 1
            continue

        if line.strip() == '':
            flush_paragraph()
        else:
            paragraph_buffer.append(line.strip())
        i += 1

    if pending is not None:
        print(f"WARNING: {path.name}: the div around app '{pending['fig_id']}' never "
              f"closed; app skipped.", file=sys.stderr)

    return get_title(path), apps


def yaml_quote(s):
    return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'


def app_chunk(app):
    """Rebuild the {shinylive-r} chunk verbatim, minus book-only chunk options.

    `label:` is dropped because each app now lives alone on its own page, where
    a book-wide cross-reference label has nothing to point at, and `code-fold:`
    because a `standalone: true` app renders as the running app only -- the
    source is shown separately below it instead.
    """
    keep = {k: v for k, v in app['options'].items() if k not in {'label', 'code-fold'}}
    keep.setdefault('standalone', 'true')
    out = ['```{shinylive-r}']
    out += [f'#| {k}: {v}' for k, v in keep.items()]
    out.append(app['code'])
    out.append('```')
    return '\n'.join(out)


def source_block(app):
    """The app's R source, folded, so the archive carries the code as well as
    the running app. Uses a fence long enough to survive backticks in the code."""
    ticks = '`' * max(4, max((len(m) for m in re.findall(r'`+', app['code'])), default=0) + 1)
    return '\n'.join([
        ':::: {.callout-note collapse="true" title="R source for this app"}',
        '',
        ticks + 'r',
        app['code'],
        ticks,
        '',
        '::::',
    ])


def render_app_page(app, chapter_title):
    book_href = f"chapters/{Path(app['chapter']).with_suffix('.html').name}#{app['fig_id']}"
    lines = [
        '---',
        f"title: {yaml_quote(app['title'])}",
        f"subtitle: {yaml_quote(chapter_title)}",
        '---',
        '',
        '<!-- GENERATED by gen_shinyapps.py from '
        f"chapters/{app['chapter']} (line {app['line']}) -- do not edit by hand. -->",
        '',
    ]
    if app['lead']:
        lines += [app['lead'], '']
    lines += [
        app_chunk(app),
        '',
        source_block(app),
        '',
        f"[Read this app in context]({book_href}) in *{chapter_title}*.",
        '',
    ]
    return '\n'.join(lines)


def render_hub(chapters_data, n_app):
    lines = [
        '---',
        f'title: {yaml_quote(SITE_TITLE)}',
        f'subtitle: {yaml_quote(BOOK_TITLE)}',
        '---',
        '',
        '<!-- GENERATED by gen_shinyapps.py -- do not edit by hand. -->',
        '',
        f'This is a standalone archive of all {n_app} interactive Shinylive apps in '
        f'*[{BOOK_TITLE}](index.html)*. Each app runs entirely in your browser: the R '
        'code is compiled to WebAssembly and executed locally by [webR](https://docs.r-wasm.org/webr/latest/), '
        'so nothing is sent to a server and no R installation is needed.',
        '',
        'Pick an app from the sidebar, or from the list below. Every page also carries '
        'the app\'s full R source and a link back to the section of the book that '
        'explains it. The first load of an app takes a few seconds while webR downloads.',
        '',
    ]
    for chapter_title, apps in chapters_data:
        if not apps:
            continue
        lines += [f'## {chapter_title}', '']
        for app in apps:
            lines.append(f"* [{app['title']}](app_{app['slug']}.html)"
                         + (f" — {app['lead'].split('. ')[0].rstrip('.')}." if app['lead'] else ""))
        lines.append('')
    return '\n'.join(lines).rstrip() + '\n'


def render_quarto_yml(chapters_data):
    lines = [
        '# GENERATED by gen_shinyapps.py -- do not edit by hand.',
        '#',
        '# A website sub-project whose only job is to publish the book\'s Shinylive',
        '# apps as one standalone page each. It renders into the repo root',
        '# (output-dir: ..) so the pages sit beside the book\'s index.html and reuse',
        '# the site_libs/ and shinylive-sw.js already built there. Search is off on',
        '# purpose: a website search index would overwrite the book\'s search.json.',
        'project:',
        '  type: website',
        '  output-dir: ..',
        '  render:',
        '    - "*.qmd"',
        '',
        'website:',
        f'  title: {yaml_quote(SITE_TITLE)}',
        '  search: false',
        '  page-navigation: true',
        '  sidebar:',
        '    style: docked',
        '    collapse-level: 1',
        '    contents:',
        f'      - href: {HUB_STEM}.qmd',
        '        text: "All apps"',
        '      - href: index.html',
        f'        text: {yaml_quote("← Back to the book")}',
    ]
    for chapter_title, apps in chapters_data:
        if not apps:
            continue
        lines.append(f'      - section: {yaml_quote(chapter_title)}')
        lines.append('        contents:')
        for app in apps:
            lines.append(f"          - href: app_{app['slug']}.qmd")
            lines.append(f"            text: {yaml_quote(plain_text(app['title']))}")
    lines += [
        '',
        'filters:',
        '  - shinylive',
        '',
        'format:',
        '  html:',
        '    theme: cosmo',
        '    toc: false',
        '    embed-resources: false   # shinylive cannot run in a self-contained file',
        '    link-external-newwindow: true',
    ]
    return '\n'.join(lines) + '\n'


def main():
    chapter_files = get_chapter_order()
    if not chapter_files:
        print("gen_shinyapps: no chapters found in _quarto.yml", file=sys.stderr)
        sys.exit(1)

    chapters_data = []
    seen_slugs = {}
    n_app = 0
    for rel in chapter_files:
        path = ROOT / rel
        if not path.exists():
            print(f"WARNING: {rel} listed in _quarto.yml but not found on disk; skipped.",
                  file=sys.stderr)
            continue
        chapter_title, apps = parse_chapter(path)
        for app in apps:
            prior = seen_slugs.get(app['slug'])
            if prior is not None:
                print(f"WARNING: apps '{prior}' and '{app['fig_id']}' both map to the "
                      f"page app_{app['slug']}.html; one will overwrite the other.",
                      file=sys.stderr)
            seen_slugs[app['slug']] = app['fig_id']
        chapters_data.append((chapter_title, apps))
        n_app += len(apps)

    if not n_app:
        print("gen_shinyapps: no {shinylive-r} apps found; nothing written.", file=sys.stderr)
        sys.exit(1)

    # Rebuild the source dir from scratch so an app deleted from the book does
    # not leave an orphan page behind. _extensions is a symlink to the book's,
    # so the sub-project can find the shinylive filter from its own root.
    if SRC_DIR.exists():
        for child in SRC_DIR.iterdir():
            if child.is_symlink() or child.is_file():
                child.unlink()
            elif child.is_dir():
                shutil.rmtree(child)
    SRC_DIR.mkdir(exist_ok=True)
    (SRC_DIR / "_extensions").symlink_to("../_extensions")

    (SRC_DIR / "_quarto.yml").write_text(render_quarto_yml(chapters_data), encoding="utf-8")
    (SRC_DIR / f"{HUB_STEM}.qmd").write_text(render_hub(chapters_data, n_app), encoding="utf-8")
    for chapter_title, apps in chapters_data:
        for app in apps:
            (SRC_DIR / f"app_{app['slug']}.qmd").write_text(
                render_app_page(app, chapter_title), encoding="utf-8")

    print(f"gen_shinyapps: wrote {SRC_DIR.name}/ — {n_app} app pages plus "
          f"{HUB_STEM}.qmd across {len(chapters_data)} chapters.\n"
          f"Now run: quarto render {SRC_DIR.name}", file=sys.stderr)


if __name__ == "__main__":
    main()
