import hashlib
import re
from pathlib import Path

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError

from store.models import Category, CategoryImage, ProductImage


GROUPS = (
    ("2 seater", "2-Seater Sofas"),
    ("3 seater", "3-Seater Sofas"),
    ("l shape", "L-Shaped Sofas"),
    ("modular", "Modular Sofas"),
    ("sofabed", "Sofa Beds"),
    ("convertible sleeper", "Sofa Beds"),
    ("accent", "Accent Chairs"),
    ("accent chair", "Accent Chairs"),
    ("lounge", "Lounge Chairs"),
    ("lounge chair", "Lounge Chairs"),
    ("lounges", "Chaise Lounges"),
    ("recliner", "Recliner Chairs"),
    ("bar stool", "Bar Stools"),
    ("bedroom bench", "Bedroom Benches"),
    ("bedside", "Bedside Tables"),
    ("bookshelf", "Bookshelves"),
    ("cabinets", "Cabinets"),
    ("coffee table", "Coffee Tables"),
    ("conference table", "Conference Tables"),
    ("console", "Console Tables"),
    ("decorative vase", "Decorative Vases"),
    ("dinning set", "Dining Sets"),
    ("dinning table", "Dining Tables"),
    ("ergonomic", "Ergonomic Chairs"),
    ("executive chair", "Executive Chairs"),
    ("floor lamp", "Floor Lamps"),
    ("footstool", "Footstools"),
    ("king size", "King Beds"),
    ("mirror", "Mirrors"),
    ("nesting table", "Nesting Tables"),
    ("office desk", "Office Desks"),
    ("ottomans", "Storage Ottomans"),
    ("ottoman", "Storage Ottomans"),
    ("pouffe", "Pouffes"),
    ("queen size", "Queen Beds"),
    ("side table", "Side Tables"),
    ("storage ottoman", "Storage Ottomans"),
    ("storage", "Storage Furniture"),
    ("study table", "Study Tables"),
    ("table lamp", "Table Lamps"),
    ("tv unit", "TV Units"),
    ("wall decor", "Wall Decor"),
    ("dinning", "Dining Chairs"),
    ("dining chair", "Dining Chairs"),
    ("rocking", "Rocking Chairs"),
    ("rocking chair", "Rocking Chairs"),
)


def category_group(filename):
    stem = Path(filename).stem.casefold().strip()
    for prefix, category_name in GROUPS:
        if stem == prefix or stem.startswith(f"{prefix} "):
            return category_name
    return None


def order_for(filename):
    stem = Path(filename).stem.casefold()
    if stem.startswith("convertible sleeper sofa bed"):
        return 4
    match = re.search(r"(\d+)$", stem)
    return int(match.group(1)) if match else 0


class Command(BaseCommand):
    help = "Import local Sofa and Chair subcategory photos into category galleries."

    def add_arguments(self, parser):
        parser.add_argument("directory", help="Folder containing the Sofa subcategory photos.")

    def handle(self, *args, **options):
        directory = Path(options["directory"]).expanduser().resolve()
        if not directory.is_dir():
            raise CommandError(f"Image directory does not exist: {directory}")

        categories = {
            category.name: category
            for category in Category.objects.filter(name__in=[name for _, name in GROUPS])
        }
        imported = skipped = 0
        unmatched = []
        linked_product_images = {
            Path(name).name
            for name in ProductImage.objects.exclude(image="").values_list("image", flat=True)
        }
        files = sorted(
            path for path in directory.iterdir()
            if path.is_file() and path.name not in linked_product_images
        )

        for path in files:
            category_name = category_group(path.name)
            if category_name is None:
                continue
            category = categories.get(category_name)
            if category is None:
                unmatched.append(f"{path.name} (category missing: {category_name})")
                continue

            image_bytes = path.read_bytes()
            digest = hashlib.sha256(image_bytes).digest()
            gallery_image = CategoryImage.objects.filter(
                category=category, source_name=path.name
            ).first()
            if gallery_image:
                try:
                    with gallery_image.image.open("rb") as current:
                        if hashlib.sha256(current.read()).digest() == digest:
                            alt_text = f"{category.name} — view {order_for(path.name) + 1}"
                            changed_fields = []
                            if gallery_image.alt_text != alt_text:
                                gallery_image.alt_text = alt_text
                                changed_fields.append("alt_text")
                            if gallery_image.sort_order != order_for(path.name):
                                gallery_image.sort_order = order_for(path.name)
                                changed_fields.append("sort_order")
                            if changed_fields:
                                gallery_image.save(update_fields=changed_fields)
                            skipped += 1
                            continue
                except FileNotFoundError:
                    pass
                gallery_image.image.delete(save=False)
            else:
                gallery_image = CategoryImage(category=category, source_name=path.name)

            gallery_image.alt_text = f"{category.name} — view {order_for(path.name) + 1}"
            gallery_image.sort_order = order_for(path.name)
            gallery_image.image.save(path.name, ContentFile(image_bytes), save=False)
            gallery_image.save()
            imported += 1
            self.stdout.write(f"Imported {path.name} -> {category.name}")

        self.stdout.write(
            self.style.SUCCESS(
                f"Imported {imported} category gallery image(s); skipped {skipped} unchanged."
            )
        )
        if unmatched:
            self.stdout.write(self.style.WARNING("Unmatched: " + ", ".join(unmatched)))

        for parent in Category.objects.filter(parent__isnull=True).prefetch_related("gallery_images"):
            first_image = parent.gallery_images.first()
            if first_image and parent.image.name != first_image.image.name:
                parent.image.name = first_image.image.name
                parent.save(update_fields=("image",))
