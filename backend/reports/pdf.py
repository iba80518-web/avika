from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


def render_report_pdf(text):
    """Met en page le texte d'un rapport (même contenu que le message WhatsApp) en PDF A4.

    Le PDF ne contient que les lignes déjà filtrées par droits : il ne peut rien montrer de plus.
    """
    styles = getSampleStyleSheet()
    title = ParagraphStyle("title", parent=styles["Title"], fontSize=18, leading=22, alignment=0)
    section = ParagraphStyle("section", parent=styles["Heading3"], spaceBefore=6)
    body = ParagraphStyle("body", parent=styles["BodyText"], fontSize=11, leading=16)

    story = []
    for index, line in enumerate(text.split("\n")):
        clean = escape(line.replace("*", ""))
        if index == 0:
            story.append(Paragraph(clean, title))
        elif not line.strip():
            story.append(Spacer(1, 0.3 * cm))
        elif line.endswith(":") and not line.startswith("-"):
            story.append(Paragraph(clean, section))
        else:
            story.append(Paragraph(clean, body))

    buffer = BytesIO()
    SimpleDocTemplate(
        buffer, pagesize=A4, title="AVIKA — Rapport", author="AVIKA",
        leftMargin=2 * cm, rightMargin=2 * cm, topMargin=2 * cm, bottomMargin=2 * cm,
    ).build(story)
    return buffer.getvalue()
