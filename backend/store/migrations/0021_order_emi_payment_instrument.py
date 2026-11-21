from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("store", "0020_homepagebanner_description"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="emi_requested",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="order",
            name="payment_instrument",
            field=models.CharField(blank=True, max_length=20),
        ),
    ]
