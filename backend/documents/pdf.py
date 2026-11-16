from datetime import date
from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .logo import logo_file

DEFAULT_ACCENT = "#1F7A4D"
GREY = colors.HexColor("#555555")


def _money(value, currency):
    return f"{int(value):,}".replace(",", " ") + f" {currency}".rstrip()


def _day(iso):
    return date.fromisoformat(iso).strftime("%d/%m/%Y")


def _text(value):
    """Texte saisi par l'utilisateur : neutralisé avant d'entrer dans la mise en page."""
    return escape(str(value or ""))


def _accent(value):
    try:
        return colors.HexColor(value or DEFAULT_ACCENT)
    except (ValueError, TypeError):
        return colors.HexColor(DEFAULT_ACCENT)


def _logo(path):
    """Le logo, ou rien si le fichier manque : le PDF se génère toujours."""
    if not path:
        return None
    try:
        file = logo_file(path)
        if not file.is_file():
            return None
        width, height = ImageReader(str(file)).getSize()
        scale = min(4 * cm / width, 2.2 * cm / height)
        return Image(str(file), width=width * scale, height=height * scale, hAlign="LEFT")
    except Exception:  # un logo illisible ne doit jamais empêcher d'émettre la facture
        return None


def render_document_pdf(document, *, cancelled=False):
    """PDF A4 d'une facture ou d'un reçu, à partir de la copie figée à l'émission."""
    content = document.content
    currency = content.get("currency", "")
    issuer = content["issuer"]
    sale = content["sale"]
    is_receipt = document.kind == "receipt"
    accent = _accent(issuer.get("accent_color"))

    styles = getSampleStyleSheet()
    normal = ParagraphStyle("n", parent=styles["BodyText"], fontSize=10, leading=14)
    small = ParagraphStyle("s", parent=normal, fontSize=8.5, leading=12, textColor=GREY)
    bold = ParagraphStyle("b", parent=normal, fontName="Helvetica-Bold")
    name = ParagraphStyle("name", parent=bold, fontSize=14, leading=18)
    title = ParagraphStyle(
        "t", parent=bold, fontSize=24, leading=28, alignment=TA_RIGHT, textColor=accent
    )
    right = ParagraphStyle("r", parent=normal, alignment=TA_RIGHT)
    centered = ParagraphStyle("c", parent=small, alignment=TA_CENTER)
    label = ParagraphStyle("l", parent=small, textColor=accent, fontName="Helvetica-Bold")

    story = []

    # --- En-tête : logo + coordonnées à gauche, titre et numéro à droite
    left = []
    logo = _logo(issuer.get("logo_path"))
    if logo is not None:
        left += [logo, Spacer(1, 0.2 * cm)]
    left.append(Paragraph(_text(issuer.get("name")), name))
    lines = [issuer.get("address"), issuer.get("phone") and f"Tél : {issuer['phone']}", issuer.get("email")]
    legal = [issuer.get("tax_id") and f"NIF : {issuer['tax_id']}",
             issuer.get("registry_id") and f"RCCM : {issuer['registry_id']}"]
    for line in [*lines, *legal]:
        if line:
            left.append(Paragraph(_text(line), small))
    head_right = [
        Paragraph("REÇU" if is_receipt else "FACTURE", title),
        Paragraph(f"N° {_text(document.number)}", ParagraphStyle("nr", parent=right, fontName="Helvetica-Bold")),
        Paragraph(f"Émis le {_day(document.issued_on.isoformat())}", right),
    ]
    header = Table([[left, head_right]], colWidths=[9.8 * cm, 7 * cm])
    header.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                                ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
    story += [header, Spacer(1, 0.6 * cm)]

    # --- Client et vente
    customer = content.get("customer")
    who = [Paragraph("REÇU DE" if is_receipt else "FACTURÉ À", label)]
    if customer is None:
        who.append(Paragraph("Client de passage", normal))
    else:
        who.append(Paragraph(_text(customer.get("name")), bold))
        for line in (customer.get("phone"), customer.get("address")):
            if line:
                who.append(Paragraph(_text(line), small))
    about = [
        Paragraph("VENTE", label),
        Paragraph(f"N° {sale['id']} du {_day(sale['date'])}", normal),
        Paragraph(f"Bande : {_text(sale.get('cycle'))}", small),
    ]
    info = Table([[who, about]], colWidths=[9.8 * cm, 7 * cm])
    info.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                              ("LEFTPADDING", (0, 0), (-1, -1), 0)]))
    story += [info, Spacer(1, 0.6 * cm)]

    # --- Lignes de la vente
    rows = [["Désignation", "Quantité", "Prix unitaire", "Montant"]]
    for line in sale["lines"]:
        rows.append([
            Paragraph(_text(line["label"]), normal),
            f"{line['quantity']} {line['unit']}",
            _money(line["unit_price"], currency),
            _money(line["total"], currency),
        ])
    table = Table(rows, colWidths=[7.2 * cm, 3 * cm, 3.3 * cm, 3.3 * cm], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), accent),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBELOW", (0, 1), (-1, -1), 0.4, colors.HexColor("#DDDDDD")),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story += [table, Spacer(1, 0.5 * cm)]
    if sale.get("note"):
        story += [Paragraph(f"Note : {_text(sale['note'])}", small), Spacer(1, 0.3 * cm)]

    # --- Reçu : le montant reçu en évidence
    if is_receipt:
        payment = content["payment"]
        box = Table(
            [[Paragraph("MONTANT REÇU", label)],
             [Paragraph(_money(payment["amount"], currency),
                        ParagraphStyle("big", parent=bold, fontSize=20, leading=26, textColor=accent))],
             [Paragraph(f"{_text(payment['method'])} — le {_day(payment['date'])}", normal)]],
            colWidths=[16.8 * cm],
        )
        box.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 1, accent),
                                 ("LEFTPADDING", (0, 0), (-1, -1), 12),
                                 ("TOPPADDING", (0, 0), (-1, -1), 4),
                                 ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
        story += [box, Spacer(1, 0.4 * cm)]

    # --- Totaux
    paid_label = "Cumul payé (ce paiement inclus)" if is_receipt else "Déjà payé"
    total_label = "Total de la vente" if is_receipt else "Total"
    totals = Table(
        [[total_label, _money(sale["total"], currency)],
         [paid_label, _money(content["paid"], currency)],
         ["Reste à payer", _money(content["balance"], currency)]],
        colWidths=[7 * cm, 4 * cm], hAlign="RIGHT",
    )
    totals.setStyle(TableStyle([
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("FONTNAME", (0, 2), (-1, 2), "Helvetica-Bold"),
        ("LINEABOVE", (0, 2), (-1, 2), 1, accent),
        ("TEXTCOLOR", (0, 2), (-1, 2), accent),
    ]))
    story.append(totals)
    if content["balance"] == 0:
        story += [Spacer(1, 0.2 * cm), Paragraph("Vente soldée.", right)]

    # --- Mentions
    if issuer.get("payment_terms"):
        story += [Spacer(1, 0.6 * cm), Paragraph("CONDITIONS DE PAIEMENT", label),
                  Paragraph(_text(issuer["payment_terms"]).replace("\n", "<br/>"), small)]
    if issuer.get("footer_text"):
        story += [Spacer(1, 0.6 * cm), Paragraph(_text(issuer["footer_text"]).replace("\n", "<br/>"), centered)]

    def decorate(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(GREY)
        canvas.drawCentredString(A4[0] / 2, 1.1 * cm, f"{document.number} — page {doc.page} — établi avec AVIKA")
        if cancelled:
            canvas.translate(A4[0] / 2, A4[1] / 2)
            canvas.rotate(35)
            canvas.setFont("Helvetica-Bold", 90)
            canvas.setFillColor(colors.Color(0.8, 0.1, 0.1, alpha=0.2))
            canvas.drawCentredString(0, 0, "ANNULÉE")
        canvas.restoreState()

    buffer = BytesIO()
    SimpleDocTemplate(
        buffer, pagesize=A4, title=f"{document.number}", author=_text(issuer.get("name")) or "AVIKA",
        leftMargin=2.1 * cm, rightMargin=2.1 * cm, topMargin=2 * cm, bottomMargin=2 * cm,
    ).build(story, onFirstPage=decorate, onLaterPages=decorate)
    return buffer.getvalue()
