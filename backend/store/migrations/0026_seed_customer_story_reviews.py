from django.db import migrations


REVIEWS = (
    (
        "king-bed-01",
        "Kavya Rao (Sample)",
        "A restful bedroom starts with a bed that feels like it belongs in the space. This design gives the room a calm, considered centrepiece.",
    ),
    (
        "coffee-table-01",
        "Saurabh Iyer (Sample)",
        "A coffee table brings the seating area together and keeps everyday essentials close at hand. A useful finishing touch for the room.",
    ),
    (
        "recliner-chair-01",
        "Meera Nair (Sample)",
        "A recliner gives a quiet corner a clear purpose: a comfortable place to put your feet up and unwind at the end of the day.",
    ),
    (
        "three-seat-sofa-01",
        "Aarav Mehta (Sample)",
        "A welcoming sofa can set the tone for the whole living room. This one feels like an easy place to slow down, gather, and settle in.",
    ),
)


def seed_customer_stories(apps, schema_editor):
    Product = apps.get_model("store", "Product")
    ProductReview = apps.get_model("store", "ProductReview")
    database = schema_editor.connection.alias

    for slug, customer_name, body in REVIEWS:
        product = Product.objects.using(database).filter(slug=slug).first()
        if product is None:
            continue

        review = ProductReview.objects.using(database).filter(
            product_id=product.pk,
            customer__isnull=True,
            customer_name=customer_name,
        ).first()
        values = {"rating": 5, "body": body, "is_approved": True}
        if review is None:
            ProductReview.objects.using(database).create(
                product_id=product.pk,
                customer_name=customer_name,
                **values,
            )
        else:
            for field, value in values.items():
                setattr(review, field, value)
            review.save(using=database, update_fields=list(values))


def remove_customer_stories(apps, schema_editor):
    Product = apps.get_model("store", "Product")
    ProductReview = apps.get_model("store", "ProductReview")
    database = schema_editor.connection.alias

    for slug, customer_name, _body in REVIEWS:
        product = Product.objects.using(database).filter(slug=slug).first()
        if product is not None:
            ProductReview.objects.using(database).filter(
                product_id=product.pk,
                customer__isnull=True,
                customer_name=customer_name,
            ).delete()


class Migration(migrations.Migration):
    dependencies = [("store", "0025_sitebranding")]

    operations = [
        migrations.RunPython(seed_customer_stories, remove_customer_stories),
    ]
