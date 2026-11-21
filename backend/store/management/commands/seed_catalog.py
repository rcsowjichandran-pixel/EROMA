from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.utils.text import slugify

from store.models import Category, Coupon, Offer, Product


CATEGORY_HIERARCHY = {
    "Sofas": (
        "2-Seater Sofas",
        "3-Seater Sofas",
        "L-Shaped Sofas",
        "Modular Sofas",
        "Sofa Beds",
    ),
    "Chairs & Armchairs": (
        "Accent Chairs",
        "Lounge Chairs",
        "Recliner Chairs",
        "Dining Chairs",
        "Rocking Chairs",
    ),
    "Loungers & Ottomans": (
        "Chaise Lounges",
        "Footstools",
        "Pouffes",
        "Storage Ottomans",
    ),
    "Dining Furniture": (
        "Dining Tables",
        "Dining Sets",
        "Bar Stools",
        "Console Tables",
    ),
    "Beds & Bedroom": (
        "King Beds",
        "Queen Beds",
        "Bedside Tables",
        "Bedroom Benches",
    ),
    "Tables": (
        "Coffee Tables",
        "Side Tables",
        "Nesting Tables",
        "Study Tables",
    ),
    "Storage Furniture": (
        "Sideboards",
        "Cabinets",
        "Bookshelves",
        "TV Units",
    ),
    "Office Furniture": (
        "Conference Tables",
        "Ergonomic Chairs",
        "Executive Chairs",
        "Office Desks",
    ),
    "Home Decor & Lighting": (
        "Table Lamps",
        "Floor Lamps",
        "Decorative Vases",
        "Mirrors",
        "Wall Decor",
    ),
}

# Individually selected Unsplash photographs for the starter products.
# Keeping this keyed by SKU prevents repeated category photos across product cards.
PRODUCT_IMAGES = {
    "SOF-LUN-001": "photo-1555041469-a586c61ea9bc",
    "SOF-AUR-002": "photo-1759735218086-67f9f853ab8b",
    "SOF-MIL-003": "photo-1776763255235-046cd40f3093",
    "CHA-VEL-004": "photo-1789799223024-777e6d9f3423",
    "CHA-ARI-005": "photo-1767946876712-c78a132cc317",
    "CHA-MON-006": "photo-1567538096630-e0c55bd6374c",
    "LOU-CLO-007": "photo-1774477178005-bff823e43be8",
    "DIN-NOV-008": "photo-1723641277401-225d0dffcb2a",
    "BED-EDN-009": "photo-1505693416388-ac5ce068fe85",
    "TAB-ZEN-010": "photo-1789799223021-e8fb04e10b0b",
    "STO-AUR-011": "photo-1767963758785-b9def36c13e3",
    "OFF-WSP-012": "photo-1782080163196-26ed8ea266d7",
    "DEC-LUM-013": "photo-1780898406363-a3858597ca6c",
    "DEC-TER-014": "photo-1607200711767-5f91ad860ae0",
    "OFF-OSL-015": "photo-1781106743595-1a2c6397e812",
}


def product_image_url(sku):
    photo_id = PRODUCT_IMAGES.get(sku)
    if not photo_id:
        return ""
    return f"https://images.unsplash.com/{photo_id}?auto=format&fit=crop&w=1200&q=85"


PRODUCTS = (
    {
        "name": "Luna Modular Sofa",
        "sku": "SOF-LUN-001",
        "category": "Modular Sofas",
        "price": "89999",
        "short_description": "Modern modular comfort",
        "description": "Premium modular sofa with soft upholstery and solid wood support.",
        "material": "Premium fabric, solid wood",
        "fabric_type": "Premium fabric",
        "frame_material": "Solid wood",
        "color_options": "Ivory",
        "dimensions": "220 × 95 × 85 cm",
        "weight_kg": "65",
        "warranty": "2 years",
        "seats": 3,
        "featured": True,
        "best_seller": True,
    },
    {
        "name": "Aura 3-Seater Sofa",
        "sku": "SOF-AUR-002",
        "category": "3-Seater Sofas",
        "price": "79999",
        "description": "A three-seat design for relaxed, contemporary living spaces.",
        "seats": 3,
    },
    {
        "name": "Milano L-Shape Sofa",
        "sku": "SOF-MIL-003",
        "category": "L-Shaped Sofas",
        "price": "119999",
        "description": "A generous L-shaped profile for relaxed living and social spaces.",
        "seats": 5,
    },
    {
        "name": "Velora Lounge Chair",
        "sku": "CHA-VEL-004",
        "category": "Lounge Chairs",
        "price": "24999",
        "description": "A sculptural lounge seat for quiet moments and relaxed reading.",
        "seats": 1,
    },
    {
        "name": "Aria Accent Chair",
        "sku": "CHA-ARI-005",
        "category": "Accent Chairs",
        "price": "19999",
        "description": "A statement accent seat for living rooms, bedrooms, and reading corners.",
        "seats": 1,
    },
    {
        "name": "Monarch Recliner",
        "sku": "CHA-MON-006",
        "category": "Recliner Chairs",
        "price": "44999",
        "description": "A recliner designed for relaxed, everyday comfort.",
        "seats": 1,
    },
    {
        "name": "Cloud Ottoman",
        "sku": "LOU-CLO-007",
        "category": "Loungers & Ottomans",
        "price": "8999",
        "description": "A versatile ottoman for living rooms and lounge spaces.",
    },
    {
        "name": "Nova Dining Table",
        "sku": "DIN-NOV-008",
        "category": "Dining Tables",
        "price": "49999",
        "description": "A dining table for everyday meals and shared moments.",
    },
    {
        "name": "Eden King Bed",
        "sku": "BED-EDN-009",
        "category": "King Beds",
        "price": "69999",
        "description": "A king bed with a clean, contemporary profile for restful bedrooms.",
    },
    {
        "name": "Zen Coffee Table",
        "sku": "TAB-ZEN-010",
        "category": "Coffee Tables",
        "price": "24999",
        "description": "A refined centerpiece for living rooms and everyday use.",
    },
    {
        "name": "Aura Sideboard",
        "sku": "STO-AUR-011",
        "category": "Sideboards",
        "price": "39999",
        "description": "A streamlined storage piece for dining and living spaces.",
    },
    {
        "name": "WorkSpace Executive Chair",
        "sku": "OFF-WSP-012",
        "category": "Executive Chairs",
        "price": "18999",
        "description": "An executive chair designed for focused work.",
        "seats": 1,
    },
    {
        "name": "Lumi Floor Lamp",
        "sku": "DEC-LUM-013",
        "category": "Floor Lamps",
        "price": "7999",
        "description": "A floor lamp for warm, layered ambient lighting.",
    },
    {
        "name": "Terra Ceramic Vase",
        "sku": "DEC-TER-014",
        "category": "Decorative Vases",
        "price": "2499",
        "description": "A ceramic vase for considered interior styling.",
    },
    {
        "name": "Oslo Study Desk",
        "sku": "OFF-OSL-015",
        "category": "Office Desks",
        "price": "16999",
        "description": "A study desk designed for focused work and study.",
    },
)


class Command(BaseCommand):
    help = "Create the SOFALUX category hierarchy and starter catalogue."

    def handle(self, *args, **options):
        if args:
            raise CommandError("seed_catalog does not accept positional arguments.")

        categories = self._ensure_categories()
        created_count = 0

        for item in PRODUCTS:
            sale_price = Decimal(item["price"])
            regular_price = (sale_price * Decimal("1.10")).quantize(
                Decimal("1"), rounding=ROUND_HALF_UP
            )
            defaults = {
                "name": item["name"],
                "slug": slugify(item["name"]),
                "category": categories[item["category"]],
                "image_url": product_image_url(item["sku"]),
                "short_description": item.get("short_description", ""),
                "description": item["description"],
                "price": sale_price,
                "regular_price": regular_price,
                "material": item.get("material", ""),
                "fabric_type": item.get("fabric_type", ""),
                "frame_material": item.get("frame_material", ""),
                "color_options": item.get("color_options", ""),
                "dimensions": item.get("dimensions", ""),
                "weight_kg": item.get("weight_kg"),
                "warranty": item.get("warranty", ""),
                "seats": item.get("seats"),
                "stock": 15,
                "featured": item.get("featured", False),
                "best_seller": item.get("best_seller", False),
                "new_arrival": False,
                "status": "active",
            }
            product, created = Product.objects.get_or_create(sku=item["sku"], defaults=defaults)
            if not created and product.regular_price != regular_price:
                product.regular_price = regular_price
                product.save(update_fields=("regular_price",))
            if not created and (
                not product.image_url or "images.unsplash.com/" in product.image_url
            ):
                product.image_url = defaults["image_url"]
                product.save(update_fields=("image_url",))
            created_count += int(created)

        today = timezone.localdate()
        next_new_year = (today.year, "01-01", today.year, "01-08") if today.month == 1 and today.day <= 8 else (today.year, "12-27", today.year + 1, "01-08")
        next_pongal_year = today.year if today.month == 1 and today.day <= 18 else today.year + 1
        next_christmas_year = today.year if today.month < 12 or today.day <= 26 else today.year + 1
        diwali_dates = {2026: "2026-11-08", 2027: "2027-10-29", 2028: "2028-10-17", 2029: "2029-11-05", 2030: "2030-10-26"}
        next_diwali = next((date for year, date in sorted((year, datetime.fromisoformat(day).date()) for year, day in diwali_dates.items()) if date >= today), None)
        if next_diwali is None:
            next_diwali = datetime(today.year + 1, 10, 25).date()
        campaigns = (
            ("SOFA1500", "Christmas Sale", "Sofas", "1500", "25000", f"{next_christmas_year}-12-01", f"{next_christmas_year}-12-26"),
            ("BEDROOM1200", "New Year Sale", "Beds & Bedroom", "1200", "25000", f"{next_new_year[0]}-{next_new_year[1]}", f"{next_new_year[2]}-{next_new_year[3]}"),
            ("DINING1000", "Diwali Sale", "Dining Furniture", "1000", "20000", (next_diwali - timedelta(days=7)).isoformat(), (next_diwali + timedelta(days=4)).isoformat()),
            ("STORAGE800", "Pongal Sale", "Storage Furniture", "800", "15000", f"{next_pongal_year}-01-10", f"{next_pongal_year}-01-18"),
            ("HOME600", "Year-End Sale", "Home Decor & Lighting", "600", "5000", f"{today.year}-11-15", f"{today.year}-12-31"),
        )
        Coupon.objects.filter(code__in=("SOFA500", "BEDROOM500", "DINING500", "STORAGE500", "HOME500")).update(is_active=False)
        Offer.objects.filter(name__in=("EROMA Sofa Refresh", "EROMA Bedroom Edit", "EROMA Dining Edit", "EROMA Storage Edit", "EROMA Home Edit")).update(is_active=False)
        for code, title, category_name, discount, minimum_order, starts_on, ends_on in campaigns:
            parent = categories[category_name]
            eligible_categories = [parent, *parent.subcategories.all()]
            description = f"Save INR {discount} on eligible {category_name.lower()} orders of INR {minimum_order} or more."
            coupon, _ = Coupon.objects.update_or_create(code=code, defaults={
                "description": description,
                "discount_type": "fixed",
                "discount_value": Decimal(discount),
                "minimum_order": Decimal(minimum_order),
                "usage_limit": 200,
                "is_active": True,
            })
            coupon.categories.set(eligible_categories)
            offer, _ = Offer.objects.update_or_create(name=title, defaults={
                "description": description,
                "discount_type": "fixed",
                "discount_value": Decimal(discount),
                "coupon": coupon,
                "is_active": True,
                "starts_at": timezone.make_aware(datetime.fromisoformat(f"{starts_on}T00:00:00")),
                "ends_at": timezone.make_aware(datetime.fromisoformat(f"{ends_on}T23:59:59")),
            })
            offer.categories.set([parent])

        if options.get("verbosity", 1):
            self.stdout.write(
                self.style.SUCCESS(
                    f"Category hierarchy ready: {len(CATEGORY_HIERARCHY)} parent categories; "
                    f"{created_count} starter products added; {len(campaigns)} category offer cards ready."
                )
            )

    def _ensure_categories(self):
        categories = {}

        legacy_sofa_bed = Category.objects.filter(name="Sofa Bed").first()
        if legacy_sofa_bed and not Category.objects.filter(name="Sofa Beds").exists():
            legacy_sofa_bed.name = "Sofa Beds"
            legacy_sofa_bed.slug = slugify("Sofa Beds")
            legacy_sofa_bed.save(update_fields=("name", "slug"))

        for parent_name, child_names in CATEGORY_HIERARCHY.items():
            if parent_name == "Dining Furniture":
                parent = Category.objects.filter(slug="dinning-furniture").first()
                if parent is None:
                    parent = Category.objects.filter(name="Dinning Furniture").first()
                if parent is not None and parent.name != parent_name:
                    parent.name = parent_name
                    parent.save(update_fields=("name",))
            else:
                parent = Category.objects.filter(name=parent_name, parent__isnull=True).first()

            if parent is None:
                parent, _ = Category.objects.get_or_create(
                    name=parent_name,
                    defaults={"slug": slugify(parent_name)},
                )
            if parent.parent_id is not None:
                parent.parent = None
                parent.save(update_fields=("parent",))
            categories[parent_name] = parent

            for child_name in child_names:
                child, _ = Category.objects.get_or_create(
                    name=child_name,
                    defaults={
                        "slug": slugify(child_name),
                        "parent": parent,
                    },
                )
                if child.parent_id != parent.pk:
                    child.parent = parent
                    child.save(update_fields=("parent",))
                categories[child_name] = child

        return categories
