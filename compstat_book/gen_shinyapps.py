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

# SPENT MIGRATION TOOL -- kept for the record, not for re-running.
#
# On 2026-09-26 this script moved all 16 {shinylive-r} apps out of the book's
# chapters and into the standalone archive in shinyliveapps_compstat/, taking
# each app's caption and the prose of its chapter section along as that page's
# "About the app" notes. The chapters now hold only a pointer to the archive.
#
# Because it builds the archive *from* the chapters, and the chapters no
# longer contain any apps, running it again finds nothing and exits with
# "no {shinylive-r} apps found; nothing written" without touching anything.
# The archive is now hand-maintained: shinyliveapps_compstat/app_<slug>.qmd is
# the only copy of each app, and _quarto.yml's sidebar is the list of them.
# To add an app, write its page and add it to index.qmd and that sidebar, then
#
#   quarto render shinyliveapps_compstat
#
# The rest of this file documents how the migration was done.
#
# Every app in the book was wrapped in a Pandoc Figure Div
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
# so the div id gave the page its slug and its back-link anchor, and the bold
# run opening the trailing caption paragraph gave the page its title. The
# chapter parser is the same one gen_gallery.py uses.

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
QUARTO_YML = ROOT / "_quarto.yml"
SRC_DIR = ROOT / "shinyliveapps_compstat"
HUB_STEM = "index"
STYLES = "styles.scss"
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



# Seeded into the archive once, then hand-editable forever after. Quarto's
# stock sidebar is a plain list in small type; the rules below turn each entry
# into a card-like button and make the chapter names read as section labels
# rather than as more links.
DEFAULT_STYLES = """/*-- scss:defaults --*/

// The app titles taken from the book's captions are long sentences, so the
// sidebar needs more room than Quarto's 250px default. Quarto spends only
// about 0.6 of this value on the sidebar columns themselves, so 470px is what
// buys a sidebar roughly 300px wide.
$grid-sidebar-width: 470px;

/*-- scss:rules --*/

$app-accent: #2563eb;
$app-accent-soft: rgba(37, 99, 235, 0.1);
$app-ink: #334155;

#quarto-sidebar {
  background: linear-gradient(180deg, #fbfcfe 0%, #eef2f8 100%);
  border-right: 1px solid rgba(15, 23, 42, 0.08);
  padding: 0 0.7rem 2rem;
}

#quarto-sidebar .sidebar-title {
  font-size: 1.2rem;
  font-weight: 650;
  letter-spacing: -0.015em;
  padding: 0.5rem 0.35rem 0.1rem;

  a {
    color: #0f172a;
    text-decoration: none;
  }
}

#quarto-sidebar .sidebar-item {
  font-size: 0.97rem;
  line-height: 1.32;
}

#quarto-sidebar .sidebar-item-container {
  margin: 0.22rem 0;
}

// Every navigable entry is a button.
#quarto-sidebar .sidebar-link {
  display: block;
  width: 100%;
  padding: 0.55rem 0.7rem;
  border-radius: 0.55rem;
  color: $app-ink;
  text-decoration: none;
  background: #fff;
  border: 1px solid rgba(15, 23, 42, 0.08);
  box-shadow: 0 1px 2px rgba(15, 23, 42, 0.05);
  transition: background-color 0.15s ease, border-color 0.15s ease,
    box-shadow 0.15s ease, transform 0.15s ease, color 0.15s ease;
}

#quarto-sidebar .sidebar-link:hover {
  background: $app-accent-soft;
  border-color: rgba(37, 99, 235, 0.35);
  color: #1e293b;
  box-shadow: 0 2px 6px rgba(15, 23, 42, 0.09);
  transform: translateX(2px);
}

#quarto-sidebar .sidebar-link.active {
  background: linear-gradient(180deg, #3b82f6 0%, $app-accent 100%);
  border-color: transparent;
  color: #fff;
  font-weight: 600;
  box-shadow: 0 3px 8px rgba(37, 99, 235, 0.32);
}

// ...except the chapter headings, which are labels for the buttons beneath
// them. They carry .sidebar-link too, so the button styling is undone here.
#quarto-sidebar .sidebar-item-section > .sidebar-item-container {
  display: flex;
  align-items: center;
  margin: 0.9rem 0 0.15rem;
}

#quarto-sidebar .sidebar-item-section > .sidebar-item-container > .sidebar-link {
  flex: 1;
  background: transparent;
  border: none;
  box-shadow: none;
  padding: 0.15rem 0.35rem;
  font-size: 0.75rem;
  font-weight: 700;
  letter-spacing: 0.07em;
  text-transform: uppercase;
  color: #64748b;

  &:hover {
    background: transparent;
    box-shadow: none;
    transform: none;
    color: $app-accent;
  }
}

#quarto-sidebar .sidebar-item-toggle {
  color: #94a3b8;
  text-decoration: none;

  &:hover {
    color: $app-accent;
  }
}

#quarto-sidebar .sidebar-section .sidebar-item-container {
  margin-left: 0.1rem;
}
"""

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


# Sentences that exist only because the app sits inside a multi-format book:
# they tell PDF readers where to find the live version. On a page that *is*
# the live version they are worse than redundant, so they are dropped. The
# patterns allow any whitespace between words because the chapter sources are
# hard-wrapped, so a sentence is usually split across two or three lines.
BOOK_ONLY_SENTENCES = [
    "This app runs live only in the HTML edition of this book; readers of "
    "other formats can follow the link below it.",
]
BOOK_ONLY_RES = [re.compile(r'\s+'.join(map(re.escape, t.split())))
                 for t in BOOK_ONLY_SENTENCES]


def strip_book_only(text):
    for rx in BOOK_ONLY_RES:
        text = rx.sub('', text)
    # Tidy up after the excisions: trailing spaces and the blank-line runs a
    # removed sentence can leave behind.
    text = re.sub(r'[ \t]+$', '', text, flags=re.M)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip('\n')


# Prose lifted out of a chapter can carry the book's cross-references with it
# (@tbl-..., @sec-..., @fig-...). Those resolve to nothing on an archive page,
# where Quarto renders them as a broken "?@ref", so each one is rewritten into
# a real link: to another app's page when it points at an app, and otherwise
# back into the rendered chapter that owns it, keeping the number the book
# gave it ("Table 10.2") by reading it out of the rendered HTML.
XREF_RE = re.compile(r'(?<![\w@])@((?:fig|tbl|sec|eq|thm|lst|exm|exr)-[A-Za-z0-9_-]+)')
XREF_LABEL_RE = r'<a href="#%s" class="quarto-xref">(.*?)</a>'
NBSP_RE = re.compile(r'&nbsp;|&#160;')


def _label_text(raw):
    """'Table&nbsp;<span>10.2</span>' -> 'Table 10.2'."""
    text = re.sub(r'<[^>]+>', '', raw)
    return re.sub(r'\s+', ' ', NBSP_RE.sub(' ', text)).strip()


def build_xref_index(chapter_files, wanted):
    """Map each wanted crossref id to (rendered chapter file, label text)."""
    index = {}
    if not wanted:
        return index
    for rel in chapter_files:
        html_path = ROOT / Path(rel).with_suffix('.html')
        if not html_path.exists():
            continue
        html = html_path.read_text(encoding="utf-8", errors="replace")
        for cid in wanted - index.keys():
            if f'id="{cid}"' not in html:
                continue
            m = re.search(XREF_LABEL_RE % re.escape(cid), html, re.S)
            index[cid] = (html_path.name, _label_text(m.group(1)) if m else cid)
    return index


def rewrite_xrefs(text, app, app_ids, xref_index):
    def sub(m):
        cid = m.group(1)
        if cid in (app['fig_id'], app.get('sec_id')):
            return 'the app above'
        if cid in app_ids:
            slug, title = app_ids[cid]
            return f'[{title}](app_{slug}.html)'
        hit = xref_index.get(cid)
        if hit:
            chapter_html, label = hit
            return f'[{label}](../chapters/{chapter_html}#{cid})'
        print(f"WARNING: {app['chapter']}: '{app['fig_id']}' refers to @{cid}, which "
              f"is neither an app nor findable in the rendered book; left as-is and "
              f"it will render as a broken cross-reference. Render the book first.",
              file=sys.stderr)
        return m.group(0)
    return XREF_RE.sub(sub, text)


def structural_headings(lines):
    """Headings that actually divide the chapter into sections.

    Two kinds of line look like a heading but are not one: an R comment inside
    a chunk ("# ---- setup ----") and a heading written inside a div, which in
    this book is how a callout gets its title ("::: {.callout-note}" followed
    by "### Reproducing this figure"). Counting either as a section break cuts
    an app's section short.
    """
    heads = []
    in_chunk = False
    depth = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith('```'):
            in_chunk = not in_chunk
            continue
        if in_chunk:
            continue
        if DIV_FENCE_RE.match(stripped):
            depth = depth + 1 if DIV_OPEN_RE.match(stripped) else max(depth - 1, 0)
            continue
        if depth == 0 and (m := HEADING_RE.match(line)):
            heads.append((i, len(m.group(1))))
    return heads


# In the book each app sits in a section of its own -- "### Shinylive App for
# X" -- holding the app plus a few paragraphs explaining what to do with it.
# Those paragraphs are the archive's "About the app" text. Everything that is
# the app itself, or exists only to paper over the app's absence in the PDF
# edition, is left behind: the Figure Div carrying the chunk and its caption
# (already the page's lead), and the .content-visible blocks, whose whole
# purpose is to show one thing in HTML and another elsewhere.
CONTENT_VISIBLE_RE = re.compile(r'content-visible|content-hidden')


def extract_about(lines, heads, app):
    div_start, div_end = app.get('div_span', (None, None))
    if div_start is None:
        return ""

    # The enclosing section runs from the nearest heading above the app to the
    # next heading at the same or a shallower level.
    prior = [h for h in heads if h[0] < div_start]
    if not prior:
        return ""
    head_idx, head_level = prior[-1]
    end = next((i for i, lv in heads if i > head_idx and lv <= head_level), len(lines))

    kept = []
    i = head_idx + 1
    while i < end:
        line = lines[i]
        stripped = line.strip()
        if div_start <= i <= div_end:
            i = div_end + 1
            continue
        om = DIV_OPEN_RE.match(stripped)
        if om and CONTENT_VISIBLE_RE.search(om.group(1)):
            # Skip the whole conditional block, including any nesting inside it.
            depth = 0
            while i < end:
                st = lines[i].strip()
                if DIV_FENCE_RE.match(st):
                    depth += 1 if DIV_OPEN_RE.match(st) else -1
                    if depth == 0:
                        break
                i += 1
            i += 1
            continue
        kept.append(line)
        i += 1

    return strip_book_only('\n'.join(kept))


def parse_chapter(path):
    """Return (chapter title, [app dicts]) for one chapter file."""
    lines = path.read_text(encoding="utf-8").splitlines()
    n = len(lines)
    heads = structural_headings(lines)
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
        for div_id, _ in reversed(div_stack):
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
                div_stack.append((idm.group(1) if idm else None, i))
            else:
                closed_id, opened_at = div_stack.pop() if div_stack else (None, None)
                if pending is not None and closed_id == pending['fig_id']:
                    pending['div_span'] = (opened_at, i)
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
                    sid = HEADING_ID_RE.search(pending['heading'] or '')
                    pending['sec_id'] = sid.group(1) if sid else None
                    pending['about'] = extract_about(lines, heads, pending)
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


# `engine: markdown` has to sit in each document's front matter -- Quarto
# ignores a project-level `engine:` key. Without it Quarto starts a jupyter
# kernel for every page, which is both slow and a dependency this archive does
# not otherwise have: no chunk here is executed at render time, since the
# shinylive filter turns the {shinylive-r} block into a browser-side app.
def render_app_page(app, chapter_title, app_ids, xref_index):
    # The archive lives one directory below the book, so every link back into
    # a chapter climbs out of it first. The target is the *section* the app
    # used to occupy, not its Figure Div: once the app itself has moved here,
    # what remains in the chapter is that section, now a pointer back to this
    # page. Sections that never carried an explicit id get the same id the
    # book-side stub is given.
    anchor = app.get('sec_id') or f"sec-{app['slug']}-app"
    book_href = f"../chapters/{Path(app['chapter']).with_suffix('.html').name}#{anchor}"
    lines = [
        '---',
        'engine: markdown',
        f"title: {yaml_quote(app['title'])}",
        f"subtitle: {yaml_quote(chapter_title)}",
        '---',
        '',
        '<!-- GENERATED by gen_shinyapps.py from '
        f"chapters/{app['chapter']} (line {app['line']}) -- do not edit by hand. -->",
        '',
    ]
    lines += [app_chunk(app), '']
    # The caption's description opens "About the app" so that every app has
    # one, including the few whose chapter section holds nothing but the app.
    about = '\n\n'.join(x for x in (app['lead'], app.get('about', '')) if x)
    about = rewrite_xrefs(about, app, app_ids, xref_index)
    if about:
        lines += ['## About the app', '', about, '']
    lines += [
        source_block(app),
        '',
        f"This app accompanies *[{chapter_title}]({book_href})* in the book.",
        '',
    ]
    return '\n'.join(lines)


def render_hub(chapters_data, n_app):
    lines = [
        '---',
        'engine: markdown',
        f'title: {yaml_quote(SITE_TITLE)}',
        f'subtitle: {yaml_quote(BOOK_TITLE)}',
        '---',
        '',
        '<!-- GENERATED by gen_shinyapps.py -- do not edit by hand. -->',
        '',
        f'This is a standalone archive of all {n_app} interactive Shinylive apps in '
        f'*[{BOOK_TITLE}](../index.html)*. Each app runs entirely in your browser: the R '
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
        "# A website sub-project whose only job is to publish the book's Shinylive",
        '# apps as one standalone page each. Sources and rendered pages share this',
        '# directory (output-dir: .), exactly as the book does at the repo root, so',
        '# rendering the archive can never touch the book\'s own index.html,',
        '# search.json or site_libs/ one level up.',
        'project:',
        '  type: website',
        '  output-dir: .',
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
        '      - href: index.qmd',
        '        text: "All apps"',
        '      - href: ../index.html',
        f'        text: {yaml_quote("Back to the book")}',
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
        f'    theme: [cosmo, {STYLES}]',
        '    toc: false',
        '    # These pages are app viewers, not prose: the default article column',
        '    # squeezes a sidebarLayout app into half the window and leaves the',
        '    # rest of the screen empty.',
        '    page-layout: full',
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

    # The rendered pages now live in this directory too, so the old
    # wipe-and-recreate is gone: only the files this script owns are rewritten,
    # and only apps that have disappeared from the book are cleaned up.
    SRC_DIR.mkdir(exist_ok=True)
    ext = SRC_DIR / "_extensions"
    if not ext.exists():
        # The sub-project is its own Quarto project root, so it cannot see the
        # book's _extensions by walking up -- it needs its own path to the
        # shinylive filter.
        ext.symlink_to("../_extensions")

    # An app may be referred to by its Figure Div id or by the {#sec-...} on
    # its heading; both must land on the same archive page.
    app_ids = {}
    for _, apps in chapters_data:
        for app in apps:
            for key in (app['fig_id'], app.get('sec_id')):
                if key:
                    app_ids[key] = (app['slug'], app['title'])
    wanted = set()
    for _, apps in chapters_data:
        for app in apps:
            for cid in XREF_RE.findall(f"{app['lead']}\n{app.get('about', '')}"):
                if cid not in app_ids:
                    wanted.add(cid)
    xref_index = build_xref_index(chapter_files, wanted)

    (SRC_DIR / "_quarto.yml").write_text(render_quarto_yml(chapters_data), encoding="utf-8")
    (SRC_DIR / f"{HUB_STEM}.qmd").write_text(render_hub(chapters_data, n_app), encoding="utf-8")

    wanted = set()
    for chapter_title, apps in chapters_data:
        for app in apps:
            name = f"app_{app['slug']}"
            wanted.add(name)
            (SRC_DIR / f"{name}.qmd").write_text(
                render_app_page(app, chapter_title, app_ids, xref_index),
                encoding="utf-8")

    # An app renamed or removed in the book would otherwise leave its page
    # behind, still listed by nothing but still served.
    removed = 0
    for stale in sorted(SRC_DIR.glob("app_*.qmd")):
        if stale.stem not in wanted:
            stale.unlink()
            stale.with_suffix(".html").unlink(missing_ok=True)
            print(f"gen_shinyapps: removed stale page {stale.stem} "
                  f"(its app is no longer in the book).", file=sys.stderr)
            removed += 1

    # styles.scss is seeded once and then left alone, so the sidebar can be
    # restyled by hand without the next run reverting it.
    styles = SRC_DIR / STYLES
    if not styles.exists():
        styles.write_text(DEFAULT_STYLES, encoding="utf-8")
        print(f"gen_shinyapps: created {STYLES} (edit it freely -- it is never "
              f"overwritten).", file=sys.stderr)

    print(f"gen_shinyapps: wrote {SRC_DIR.name}/ — {n_app} app pages plus "
          f"{HUB_STEM}.qmd across {len(chapters_data)} chapters.\n"
          f"Now run: quarto render {SRC_DIR.name}", file=sys.stderr)


if __name__ == "__main__":
    main()
