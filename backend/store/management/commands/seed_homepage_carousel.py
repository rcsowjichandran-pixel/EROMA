from django.core.management.base import BaseCommand

from store.models import HomepageBanner


SLIDES = (
    {
        "title": "THE EROMA HOME EDIT",
        "subtitle": "A home edit for every moment.",
        "description": "Gather, unwind, and make a little more room for living.",
        "eyebrow": "DESIGNED FOR SLOW LIVING",
        "offer_text": "",
        "offer_code": "",
        "card_title": "The living room edit",
        "card_subtitle": "Made for the way you unwind",
        "cta_label": "Explore home decor",
        "category_name": "Home Decor & Lighting",
        "theme": "ruby",
        "image": "banners/defaults/festive-dining.jpg",
        "alt_text": "Warmly styled EROMA dining and living room furniture",
        "sort_order": 0,
    },
    {
        "title": "MAKE ROOM FOR COMFORT",
        "subtitle": "Make your home a softer place to land.",
        "description": "Explore comfortable sofas for slow mornings and long evenings.",
        "eyebrow": "COMFORT, EVERY DAY",
        "offer_text": "",
        "offer_code": "",
        "card_title": "The sofa collection",
        "card_subtitle": "Relax into considered design",
        "cta_label": "Shop sofas",
        "category_name": "Sofas",
        "theme": "midnight",
        "image": "banners/defaults/everyday-sofas.jpg",
        "alt_text": "Comfortable EROMA sofa for relaxed everyday living",
        "sort_order": 1,
    },
    {
        "title": "CRAFTED FOR LASTING LIVING",
        "subtitle": "A more restful space starts here.",
        "description": "Explore considered bedroom pieces and natural wood details.",
        "eyebrow": "A MORE RESTFUL SPACE",
        "offer_text": "",
        "offer_code": "",
        "card_title": "The bedroom edit",
        "card_subtitle": "Bring home a slower start",
        "cta_label": "Shop bedroom",
        "category_name": "Beds & Bedroom",
        "theme": "walnut",
        "image": "banners/defaults/solid-wood-bedroom.jpg",
        "alt_text": "A warm EROMA bedroom with considered wood furniture",
        "sort_order": 2,
    },
)


class Command(BaseCommand):
    help = "Create the editable three-slide EROMA homepage hero carousel."

    def handle(self, *args, **options):
        HomepageBanner.objects.filter(title="Homepage hero").update(is_active=False)
        created = 0
        for slide in SLIDES:
            _, was_created = HomepageBanner.objects.update_or_create(
                title=slide["title"],
                defaults={**slide, "is_active": True, "cta_label": slide["cta_label"]},
            )
            created += int(was_created)
        self.stdout.write(self.style.SUCCESS(f"Homepage carousel ready: {len(SLIDES)} slides ({created} created)."))
