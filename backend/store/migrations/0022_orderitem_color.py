from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("store", "0021_order_emi_payment_instrument"),
    ]

    operations = [
        migrations.AddField(
            model_name="orderitem",
            name="color",
            field=models.CharField(blank=True, max_length=50),
        ),
    ]
