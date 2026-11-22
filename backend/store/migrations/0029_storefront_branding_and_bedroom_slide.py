from django.db import migrations, models


def update_storefront(apps, schema_editor):
    alias = schema_editor.connection.alias
    branding = apps.get_model("store", "SiteBranding").objects.using(alias)
    branding.filter(logo_alt_text="EROMA Furniture — Elegence in Every Corner").update(
        logo_alt_text="EROMA Furniture — Elegance in Every Corner"
    )

    banners = apps.get_model("store", "HomepageBanner").objects.using(alias)
    bedroom = banners.filter(title="CRAFTED FOR LASTING LIVING", category_name="Beds & Bedroom", sort_order=2)
    sofa = banners.filter(title="MAKE ROOM FOR COMFORT", category_name="Sofas", sort_order=1)
    if bedroom.exists() and sofa.exists():
        sofa.update(sort_order=3)
        bedroom.update(cta_label="Shop bedroom")


class Migration(migrations.Migration):
    dependencies = [("store", "0028_contactmessage")]

    operations = [
        migrations.AlterField(
            model_name="sitebranding",
            name="logo_alt_text",
            field=models.CharField(default="EROMA Furniture — Elegance in Every Corner", max_length=180),
        ),
        migrations.RunPython(update_storefront, migrations.RunPython.noop),
    ]
