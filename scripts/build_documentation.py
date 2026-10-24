"""Build the user and theory PDFs from the Markdown sources in docs/."""

from __future__ import annotations

import re
from html import escape
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfdoc import PDFDictionary
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    Flowable,
    ListFlowable,
    ListItem,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
)


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
ACCENT = colors.HexColor("#176b73")
INK = colors.HexColor("#1d2935")
MUTED = colors.HexColor("#607080")

def styles_for_document():
    """Create a readable, consistent type scale for both guides."""
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "GuideTitle", parent=base["Title"], fontName="Helvetica-Bold",
            fontSize=25, leading=31, textColor=colors.white, alignment=TA_LEFT,
            spaceAfter=8,
        ),
        "subtitle": ParagraphStyle(
            "GuideSubtitle", parent=base["Normal"], fontName="Helvetica",
            fontSize=11, leading=16, textColor=colors.HexColor("#e5f1f1"),
            spaceAfter=10,
        ),
        "h2": ParagraphStyle(
            "Section", parent=base["Heading2"], fontName="Helvetica-Bold",
            fontSize=15, leading=19, textColor=ACCENT, spaceBefore=12,
            spaceAfter=7, keepWithNext=True,
        ),
        "h3": ParagraphStyle(
            "Subsection", parent=base["Heading3"], fontName="Helvetica-Bold",
            fontSize=10.5, leading=14, textColor=INK, spaceBefore=8,
            spaceAfter=4, keepWithNext=True,
        ),
        "body": ParagraphStyle(
            "GuideBody", parent=base["BodyText"], fontName="Helvetica",
            fontSize=9.25, leading=13, textColor=INK, spaceAfter=6,
            alignment=TA_JUSTIFY,
        ),
        "bullet": ParagraphStyle(
            "GuideBullet", parent=base["BodyText"], fontName="Helvetica",
            fontSize=9.1, leading=12.5, textColor=INK, spaceAfter=2,
            alignment=TA_JUSTIFY,
        ),
        "cover": ParagraphStyle(
            "CoverText", parent=base["BodyText"], fontName="Helvetica",
            fontSize=10.25, leading=15, textColor=colors.white, spaceAfter=8,
            alignment=TA_JUSTIFY,
        ),
        "equation": ParagraphStyle(
            "Equation", parent=base["Code"], fontName="Courier",
            fontSize=8.3, leading=12, textColor=INK, alignment=TA_CENTER,
            backColor=colors.HexColor("#f2f6f7"), borderColor=colors.HexColor("#d8e1e6"),
            borderWidth=0.5, borderPadding=6, spaceBefore=8, spaceAfter=10,
        ),
        "caption": ParagraphStyle(
            "FigureCaption", parent=base["Normal"], fontName="Helvetica-Oblique",
            fontSize=8, leading=10, alignment=TA_CENTER, textColor=MUTED,
            spaceBefore=3, spaceAfter=8,
        ),
    }


class GuideDocTemplate(BaseDocTemplate):
    """Collect section destinations while laying out a guide."""

    def __init__(self, filename: Path, title: str):
        super().__init__(
            str(filename), pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm,
            topMargin=20 * mm, bottomMargin=19 * mm, title=title,
            author="OpTurbo project",
        )
        frame = Frame(
            self.leftMargin, self.bottomMargin, self.width, self.height,
            id="main", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0,
        )
        self.addPageTemplates(PageTemplate(id="guide", frames=frame, onPage=self.draw_page))

    @staticmethod
    def draw_page(canvas, doc):
        """Draw the restrained running header, accent line, and page number."""
        canvas.saveState()
        width, height = A4
        if doc.page == 1:
            canvas.setFillColor(ACCENT)
            canvas.rect(0, height - 160 * mm, width, 160 * mm, fill=1, stroke=0)
        else:
            canvas.setStrokeColor(colors.HexColor("#d8e1e6"))
            canvas.setLineWidth(0.5)
            canvas.line(20 * mm, height - 13 * mm, width - 20 * mm, height - 13 * mm)
            canvas.setFont("Helvetica", 8)
            canvas.setFillColor(MUTED)
            canvas.drawString(20 * mm, height - 10 * mm, "OPTURBO  /  ENGINEERING GUIDE")
        canvas.setStrokeColor(colors.HexColor("#d8e1e6"))
        canvas.line(20 * mm, 13 * mm, width - 20 * mm, 13 * mm)
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(MUTED)
        canvas.drawRightString(width - 20 * mm, 8 * mm, f"{doc.page}")
        canvas.restoreState()

    def afterFlowable(self, flowable):
        """Add a numbered PDF outline entry and remember its named destination."""
        anchor = getattr(flowable, "section_anchor", None)
        title = getattr(flowable, "section_title", None)
        if anchor and title:
            heading_top = self.frame._y + flowable.getSpaceAfter() + flowable.height
            destination = self.canv.bookmarkPage(anchor, fit="FitH", top=heading_top)
            self.canv.addOutlineEntry(title, anchor, flowable.section_level, False)
            catalog = self.canv._doc.Catalog
            named_destinations = getattr(catalog, "Dests", None)
            if named_destinations is None:
                named_destinations = catalog.Dests = PDFDictionary({})
            named_destinations[anchor] = destination


def inline_markup(text: str) -> str:
    """Escape Markdown text and retain its simple bold and code emphasis."""
    output = escape(text, quote=False)
    replacements: list[str] = []

    def save_replacement(match):
        replacements.append(match.group(1))
        return f"\x00{len(replacements) - 1}\x00"

    output = re.sub(r"`([^`]+)`", save_replacement, output)
    output = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", output)
    for index, code in enumerate(replacements):
        output = output.replace(f"\x00{index}\x00", f'<font name="Courier">{code}</font>')
    return output


class DiagramFlowable(Flowable):
    """Draw a compact, vector workflow diagram on the current PDF page."""

    def __init__(self, kind: str, width: float):
        super().__init__()
        self.kind = kind
        self.width = width
        self.height = 37 * mm

    def draw(self):
        canvas = self.canv
        if self.kind == "cfd_bem_coupling":
            labels = ["Fluent flow", "Radial reports", "BEM blade loads", "Relaxed sources"]
            colors_ = ["#e9f3f4", "#f3f5f7", "#e9f3f4", "#f3f5f7"]
        else:
            labels = ["Initialize", "Evaluate", "Select parents", "Cross over", "Mutate + clamp", "Keep elites"]
            colors_ = ["#e9f3f4", "#f3f5f7", "#e9f3f4", "#f3f5f7", "#e9f3f4", "#f3f5f7"]
        gap = 6
        box_w = (self.width - gap * (len(labels) - 1)) / len(labels)
        box_h = 19 * mm
        y = 13 * mm
        for index, (label, fill) in enumerate(zip(labels, colors_)):
            x = index * (box_w + gap)
            canvas.setFillColor(colors.HexColor(fill))
            canvas.setStrokeColor(colors.HexColor("#9fb5bc"))
            canvas.roundRect(x, y, box_w, box_h, 5, fill=1, stroke=1)
            canvas.setFillColor(INK)
            canvas.setFont("Helvetica-Bold", 7.5)
            words = label.split()
            if len(label) > 15 and len(words) > 1:
                midpoint = max(1, len(words) // 2)
                lines = (" ".join(words[:midpoint]), " ".join(words[midpoint:]))
            else:
                lines = (label,)
            for line_no, line in enumerate(lines):
                canvas.drawCentredString(x + box_w / 2, y + box_h / 2 + (3 if len(lines) == 2 else 0) - line_no * 10, line)
            if index < len(labels) - 1:
                x1 = x + box_w + 1
                x2 = x + box_w + gap - 1
                mid_y = y + box_h / 2
                canvas.setStrokeColor(ACCENT)
                canvas.setFillColor(ACCENT)
                canvas.setLineWidth(1.1)
                canvas.line(x1, mid_y, x2, mid_y)
                canvas.line(x2 - 3, mid_y + 3, x2, mid_y)
                canvas.line(x2 - 3, mid_y - 3, x2, mid_y)
        target_index = 0 if self.kind == "cfd_bem_coupling" else 1
        target_mid = target_index * (box_w + gap) + box_w / 2
        right_mid = (len(labels) - 1) * (box_w + gap) + box_w / 2
        lower_y = 4 * mm
        canvas.setStrokeColor(ACCENT)
        canvas.setFillColor(ACCENT)
        canvas.setLineWidth(1.1)
        canvas.line(right_mid, y - 1, right_mid, lower_y)
        canvas.line(right_mid, lower_y, target_mid, lower_y)
        canvas.line(target_mid, lower_y, target_mid, y - 1)
        canvas.line(target_mid - 3, y - 4, target_mid, y - 1)
        canvas.line(target_mid + 3, y - 4, target_mid, y - 1)


def parse_markdown(path: Path, styles: dict[str, ParagraphStyle], cover: bool):
    """Convert the small Markdown subset used by the guide sources."""
    lines = path.read_text(encoding="utf-8").splitlines()
    story = []
    paragraph: list[str] = []
    bullet_items: list[str] = []
    number_items: list[str] = []
    saw_title = False
    first_section = True
    available_width = A4[0] - 40 * mm
    in_equation = False
    equation_lines: list[str] = []
    chapter_number = 0
    subsection_number = 0

    def flush_paragraph():
        nonlocal paragraph
        if paragraph:
            story.append(Paragraph(inline_markup(" ".join(paragraph)), styles["cover" if cover and first_section else "body"]))
            paragraph = []

    def flush_lists():
        nonlocal bullet_items, number_items
        if bullet_items:
            items = [ListItem(Paragraph(inline_markup(item), styles["bullet"]), leftIndent=8) for item in bullet_items]
            story.append(ListFlowable(items, bulletType="bullet", start="circle", leftIndent=15,
                                      bulletFontName="Helvetica", bulletFontSize=7,
                                      spaceBefore=1, spaceAfter=6))
            bullet_items = []
        if number_items:
            items = [ListItem(Paragraph(inline_markup(item), styles["bullet"]), leftIndent=10) for item in number_items]
            story.append(ListFlowable(items, bulletType="1", leftIndent=18,
                                      bulletFontName="Helvetica", bulletFontSize=8,
                                      spaceBefore=1, spaceAfter=6))
            number_items = []

    for line in lines:
        raw = line.strip()
        if raw == "$$":
            if in_equation:
                story.append(Paragraph(inline_markup(" ".join(equation_lines)), styles["equation"]))
                equation_lines.clear()
                in_equation = False
            else:
                flush_paragraph()
                flush_lists()
                in_equation = True
            continue
        if in_equation:
            equation_lines.append(raw)
            continue
        if not raw:
            flush_paragraph()
            flush_lists()
            continue
        image = re.match(r"^!\[([^\]]*)\]\(([^)]+)\)$", raw)
        if image:
            flush_paragraph()
            flush_lists()
            relative_image = Path(image.group(2))
            if relative_image.parts[:1] != ("images",):
                raise ValueError(f"Documentation images must be relative to docs/images: {relative_image}")
            image_path = DOCS / relative_image
            if not image_path.is_file():
                raise FileNotFoundError(f"Missing documentation figure: {image_path}")
            story.append(DiagramFlowable(image_path.stem, available_width))
            story.append(Paragraph(inline_markup(image.group(1)), styles["caption"]))
            continue
        heading = re.match(r"^(#{1,3})\s+(.+)$", raw)
        if heading:
            flush_paragraph()
            flush_lists()
            level = len(heading.group(1))
            content = heading.group(2)
            anchor_match = re.search(r"\s+\{#([a-z0-9-]+)\}$", content)
            anchor = anchor_match.group(1) if anchor_match else None
            title = content[:anchor_match.start()].rstrip() if anchor_match else content
            if level == 1:
                if saw_title:
                    story.append(Paragraph(inline_markup(title), styles["h2"]))
                else:
                    story.append(Spacer(1, 45 * mm))
                    story.append(Paragraph(inline_markup(title), styles["title"]))
                    saw_title = True
            else:
                if cover and level == 2:
                    if first_section:
                        story.append(PageBreak())
                        first_section = False
                if level == 2:
                    chapter_number += 1
                    subsection_number = 0
                    title = f"{chapter_number}. {title}"
                elif level == 3:
                    subsection_number += 1
                    title = f"{chapter_number}.{subsection_number} {title}"
                if anchor is None:
                    anchor = (
                        f"chapter-{chapter_number}"
                        if level == 2
                        else f"section-{chapter_number}-{subsection_number}"
                    )
                style = styles["h2"] if level == 2 else styles["h3"]
                item = Paragraph(inline_markup(title), style)
                item.section_anchor = anchor
                item.section_title = title
                item.section_level = level - 2
                story.append(item)
            continue
        bullet = re.match(r"^[-*]\s+(.+)$", raw)
        numbered = re.match(r"^\d+[.)]\s+(.+)$", raw)
        if bullet:
            flush_paragraph()
            if number_items:
                flush_lists()
            bullet_items.append(bullet.group(1))
            continue
        if numbered:
            flush_paragraph()
            if bullet_items:
                flush_lists()
            number_items.append(numbered.group(1))
            continue
        flush_lists()
        paragraph.append(raw)
    flush_paragraph()
    flush_lists()
    if in_equation:
        raise ValueError(f"Unclosed display equation in {path}")
    return story


def build_guide(source: Path, target: Path, title: str) -> None:
    """Build a continuously flowing, numbered PDF with chapter bookmarks."""
    styles = styles_for_document()
    doc = GuideDocTemplate(target, title)
    doc.build(parse_markdown(source, styles, cover=True))


def main() -> None:
    """Build the user manual and engineering theory PDF guides."""
    build_guide(DOCS / "manual.md", DOCS / "manual.pdf", "OpTurbo User Manual")
    build_guide(DOCS / "theory.md", DOCS / "theory.pdf", "OpTurbo Theory Guide")


if __name__ == "__main__":
    main()
