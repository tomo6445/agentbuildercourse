"""
mdlite — a small, dependency-free Markdown renderer for this course.

Deliberately a subset. It supports exactly what the lesson files use, and
nothing else, so the build stays a single `python3 tools/build.py` with no
pip install and no network access.

Supported
---------
  ## / ### / ####        headings (h2..h4), auto-slugged ids
  paragraphs             blank-line separated
  - / * / 1.             lists, one level of nesting via two-space indent
  ```lang title=…        fenced code, optional title line
  > quote                blockquote
  | a | b |              pipe tables with a --- separator row
  ---                    horizontal rule
  ::: name Title         directive block, closed by a lone `:::`
  <div>…                 raw HTML lines pass through untouched

Inline: `code`, **bold**, *italic*, [text](href), and raw inline HTML.
"""

from __future__ import annotations

import html
import re

# --------------------------------------------------------------------------
# inline
# --------------------------------------------------------------------------

_CODE_SPAN = re.compile(r"`([^`]+)`")
_BOLD = re.compile(r"\*\*(.+?)\*\*", re.S)
_ITALIC = re.compile(r"(?<![\*\w])\*([^\*\n]+?)\*(?!\*)")
_LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
_BULLET = re.compile(r"^([-*]|\d+\.)\s+")


def inline(text: str) -> str:
    """Render inline markup. Raw HTML in the source is intentionally preserved."""
    slots: list[str] = []

    def stash(rendered: str) -> str:
        slots.append(rendered)
        return f"\x00{len(slots) - 1}\x00"

    # Code spans first: nothing inside them should be interpreted.
    text = _CODE_SPAN.sub(lambda m: stash(f"<code>{html.escape(m.group(1))}</code>"), text)
    text = _LINK.sub(lambda m: stash(f'<a href="{m.group(2)}">{m.group(1)}</a>'), text)
    text = _BOLD.sub(r"<strong>\1</strong>", text)
    text = _ITALIC.sub(r"<em>\1</em>", text)

    for i, rendered in enumerate(slots):
        text = text.replace(f"\x00{i}\x00", rendered)
    return text


def slug(text: str) -> str:
    bare = re.sub(r"<[^>]+>", "", text)
    bare = re.sub(r"[^a-zA-Z0-9\s-]", "", bare).strip().lower()
    return re.sub(r"[\s-]+", "-", bare)


# --------------------------------------------------------------------------
# block
# --------------------------------------------------------------------------

class Renderer:
    """Renders a document and collects the headings it saw, for the TOC."""

    def __init__(self, widget_renderer=None):
        self.headings: list[tuple[int, str, str]] = []  # (level, id, text)
        self.widget_renderer = widget_renderer or (lambda name, body: "")

    # -- entry point -------------------------------------------------------

    def render(self, src: str) -> str:
        self.headings = []
        lines = src.replace("\r\n", "\n").split("\n")
        return "\n".join(self._blocks(lines, 0, len(lines)))

    # -- block loop --------------------------------------------------------

    def _blocks(self, lines: list[str], i: int, end: int) -> list[str]:
        out: list[str] = []
        while i < end:
            line = lines[i]
            stripped = line.strip()

            if not stripped:
                i += 1
                continue

            if stripped.startswith("```"):
                i = self._code(lines, i, end, out)
            elif stripped.startswith(":::"):
                i = self._directive(lines, i, end, out)
            elif stripped.startswith("#"):
                i = self._heading(stripped, i, out)
            elif stripped in ("---", "***"):
                out.append("<hr>")
                i += 1
            elif stripped.startswith(">"):
                i = self._quote(lines, i, end, out)
            elif stripped.startswith("|"):
                i = self._table(lines, i, end, out)
            elif re.match(r"^([-*]|\d+\.)\s+", stripped):
                i = self._list(lines, i, end, out)
            elif stripped.startswith("<"):
                i = self._raw_html(lines, i, end, out)
            else:
                i = self._paragraph(lines, i, end, out)
        return out

    # -- individual blocks -------------------------------------------------

    def _heading(self, stripped: str, i: int, out: list[str]) -> int:
        level = len(stripped) - len(stripped.lstrip("#"))
        text = inline(stripped[level:].strip())
        level = min(max(level, 2), 5)
        ident = slug(text)
        if level in (2, 3):
            self.headings.append((level, ident, re.sub(r"<[^>]+>", "", text)))
        out.append(f'<h{level} id="{ident}">{text}</h{level}>')
        return i + 1

    def _code(self, lines: list[str], i: int, end: int, out: list[str]) -> int:
        info = lines[i].strip()[3:].strip()
        lang, _, rest = info.partition(" ")
        title = ""
        m = re.search(r'title=(?:"([^"]*)"|(\S+))', rest)
        if m:
            title = m.group(1) or m.group(2)
        i += 1
        body: list[str] = []
        while i < end and not lines[i].strip().startswith("```"):
            body.append(lines[i])
            i += 1
        i += 1  # closing fence
        code = html.escape("\n".join(body))
        head = f'<div class="code-title">{html.escape(title)}</div>' if title else ""
        out.append(
            f'<figure class="code" data-lang="{html.escape(lang)}">{head}'
            f'<button class="copy" type="button" aria-label="Copy code">copy</button>'
            f'<pre><code class="lang-{html.escape(lang)}">{code}</code></pre></figure>'
        )
        return i

    def _directive(self, lines: list[str], i: int, end: int, out: list[str]) -> int:
        header = lines[i].strip()[3:].strip()
        name, _, title = header.partition(" ")
        i += 1
        body: list[str] = []
        depth = 1
        while i < end:
            s = lines[i].strip()
            if s.startswith(":::"):
                if s == ":::":
                    depth -= 1
                    if depth == 0:
                        i += 1
                        break
                else:
                    depth += 1
            body.append(lines[i])
            i += 1

        if name == "widget":
            out.append(self.widget_renderer(title.strip(), "\n".join(body)))
            return i

        inner = "\n".join(self._blocks(body, 0, len(body)))

        if name == "deeper":
            summary = title.strip() or "Go deeper (optional)"
            out.append(
                '<details class="deeper"><summary>%s</summary>'
                '<div class="deeper-body">%s</div></details>' % (summary, inner)
            )
            return i

        if name == "jargon":
            term = title.strip()
            out.append(
                '<aside class="jargon"><h4>%s</h4><div class="callout-body">%s</div>'
                '</aside>' % (term, inner)
            )
            return i

        if name == "objectives":
            heading = title.strip() or "By the end of this module you can"
            out.append(
                '<div class="objectives"><h4>%s</h4>%s</div>' % (heading, inner)
            )
            return i

        label = title.strip() or _DIRECTIVE_LABELS.get(name, name.title())
        out.append(
            f'<aside class="callout c-{html.escape(name)}">'
            f'<h4>{inline(label)}</h4><div class="callout-body">{inner}</div></aside>'
        )
        return i

    def _quote(self, lines: list[str], i: int, end: int, out: list[str]) -> int:
        body: list[str] = []
        while i < end and lines[i].strip().startswith(">"):
            body.append(re.sub(r"^\s*>\s?", "", lines[i]))
            i += 1
        inner = "\n".join(self._blocks(body, 0, len(body)))
        out.append(f"<blockquote>{inner}</blockquote>")
        return i

    def _table(self, lines: list[str], i: int, end: int, out: list[str]) -> int:
        rows: list[list[str]] = []
        while i < end and lines[i].strip().startswith("|"):
            cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
            rows.append(cells)
            i += 1
        if len(rows) >= 2 and all(set(c) <= set("-: ") and c for c in rows[1]):
            header, body = rows[0], rows[2:]
        else:
            header, body = [], rows
        parts = ['<div class="table-wrap"><table>']
        if header:
            parts.append("<thead><tr>" + "".join(f"<th>{inline(c)}</th>" for c in header) + "</tr></thead>")
        parts.append("<tbody>")
        for r in body:
            parts.append("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>")
        parts.append("</tbody></table></div>")
        out.append("".join(parts))
        return i

    def _list(self, lines: list[str], i: int, end: int, out: list[str]) -> int:
        ordered = bool(re.match(r"^\d+\.\s+", lines[i].strip()))
        items: list[list[str]] = []
        while i < end:
            line = lines[i]
            stripped = line.strip()
            if not stripped:
                # A blank line ends the list unless the next line continues it.
                if i + 1 < end and re.match(r"^\s+\S", lines[i + 1]):
                    i += 1
                    continue
                break
            m = re.match(r"^([-*]|\d+\.)\s+(.*)$", stripped)
            if m and not line.startswith("  "):
                items.append([m.group(2)])
            elif items:
                items[-1].append(stripped)
            else:
                break
            i += 1

        tag = "ol" if ordered else "ul"
        parts = [f"<{tag}>"]
        for item in items:
            head = item[0]
            rest = item[1:]
            nested = [r for r in rest if re.match(r"^([-*]|\d+\.)\s+", r)]
            plain = [r for r in rest if r not in nested]
            body = inline(" ".join([head] + plain))
            if nested:
                sub = "".join(
                    "<li>" + inline(_BULLET.sub("", n)) + "</li>" for n in nested
                )
                body += f"<ul>{sub}</ul>"
            parts.append(f"<li>{body}</li>")
        parts.append(f"</{tag}>")
        out.append("".join(parts))
        return i

    def _raw_html(self, lines: list[str], i: int, end: int, out: list[str]) -> int:
        block: list[str] = []
        while i < end and lines[i].strip():
            block.append(lines[i])
            i += 1
        out.append("\n".join(block))
        return i

    def _paragraph(self, lines: list[str], i: int, end: int, out: list[str]) -> int:
        buf: list[str] = []
        while i < end:
            s = lines[i].strip()
            if not s or s.startswith(("```", ":::", "#", ">", "|")) or s in ("---", "***"):
                break
            if re.match(r"^([-*]|\d+\.)\s+", s):
                break
            buf.append(s)
            i += 1
        out.append("<p>" + inline(" ".join(buf)) + "</p>")
        return i


_DIRECTIVE_LABELS = {
    "autopsy": "Autopsy",
    "gate": "Ship gate",
    "warn": "Watch out",
    "note": "Note",
    "key": "The idea in one line",
    "lab": "Lab",
    "try": "Try it",
}


def render(src: str, widget_renderer=None) -> tuple[str, list[tuple[int, str, str]]]:
    r = Renderer(widget_renderer)
    body = r.render(src)
    return body, r.headings
