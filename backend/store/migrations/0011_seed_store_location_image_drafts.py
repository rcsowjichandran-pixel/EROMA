from django.db import migrations


def add_location_image_drafts(apps, schema_editor):
    StoreLocation = apps.get_model("store", "StoreLocation")
    drafts = [
        ("Bengaluru", "Karnataka", "stores/bengaluru.jpg", "Mahadev Ittina", "https://unsplash.com/photos/a-view-of-a-city-with-tall-buildings-sEDewKyq6YM"),
        ("Delhi", "Delhi", "stores/delhi.jpg", "Martijn Vonk", "https://unsplash.com/photos/a-large-building-with-a-flag-on-top-of-it-NWhgsmKSjJ0"),
        ("Mumbai", "Maharashtra", "stores/mumbai.jpg", "Prado", "https://unsplash.com/photos/people-walking-on-arch-gate-during-daytime-5EI5JYMSvj8"),
        ("Alappuzha", "Kerala", "stores/kerala.jpg", "Abhishek Prasad", "https://unsplash.com/photos/brown-wooden-boat-on-water-during-daytime-N3VzleBhOvk"),
        ("Hyderabad", "Telangana", "stores/hyderabad.jpg", "Unsplash", "https://unsplash.com/s/photos/hyderabad"),
    ]
    for order, (city, state, image, credit, source_url) in enumerate(drafts):
        StoreLocation.objects.get_or_create(
            city=city,
            state=state,
            defaults={
                "image": image,
                "image_credit": credit,
                "image_source_url": source_url,
                "description": "Draft image. Add a verified EROMA showroom address before publishing.",
                "sort_order": order,
                "is_active": False,
            },
        )


class Migration(migrations.Migration):
    dependencies = [("store", "0010_storelocation_image_source_url")]
    operations = [migrations.RunPython(add_location_image_drafts, migrations.RunPython.noop)]
