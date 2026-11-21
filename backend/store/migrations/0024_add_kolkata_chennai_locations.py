from django.db import migrations


def add_city_cards(apps, schema_editor):
    StoreLocation = apps.get_model("store", "StoreLocation")
    entries = [
        {
            "city": "Kolkata",
            "state": "West Bengal",
            "image": "stores/kolkata.jpg",
            "image_credit": "Rama Warrier",
            "image_source_url": "https://commons.wikimedia.org/wiki/File:Victoria_memorial_Kolkata.jpg",
            "map_url": "https://www.google.com/maps/search/?api=1&query=EROMA+furniture+showroom+Kolkata+West+Bengal",
            "description": "EROMA showroom search for Kolkata.",
            "sort_order": 5,
        },
        {
            "city": "Chennai",
            "state": "Tamil Nadu",
            "image": "stores/chennai.jpg",
            "image_credit": "Amos777eligius",
            "image_source_url": "https://commons.wikimedia.org/wiki/File:Chennai_Lighthouse,_Marina_Beach.jpg",
            "map_url": "https://www.google.com/maps/search/?api=1&query=EROMA+furniture+showroom+Chennai+Tamil+Nadu",
            "description": "EROMA showroom search for Chennai.",
            "sort_order": 6,
        },
    ]
    for entry in entries:
        StoreLocation.objects.get_or_create(
            city=entry["city"], state=entry["state"], defaults=entry
        )


class Migration(migrations.Migration):
    dependencies = [("store", "0023_order_shipping_tax")]

    operations = [migrations.RunPython(add_city_cards, migrations.RunPython.noop)]
