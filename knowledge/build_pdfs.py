#!/usr/bin/env python
"""Convert the Markdown help articles in src/ to PDFs in pdf/.

Usage (from the repository root):
    .venv/bin/python knowledge/build_pdfs.py                   # Orbit (saas): src/ -> pdf/
    .venv/bin/python knowledge/build_pdfs.py --domain telecom  # Nimbus: telecom/src/ -> telecom/pdf/

Requires the `markdown` and `reportlab` packages (both in the project venv).
Each src/NN-name.md becomes pdf/NN-name.pdf. The first H1 of the article is
used as the document title and as the running page header. Only the public
bucket (src/) is rendered; internal/ and restricted/ stay Markdown-only.
"""
from __future__ import annotations

import math
import sys
from html.parser import HTMLParser
from pathlib import Path
from xml.sax.saxutils import escape

import markdown
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

HERE = Path(__file__).resolve().parent

# domain -> (source dir, output dir, brand shown in the running header, PDF author)
DOMAINS = {
    "saas": (HERE / "src", HERE / "pdf",
             "Orbit Analytics Help Center", "Orbit Analytics (fictional)"),
    "telecom": (HERE / "telecom" / "src", HERE / "telecom" / "pdf",
                "Nimbus Mobile Help Center", "Nimbus Mobile (fictional)"),
}
DEFAULT_DOMAIN = "saas"

PAGE_SIZE = letter
MARGIN = 1 * inch
BODY_FONT = "Helvetica"
BOLD_FONT = "Helvetica-Bold"
BODY_SIZE = 11
BODY_LEADING = 15
CONTENT_WIDTH = PAGE_SIZE[0] - 2 * MARGIN

STYLES = {
    "title": ParagraphStyle("title", fontName=BOLD_FONT, fontSize=22, leading=27,
                            spaceAfter=14, textColor=colors.HexColor("#1f2a44")),
    "h2": ParagraphStyle("h2", fontName=BOLD_FONT, fontSize=15, leading=19,
                         spaceBefore=16, spaceAfter=6, textColor=colors.HexColor("#1f2a44")),
    "h3": ParagraphStyle("h3", fontName=BOLD_FONT, fontSize=12.5, leading=16,
                         spaceBefore=12, spaceAfter=4, textColor=colors.HexColor("#1f2a44")),
    "h4": ParagraphStyle("h4", fontName=BOLD_FONT, fontSize=BODY_SIZE, leading=BODY_LEADING,
                         spaceBefore=10, spaceAfter=3),
    "body": ParagraphStyle("body", fontName=BODY_FONT, fontSize=BODY_SIZE, leading=BODY_LEADING,
                           spaceAfter=8, alignment=TA_LEFT),
    "list": ParagraphStyle("list", fontName=BODY_FONT, fontSize=BODY_SIZE, leading=BODY_LEADING,
                           spaceAfter=3),
    "cell": ParagraphStyle("cell", fontName=BODY_FONT, fontSize=9.5, leading=12),
    "cell_head": ParagraphStyle("cell_head", fontName=BOLD_FONT, fontSize=9.5, leading=12),
}


class Block:
    """One top-level block collected from the HTML stream."""

    def __init__(self, kind: str, **attrs):
        self.kind = kind
        self.attrs = attrs
        self.text = ""          # inline markup for paragraphs / headings
        self.items: list[str] = []   # list items
        self.rows: list[list[tuple[str, bool]]] = []  # table rows: (markup, is_header)


class ArticleParser(HTMLParser):
    """Turn python-markdown's HTML into a flat list of Blocks with reportlab inline markup."""

    INLINE = {"strong": ("<b>", "</b>"), "b": ("<b>", "</b>"),
              "em": ("<i>", "</i>"), "i": ("<i>", "</i>"),
              "code": ('<font face="Courier" size="10">', "</font>")}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.blocks: list[Block] = []
        self.current: Block | None = None
        self.buffer: list[str] = []
        self.in_cell = False
        self.cell_is_header = False
        self.row: list[tuple[str, bool]] | None = None
        self.in_li = False

    # -- helpers -----------------------------------------------------------
    def _flush_text(self) -> str:
        text = "".join(self.buffer).strip()
        self.buffer = []
        return text

    def _close_block(self):
        if self.current is not None:
            if self.current.kind in ("p", "h1", "h2", "h3", "h4"):
                self.current.text = self._flush_text()
                if self.current.text:
                    self.blocks.append(self.current)
            else:
                self.blocks.append(self.current)
        self.current = None

    # -- tag handlers ------------------------------------------------------
    def handle_starttag(self, tag, attrs):
        if tag in ("h1", "h2", "h3", "h4", "p"):
            if self.in_li or self.in_cell:
                return  # paragraph inside a list item or cell: keep inline
            self._close_block()
            self.current = Block(tag)
        elif tag in ("ul", "ol"):
            self._close_block()
            self.current = Block(tag)
        elif tag == "li":
            self.in_li = True
            self.buffer = []
        elif tag == "table":
            self._close_block()
            self.current = Block("table")
        elif tag == "tr":
            self.row = []
        elif tag in ("td", "th"):
            self.in_cell = True
            self.cell_is_header = tag == "th"
            self.buffer = []
        elif tag == "hr":
            self._close_block()
            self.blocks.append(Block("hr"))
        elif tag == "br":
            self.buffer.append("<br/>")
        elif tag in self.INLINE:
            self.buffer.append(self.INLINE[tag][0])
        # <a>, <thead>, <tbody> and anything else: text passes through

    def handle_endtag(self, tag):
        if tag in ("h1", "h2", "h3", "h4", "p"):
            if self.in_li or self.in_cell:
                self.buffer.append(" ")
                return
            self._close_block()
        elif tag in ("ul", "ol"):
            self._close_block()
        elif tag == "li":
            self.in_li = False
            text = self._flush_text()
            if self.current is not None and self.current.kind in ("ul", "ol") and text:
                self.current.items.append(text)
        elif tag in ("td", "th"):
            self.in_cell = False
            text = self._flush_text()
            if self.row is not None:
                self.row.append((text, self.cell_is_header))
        elif tag == "tr":
            if self.row is not None and self.current is not None and self.current.kind == "table":
                self.current.rows.append(self.row)
            self.row = None
        elif tag == "table":
            self._close_block()
        elif tag in self.INLINE:
            self.buffer.append(self.INLINE[tag][1])

    def handle_data(self, data):
        if self.current is None and not self.in_cell and not self.in_li:
            return  # whitespace between blocks
        self.buffer.append(escape(data))

    def close(self):
        super().close()
        self._close_block()


def build_table(block: Block):
    rows = block.rows
    if not rows:
        return None
    ncols = max(len(r) for r in rows)
    # Weight column widths by the longest plain-text cell in each column.
    weights = []
    for c in range(ncols):
        longest = max((len(r[c][0]) for r in rows if c < len(r)), default=1)
        weights.append(math.sqrt(max(longest, 4)))
    total = sum(weights)
    col_widths = [CONTENT_WIDTH * w / total for w in weights]

    data = []
    for r in rows:
        cells = []
        for c in range(ncols):
            text, is_head = r[c] if c < len(r) else ("", False)
            cells.append(Paragraph(text, STYLES["cell_head" if is_head else "cell"]))
        data.append(cells)

    table = Table(data, colWidths=col_widths, repeatRows=1, hAlign="LEFT")
    style = [
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#b8bfcc")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    if rows and any(h for _, h in rows[0]):
        style.append(("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e9edf4")))
    table.setStyle(TableStyle(style))
    return table


def blocks_to_flowables(blocks: list[Block]):
    story = []
    for block in blocks:
        if block.kind == "h1":
            story.append(Paragraph(block.text, STYLES["title"]))
            story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#1f2a44"),
                                    spaceAfter=10))
        elif block.kind in ("h2", "h3", "h4"):
            story.append(Paragraph(block.text, STYLES[block.kind]))
        elif block.kind == "p":
            story.append(Paragraph(block.text, STYLES["body"]))
        elif block.kind in ("ul", "ol"):
            items = [ListItem(Paragraph(t, STYLES["list"]), leftIndent=18) for t in block.items]
            if block.kind == "ol":
                lf = ListFlowable(items, bulletType="1", bulletFormat="%s.", leftIndent=18,
                                  bulletFontName=BODY_FONT, bulletFontSize=BODY_SIZE)
            else:
                lf = ListFlowable(items, bulletType="bullet", start="•", leftIndent=18,
                                  bulletFontName=BODY_FONT, bulletFontSize=BODY_SIZE)
            story.append(lf)
            story.append(Spacer(1, 6))
        elif block.kind == "table":
            table = build_table(block)
            if table is not None:
                story.append(table)
                story.append(Spacer(1, 10))
        elif block.kind == "hr":
            story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#b8bfcc"),
                                    spaceBefore=8, spaceAfter=8))
    return story


def make_page_decorator(title: str, brand: str):
    def decorate(canvas, doc):
        canvas.saveState()
        width, height = PAGE_SIZE
        canvas.setFont(BODY_FONT, 9)
        canvas.setFillColor(colors.HexColor("#5a6478"))
        canvas.drawString(MARGIN, height - 0.65 * inch, title)
        canvas.drawRightString(width - MARGIN, height - 0.65 * inch, brand)
        canvas.setStrokeColor(colors.HexColor("#b8bfcc"))
        canvas.setLineWidth(0.5)
        canvas.line(MARGIN, height - 0.72 * inch, width - MARGIN, height - 0.72 * inch)
        canvas.drawCentredString(width / 2, 0.6 * inch, f"Page {doc.page}")
        canvas.drawString(MARGIN, 0.6 * inch, "Fictional demo content")
        canvas.restoreState()
    return decorate


def convert(md_path: Path, pdf_path: Path, brand: str, author: str) -> None:
    html = markdown.markdown(md_path.read_text(encoding="utf-8"), extensions=["tables"])
    parser = ArticleParser()
    parser.feed(html)
    parser.close()

    title = next((b.text for b in parser.blocks if b.kind == "h1"), md_path.stem)
    # Strip inline markup from the running header.
    plain_title = title.replace("<b>", "").replace("</b>", "").replace("<i>", "").replace("</i>", "")

    doc = SimpleDocTemplate(
        str(pdf_path), pagesize=PAGE_SIZE,
        leftMargin=MARGIN, rightMargin=MARGIN, topMargin=MARGIN, bottomMargin=MARGIN,
        title=plain_title, author=author, subject="Help center article",
    )
    decorate = make_page_decorator(plain_title, brand)
    doc.build(blocks_to_flowables(parser.blocks), onFirstPage=decorate, onLaterPages=decorate)


def main(argv: list[str]) -> int:
    args = argv[1:]
    domain = DEFAULT_DOMAIN
    if "--domain" in args:
        i = args.index("--domain")
        if i + 1 >= len(args) or args[i + 1] not in DOMAINS:
            print(f"--domain must be one of: {', '.join(DOMAINS)}", file=sys.stderr)
            return 2
        domain = args[i + 1]
        del args[i:i + 2]
    src_dir, pdf_dir, brand, author = DOMAINS[domain]

    pdf_dir.mkdir(parents=True, exist_ok=True)
    sources = sorted(src_dir.glob("*.md"))
    if args:
        sources = [src_dir / Path(a).name for a in args]
    if not sources:
        print(f"No Markdown files found in {src_dir}", file=sys.stderr)
        return 1
    for src in sources:
        out = pdf_dir / (src.stem + ".pdf")
        convert(src, out, brand, author)
        print(f"{src.name} -> {out.relative_to(HERE)} ({out.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
