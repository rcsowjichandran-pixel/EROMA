from decimal import Decimal

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.utils.text import slugify

from store.models import Category, CategoryImage, Product, ProductImage


def catalog_item(sku, item, description, base_price, increment, material, seats=None):
    return {
        "sku": sku,
        "item": item,
        "description": description,
        "seats": seats,
        "material": material,
        "prices": tuple(base_price + increment * index for index in range(10)),
    }


CATALOG = {
    "2-Seater Sofas": {
        "sku": "SOF-2S",
        "item": "Two-seat sofa",
        "description": (
            "A space-conscious two-seat sofa with a comfortable upholstered finish and "
            "supportive cushions, suited to everyday living rooms and smaller spaces."
        ),
        "seats": 2,
        "prices": (49999, 54999, 59999, 64999, 69999),
    },
    "3-Seater Sofas": {
        "sku": "SOF-3S",
        "item": "Three-seat sofa",
        "description": (
            "A three-seat sofa with a generous cushioned profile and an upholstered finish, "
            "designed as a comfortable centrepiece for the living room."
        ),
        "seats": 3,
        "prices": (69999, 74999, 79999, 84999, 89999),
    },
    "L-Shaped Sofas": {
        "sku": "SOF-LS",
        "item": "L-shaped sofa",
        "description": (
            "An L-shaped sectional with a generous corner layout and comfortable upholstery, "
            "made to bring relaxed seating to a shared living space."
        ),
        "seats": 5,
        "prices": (99999, 109999, 119999, 129999, 139999),
    },
    "Modular Sofas": {
        "sku": "SOF-MD",
        "item": "Modular sofa",
        "description": (
            "A modular sofa with a relaxed, cushioned profile that suits flexible living-room "
            "layouts and everyday lounging."
        ),
        "seats": 3,
        "prices": (89999, 99999, 109999),
    },
    "Sofa Beds": {
        "sku": "SOF-SB",
        "item": "Sofa bed",
        "description": (
            "A convertible sofa bed designed for comfortable daytime seating and a practical "
            "sleeping option when guests stay over."
        ),
        "seats": 2,
        "prices": (55999, 62999, 69999, 76999, 82999),
    },
    "Accent Chairs": {
        "sku": "CHA-AC",
        "item": "Accent chair",
        "description": (
            "A sculptural accent chair with a comfortable upholstered seat, designed to add "
            "a relaxed statement to a living room or reading corner."
        ),
        "seats": 1,
        "prices": (19999, 24999, 29999, 34999, 39999),
    },
    "Lounge Chairs": {
        "sku": "CHA-LG",
        "item": "Lounge chair",
        "description": (
            "A comfortable lounge chair with a generous seat and upholstered finish, made for "
            "reading, relaxing, and everyday living."
        ),
        "seats": 1,
        "prices": (24999, 29999, 34999, 39999, 44999),
    },
    "Recliner Chairs": {
        "sku": "CHA-RC",
        "item": "Recliner chair",
        "description": (
            "A cushioned recliner designed for relaxed sitting and supportive everyday comfort."
        ),
        "seats": 1,
        "prices": (44999, 49999, 54999, 59999, 64999),
    },
    "Dining Chairs": {
        "sku": "CHA-DC",
        "item": "Dining chair",
        "description": (
            "An upholstered dining chair with a supportive seat, designed to pair with a dining "
            "table for everyday meals and gatherings."
        ),
        "seats": 1,
        "prices": (7999, 9999, 12999, 14999, 17999),
    },
    "Rocking Chairs": {
        "sku": "CHA-RK",
        "item": "Rocking chair",
        "description": (
            "A comfortable rocking chair with a cushioned seat and an easy, relaxed motion for "
            "quiet moments at home."
        ),
        "seats": 1,
        "prices": (17999, 21999, 24999, 27999, 31999),
    },
}

CATALOG.update({
    "Bar Stools": catalog_item("DIN-BS", "Bar stool", "A supportive bar stool for kitchen islands and counter seating, with a compact profile for everyday use.", 14999, 2500, "Furniture", 1),
    "Bedroom Benches": catalog_item("BED-BB", "Bedroom bench", "A versatile bedroom bench for extra seating at the foot of a bed or in a dressing area.", 19999, 3500, "Upholstery", 1),
    "Bedside Tables": catalog_item("BED-BT", "Bedside table", "A practical bedside table with a balanced footprint for keeping daily essentials close at hand.", 11999, 2000, "Furniture"),
    "Bookshelves": catalog_item("STO-BS", "Bookshelf", "A bookshelf with open display space for books, plants, and collected objects.", 24999, 4000, "Furniture"),
    "Cabinets": catalog_item("STO-CB", "Storage cabinet", "A versatile cabinet that brings concealed storage and a clean furniture profile to the home.", 29999, 5000, "Furniture"),
    "Coffee Tables": catalog_item("TAB-CT", "Coffee table", "A living-room coffee table designed to anchor the seating area and keep everyday essentials within reach.", 19999, 4000, "Furniture"),
    "Conference Tables": catalog_item("OFF-CT", "Conference table", "A spacious conference table designed for collaborative meetings and shared work.", 74999, 15000, "Furniture"),
    "Console Tables": catalog_item("DIN-CN", "Console table", "A slim console table for entryways and living areas, with a useful surface for lighting and decor.", 24999, 5000, "Furniture"),
    "Decorative Vases": catalog_item("DEC-VS", "Decorative vase", "A decorative vase that adds a considered accent to shelves, consoles, and tabletop arrangements.", 2499, 1000, "Decor"),
    "Dining Sets": catalog_item("DIN-DS", "Dining set", "A coordinated dining set for shared meals and everyday gatherings.", 74999, 15000, "Furniture", 4),
    "Dining Tables": catalog_item("DIN-DT", "Dining table", "A dining table designed to bring people together for everyday meals and special occasions.", 44999, 8000, "Furniture", 6),
    "Ergonomic Chairs": catalog_item("OFF-EC", "Ergonomic chair", "An ergonomic work chair with supportive seating for focused hours at a desk.", 21999, 5000, "Upholstery", 1),
    "Executive Chairs": catalog_item("OFF-EX", "Executive chair", "An executive chair with a considered profile for a comfortable and polished workspace.", 34999, 8000, "Upholstery", 1),
    "Floor Lamps": catalog_item("DEC-FL", "Floor lamp", "A floor lamp that adds warm, practical lighting beside a sofa or reading chair.", 11999, 2500, "Lighting"),
    "Footstools": catalog_item("LOU-FS", "Footstool", "A compact footstool for putting your feet up or adding a flexible extra seat.", 7999, 1200, "Upholstery", 1),
    "King Beds": catalog_item("BED-KB", "King bed", "A king-size bed with a generous sleeping area and a calm, timeless profile.", 74999, 15000, "Furniture", 2),
    "Chaise Lounges": catalog_item("LOU-CH", "Chaise lounge", "A chaise lounge with an extended seat for stretching out and relaxing.", 34999, 6000, "Upholstery", 1),
    "Mirrors": catalog_item("DEC-MR", "Decorative mirror", "A decorative mirror that reflects light and adds depth to an interior.", 11999, 2500, "Decor"),
    "Nesting Tables": catalog_item("TAB-NT", "Nesting table set", "A set of nesting tables that can be arranged together or used separately when extra surface space is needed.", 21999, 4000, "Furniture"),
    "Office Desks": catalog_item("OFF-OD", "Office desk", "A practical office desk with a generous work surface for daily tasks.", 29999, 5000, "Furniture"),
    "Storage Ottomans": catalog_item("LOU-SO", "Storage ottoman", "A cushioned storage ottoman that pairs flexible seating with a place to tuck away everyday items.", 17999, 3500, "Upholstery", 1),
    "Pouffes": catalog_item("LOU-PF", "Pouffe", "A versatile pouffe for relaxed seating or an occasional footrest.", 8999, 1500, "Upholstery", 1),
    "Queen Beds": catalog_item("BED-QB", "Queen bed", "A queen-size bed with a comfortable sleeping area and a clean, composed design.", 54999, 12000, "Furniture", 2),
    "Side Tables": catalog_item("TAB-ST", "Side table", "A compact side table for keeping a book, drink, or lamp beside your seat.", 11999, 2500, "Furniture"),
    "Storage Furniture": catalog_item("STO-SF", "Storage furniture piece", "A versatile storage piece designed to help keep the living space organized.", 19999, 4000, "Furniture"),
    "Study Tables": catalog_item("TAB-SD", "Study table", "A study table with a practical work surface for reading, learning, and everyday tasks.", 17999, 3500, "Furniture"),
    "Table Lamps": catalog_item("DEC-TL", "Table lamp", "A table lamp that brings a warm pool of light to a bedside table, desk, or console.", 7999, 2000, "Lighting"),
    "TV Units": catalog_item("STO-TV", "TV unit", "A media unit with a considered profile for organizing and displaying living-room essentials.", 24999, 5000, "Furniture"),
    "Wall Decor": catalog_item("DEC-WD", "Wall decor", "A decorative wall piece that adds a focal accent to a considered interior.", 4999, 1000, "Decor"),
})

OLD_STARTER_PRODUCTS = {
    "2-Seater Sofas": (),
    "3-Seater Sofas": ("Aura 3-Seater Sofa",),
    "L-Shaped Sofas": ("Milano L-Shape Sofa",),
    "Modular Sofas": ("Luna Modular Sofa",),
    "Sofa Beds": (),
    "Accent Chairs": ("Aria Accent Chair",),
    "Lounge Chairs": ("Velora Lounge Chair",),
    "Recliner Chairs": ("Monarch Recliner",),
    "Dining Chairs": (),
    "Rocking Chairs": (),
    "Bar Stools": (),
    "Bedroom Benches": (),
    "Bedside Tables": (),
    "Bookshelves": (),
    "Cabinets": (),
    "Coffee Tables": ("Zen Coffee Table",),
    "Conference Tables": (),
    "Console Tables": (),
    "Decorative Vases": ("Terra Ceramic Vase",),
    "Dining Sets": (),
    "Dining Tables": ("Nova Dining Table",),
    "Ergonomic Chairs": (),
    "Executive Chairs": ("WorkSpace Executive Chair",),
    "Floor Lamps": ("Lumi Floor Lamp",),
    "Footstools": (),
    "King Beds": ("Eden King Bed",),
    "Chaise Lounges": (),
    "Mirrors": (),
    "Nesting Tables": (),
    "Office Desks": ("Oslo Study Desk",),
    "Storage Ottomans": (),
    "Pouffes": (),
    "Queen Beds": (),
    "Side Tables": (),
    "Storage Furniture": (),
    "Study Tables": (),
    "Table Lamps": (),
    "TV Units": (),
    "Wall Decor": (),
    "Loungers & Ottomans": ("Cloud Ottoman",),
}


class Command(BaseCommand):
    help = "Publish supplied Sofa and Chair subcategory photos as catalog products."

    def handle(self, *args, **options):
        starters_to_archive = []
        for category_name, names in OLD_STARTER_PRODUCTS.items():
            category_has_gallery = Category.objects.filter(
                name=category_name, gallery_images__isnull=False
            ).exists()
            subcategory_has_gallery = Category.objects.filter(
                parent__name=category_name,
                gallery_images__isnull=False,
            ).exists()
            if category_has_gallery or subcategory_has_gallery:
                starters_to_archive.extend(names)
        archived = (
            Product.objects.filter(name__in=starters_to_archive)
            .exclude(status="archived")
            .update(status="archived")
        )
        created = updated = 0

        for category_name, settings in CATALOG.items():
            category = Category.objects.get(name=category_name)
            photos = list(
                CategoryImage.objects.filter(category=category).order_by("sort_order", "id")
            )
            if len(photos) > len(settings["prices"]):
                self.stderr.write(
                    self.style.WARNING(
                        f"{category_name}: {len(photos)} photos but only "
                        f"{len(settings['prices'])} sample prices configured; extra photos skipped."
                    )
                )

            for index, photo in enumerate(photos[: len(settings["prices"])]):
                number = index + 1
                name = f"{settings['item']} {number:02d}"
                sku = f"{settings['sku']}-{number:03d}"
                summary = settings["description"]
                product, was_created = Product.objects.update_or_create(
                    sku=sku,
                    defaults={
                        "name": name,
                        "slug": slugify(name),
                        "category": category,
                        "short_description": summary,
                        "description": summary,
                        "price": Decimal(settings["prices"][index]),
                        "regular_price": None,
                        "image_url": "",
                        "material": settings.get("material", "Upholstered fabric"),
                        "seats": settings["seats"],
                        "stock": 10,
                        "status": "active",
                        "featured": False,
                    },
                )
                created += int(was_created)
                updated += int(not was_created)

                product_images = list(product.images.all())
                matching_image = next(
                    (item for item in product_images if item.alt_text == photo.source_name),
                    None,
                )
                for stale_image in product_images:
                    if stale_image is matching_image:
                        continue
                    stale_image.image.delete(save=False)
                    stale_image.delete()

                if matching_image:
                    if not matching_image.is_primary or matching_image.sort_order != 0:
                        matching_image.is_primary = True
                        matching_image.sort_order = 0
                        matching_image.save(update_fields=("is_primary", "sort_order"))
                else:
                    with photo.image.open("rb") as image_file:
                        image_bytes = image_file.read()
                    product_image = ProductImage(
                        product=product,
                        alt_text=photo.source_name,
                        is_primary=True,
                        sort_order=0,
                    )
                    product_image.image.save(
                        photo.source_name, ContentFile(image_bytes), save=False
                    )
                    product_image.save()

        self.stdout.write(
            self.style.SUCCESS(
                f"Archived {archived} old starter catalog item(s); "
                f"created {created} and refreshed {updated} gallery products."
            )
        )
