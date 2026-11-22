from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape

from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def render_order_bill(order):
    output = BytesIO()
    document = SimpleDocTemplate(output, title=f"EROMA Bill {order.pk}")
    styles = getSampleStyleSheet()

    def paragraph(value):
        return Paragraph(escape(str(value)).replace("\n", "<br/>"), styles["BodyText"])

    payment_method = order.get_payment_method_display()
    if order.payment_method == "razorpay" and order.payment_instrument:
        instrument = {"emi": "Card EMI", "upi": "UPI"}.get(
            order.payment_instrument, order.payment_instrument.replace("_", " ").title()
        )
        payment_method = f"{payment_method} ({instrument})"
    payment_status = order.get_payment_status_display()
    if order.payment_method == "cod" and order.payment_status == "pending":
        payment_status = "Payable on delivery"

    items = list(order.items.all())
    rows = [["Product", "Qty", "Unit price (INR)", "Amount (INR)"]]
    subtotal = sum(item.quantity * item.unit_price for item in items)
    for item in items:
        name = f"{item.product_name} ({item.color})" if item.color else item.product_name
        rows.append([
            paragraph(name), item.quantity, f"{item.unit_price:,.2f}",
            f"{item.quantity * item.unit_price:,.2f}",
        ])
    table = Table(rows, colWidths=[213, 30, 96, 96], repeatRows=1, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e9eee9")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("LINEBELOW", (0, 0), (-1, -1), 0.35, colors.lightgrey),
    ]))
    logo = Image(str(Path(__file__).with_name("eroma-bill-logo.png")), width=150, height=80, kind="proportional")
    logo.hAlign = "LEFT"
    document.build([
        logo,
        Paragraph(f"Order bill #{order.pk}", styles["Heading2"]),
        paragraph(f"Order date: {timezone.localtime(order.created_at):%d %b %Y}"),
        Paragraph("Customer and delivery address", styles["Heading3"]),
        paragraph(order.full_name),
        paragraph(order.address),
        paragraph(f"{order.city} {order.postal_code}"),
        Spacer(1, 10),
        paragraph(f"Payment method: {payment_method}"),
        paragraph(f"Payment status: {payment_status}"),
        Spacer(1, 12),
        table,
        Spacer(1, 12),
        paragraph(f"Items subtotal: INR {subtotal:,.2f}"),
        paragraph(f"Discount: INR {order.discount_amount:,.2f}"),
        paragraph(f"Delivery: INR {order.shipping_amount:,.2f}"),
        paragraph(f"GST included: INR {order.tax_amount:,.2f}"),
        Paragraph(f"Total: INR {order.total:,.2f}", styles["Heading3"]),
    ])
    output.seek(0)
    return output
