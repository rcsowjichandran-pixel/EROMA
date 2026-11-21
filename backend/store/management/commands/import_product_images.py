from pathlib import Path

from django.conf import settings
from django.core.files import File
from django.core.management.base import BaseCommand, CommandError
from django.utils.text import slugify

from store.models import Product, ProductImage


SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


class Command(BaseCommand):
    help = "Attach product photos from a directory by product slug, SKU, or name."

    def add_arguments(self, parser):
        parser.add_argument(
            "directory",
            nargs="?",
            default=str(settings.BASE_DIR.parent / "output" / "imagegen" / "catalog"),
            help="Directory containing images named after their product slug or SKU.",
        )

    def handle(self, *args, **options):
        directory = Path(options["directory"]).expanduser().resolve()
        if not directory.is_dir():
            raise CommandError(f"Image directory does not exist: {directory}")

        products = list(Product.objects.select_related("category").all())
        by_key = {}
        for product in products:
            for value in (product.slug, product.sku, product.name):
                if value:
                    by_key[slugify(value).casefold()] = product

        files = sorted(
            path for path in directory.iterdir()
            if path.is_file() and path.suffix.casefold() in SUPPORTED_EXTENSIONS
        )
        if not files:
            raise CommandError(f"No supported images found in {directory}")

        imported = 0
        skipped = []
        for path in files:
            product = by_key.get(slugify(path.stem).casefold())
            if product is None:
                skipped.append(path.name)
                continue

            primary = ProductImage.objects.filter(product=product, is_primary=True).first()
            with path.open("rb") as source:
                if primary:
                    primary.image.save(path.name, File(source), save=False)
                    primary.alt_text = product.name
                    primary.sort_order = 0
                    primary.save(update_fields=("image", "alt_text", "sort_order"))
                else:
                    primary = ProductImage.objects.create(
                        product=product,
                        image=File(source, name=path.name),
                        alt_text=product.name,
                        is_primary=True,
                        sort_order=0,
                    )

            ProductImage.objects.filter(product=product).exclude(pk=primary.pk).update(is_primary=False)
            imported += 1
            self.stdout.write(f"Imported {path.name} -> {product.name}")

        self.stdout.write(self.style.SUCCESS(f"Imported {imported} product image(s)."))
        if skipped:
            self.stdout.write(self.style.WARNING("Unmatched files: " + ", ".join(skipped)))
