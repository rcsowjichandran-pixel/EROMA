from decimal import Decimal

from django.conf import settings
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework.test import APIRequestFactory

from .models import Category, Product, ProductImage
from .serializers import ProductSerializer


@override_settings(SECURE_SSL_REDIRECT=False)
class ProductModelTests(TestCase):
    def test_product_creation(self):
        c = Category.objects.create(name="Sofas", slug="sofas")
        p = Product.objects.create(name="Cloud Sofa", slug="cloud-sofa", category=c, description="Soft sofa", price="25000", stock=2)
        self.assertEqual(str(p), "Cloud Sofa")


@override_settings(SECURE_SSL_REDIRECT=False)
class StarterCatalogTests(TestCase):
    def test_seed_catalog_creates_nine_parents_and_fifteen_products_idempotently(self):
        call_command("seed_catalog", verbosity=0)

        self.assertEqual(Category.objects.filter(parent__isnull=True).count(), 9)
        self.assertEqual(Product.objects.count(), 15)

        luna = Product.objects.get(sku="SOF-LUN-001")
        self.assertEqual(luna.price, Decimal("89999"))
        self.assertEqual(luna.regular_price, Decimal("98999"))
        self.assertEqual(luna.category.parent.name, "Sofas")
        self.assertTrue(luna.featured)
        self.assertTrue(luna.best_seller)

        call_command("seed_catalog", verbosity=0)
        self.assertEqual(Category.objects.filter(parent__isnull=True).count(), 9)
        self.assertEqual(Product.objects.count(), 15)

    def test_custom_admin_dashboard_renders_live_metrics(self):
        call_command("seed_catalog", verbosity=0)
        user = User.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="test-password",
        )
        self.client.force_login(user)

        response = self.client.get("/admin/")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "EROMA")
        self.assertContains(response, "15")

    def test_category_admin_lists_parents_and_shows_children_inline(self):
        call_command("seed_catalog", verbosity=0)
        user = User.objects.create_superuser(
            username="category-admin",
            email="category-admin@example.com",
            password="test-password",
        )
        self.client.force_login(user)

        list_response = self.client.get(reverse("admin:store_category_changelist"))
        self.assertEqual(list_response.status_code, 200)
        self.assertContains(list_response, "Sofas")
        self.assertNotContains(list_response, "Modular Sofas")

        sofas = Category.objects.get(name="Sofas")
        change_response = self.client.get(
            reverse("admin:store_category_change", args=(sofas.pk,))
        )
        self.assertEqual(change_response.status_code, 200)
        self.assertContains(change_response, "Modular Sofas")


@override_settings(SECURE_SSL_REDIRECT=False)
class ProductImageTests(TestCase):
    def test_primary_uploaded_image_is_exposed_as_product_image_url(self):
        category = Category.objects.create(name="Sofas", slug="sofas")
        product = Product.objects.create(
            name="Cloud Sofa",
            slug="cloud-sofa",
            category=category,
            description="Soft sofa",
            price="25000",
        )
        ProductImage.objects.create(
            product=product,
            image="products/cloud-sofa.png",
            is_primary=True,
        )
        request = APIRequestFactory().get("/")
        data = ProductSerializer(product, context={"request": request}).data

        self.assertEqual(
            data["image_url"],
            f"http://testserver{settings.MEDIA_URL}products/cloud-sofa.png",
        )
