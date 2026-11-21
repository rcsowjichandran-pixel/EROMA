import hashlib
from pathlib import Path

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand, CommandError
from django.utils.text import slugify

from store.models import Category


SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


class Command(BaseCommand):
    help = "Attach category photos from files named after category slugs."

    def add_arguments(self, parser):
        parser.add_argument("directory", help="Folder containing category image files.")

    def handle(self, *args, **options):
        directory = Path(options["directory"]).expanduser().resolve()
        if not directory.is_dir():
            raise CommandError(f"Image directory does not exist: {directory}")

        categories = {}
        for item in Category.objects.all():
            categories[slugify(item.slug).casefold()] = item
            # Also accept the visible category name so legacy slugs do not block imports.
            categories[slugify(item.name).casefold()] = item
        files = sorted(
            path for path in directory.iterdir()
            if path.is_file() and path.suffix.casefold() in SUPPORTED_EXTENSIONS
        )
        if not files:
            raise CommandError(f"No supported images found in {directory}")

        imported = 0
        skipped = 0
        unmatched = []
        for path in files:
            category = categories.get(slugify(path.stem).casefold())
            if category is None:
                unmatched.append(path.name)
                continue

            image_bytes = path.read_bytes()
            source_digest = hashlib.sha256(image_bytes).digest()
            if category.image:
                try:
                    with category.image.open("rb") as current_image:
                        if hashlib.sha256(current_image.read()).digest() == source_digest:
                            skipped += 1
                            continue
                except FileNotFoundError:
                    pass
                category.image.delete(save=False)

            category.image.save(path.name, ContentFile(image_bytes), save=False)
            category.save(update_fields=("image",))
            imported += 1
            self.stdout.write(f"Imported {path.name} -> {category.name}")

        self.stdout.write(
            self.style.SUCCESS(f"Imported {imported} category image(s); skipped {skipped} unchanged.")
        )
        if unmatched:
            self.stdout.write(self.style.WARNING("Unmatched files: " + ", ".join(unmatched)))
