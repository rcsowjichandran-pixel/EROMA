from django.db import migrations


COLLECTION_NOTES = {
    "Sofas": "Build the rest of the room around the sofa's shape and upholstery. A rug can define the seating area, while cushions in a contrasting texture can add depth without introducing another strong colour.",
    "Chairs & Armchairs": "If you are adding this chair to an existing room, repeat one finish or colour from the furniture nearby to tie the pieces together. A different shade or texture can still give the chair a distinct place in the arrangement.",
    "Loungers & Ottomans": "Let the piece pick up a colour or texture already used elsewhere in the room. A quieter rug or throw can help it sit comfortably alongside the main seating, especially if the upholstery already has a strong pattern.",
    "Dining Furniture": "For everyday dining, keep the centre of the table open and bring in colour through placemats or linen. A pendant or a nearby lamp can define the dining area and make it feel separate from the rest of an open room.",
    "Beds & Bedroom": "Keep the largest surfaces in a related palette, then bring contrast in through bedding, lamps, or a rug. Repeating one finish in the bedside furniture or accessories can tie the room together without making every piece match.",
    "Tables": "Choose what you want within easy reach and leave the rest of the surface free. A small tray can group everyday items, while one taller object, such as a lamp or vase, can give the arrangement a sense of height.",
    "Storage Furniture": "Plan the storage around the things you reach for most, with occasional items farther out of the way. A matching finish can help the piece sit quietly in the room, while contrast can make it a focal point.",
    "Office Furniture": "Keep the pieces you use throughout the day within easy reach and leave a clear working area. A task light and a small tray for essentials can make the workspace easier to use without crowding it.",
    "Home Decor & Lighting": "Use this piece to draw attention to a spot you want to highlight. Repeat a colour or finish from nearby furniture, or leave enough space around it for its shape to stand out on its own.",
}

PRODUCT_NOTES = {
    "Bookshelves": "Mix books with a few display pieces and leave some open space so each shelf is easy to read visually. Put the books you reach for most at a comfortable height and follow the shelf's load and anchoring instructions.",
    "Bedside Tables": "A lamp, a small dish, and a spot for a book can cover most bedside needs. Keeping the rest of the surface clear makes it easier to find what you need at night.",
    "Mirrors": "Consider what the mirror will reflect from the main entrance to the room. A window or a simple wall arrangement can help bring more light or visual depth into the space.",
    "TV Units": "Group remotes and other small accessories in one place and leave ventilation space around electronic equipment. A few low decorative pieces can soften the arrangement while keeping the screen clear.",
}


def add_styling_paragraph(apps, schema_editor):
    product_model = apps.get_model("store", "Product")
    products = product_model.objects.using(schema_editor.connection.alias).select_related("category__parent")
    updates = []
    for product in products.iterator(chunk_size=250):
        category = product.category
        collection = category.parent or category
        note = PRODUCT_NOTES.get(category.name) or COLLECTION_NOTES.get(collection.name)
        if note and note not in product.description:
            product.description = f"{product.description.rstrip()}\n\n{note}".lstrip()
            updates.append(product)
    products.bulk_update(updates, ["description"], batch_size=250)


class Migration(migrations.Migration):
    dependencies = [("store", "0031_expand_catalog_descriptions")]
    operations = [migrations.RunPython(add_styling_paragraph, migrations.RunPython.noop)]
