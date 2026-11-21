from django.db import migrations


def set_seeded_offer_terms(apps, schema_editor):
    Offer = apps.get_model("store", "Offer")
    terms = {
        "EROMA Sofa Refresh": "Save INR 500 on eligible sofa orders of INR 10,000 or more.",
        "EROMA Bedroom Edit": "Save INR 500 on eligible bedroom orders of INR 10,000 or more.",
        "EROMA Dining Edit": "Save INR 500 on eligible dining orders of INR 10,000 or more.",
        "EROMA Storage Edit": "Save INR 500 on eligible storage orders of INR 10,000 or more.",
        "EROMA Home Edit": "Save INR 500 on eligible decor orders of INR 10,000 or more.",
    }
    for name, description in terms.items():
        Offer.objects.filter(name=name).update(description=description)


class Migration(migrations.Migration):
    dependencies = [("store", "0013_coupon_categories_offer_coupon")]
    operations = [migrations.RunPython(set_seeded_offer_terms, migrations.RunPython.noop)]
