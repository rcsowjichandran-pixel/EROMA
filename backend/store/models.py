from decimal import Decimal, ROUND_HALF_UP

from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MaxValueValidator, MinValueValidator
from django.core.exceptions import ValidationError

from .contact_fields import validate_phone, validate_pin

class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True)
    image = models.ImageField(upload_to="categories/%Y/%m/", blank=True)

    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='subcategories'
    )

    def __str__(self):
        if self.parent:
            return f"{self.parent.name} → {self.name}"
        return self.name

class CategoryImage(models.Model):
    category = models.ForeignKey(
        Category, on_delete=models.CASCADE, related_name="gallery_images"
    )
    image = models.ImageField(upload_to="categories/gallery/%Y/%m/")
    alt_text = models.CharField(max_length=180, blank=True)
    source_name = models.CharField(max_length=255)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ("sort_order", "id")
        constraints = [
            models.UniqueConstraint(
                fields=("category", "source_name"), name="unique_category_gallery_source"
            )
        ]

    def __str__(self):
        return f"{self.category.name}: {self.alt_text or self.source_name}"


class Product(models.Model):
    STATUS_CHOICES = [
        ("active", "Active"),
        ("draft", "Draft"),
        ("archived", "Archived"),
    ]

    name = models.CharField(max_length=180)
    slug = models.SlugField(unique=True)
    sku = models.CharField(max_length=50, unique=True, null=True, blank=True)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="products")
    short_description = models.CharField(max_length=240, blank=True)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Sale price")
    regular_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    image_url = models.URLField(blank=True)
    material = models.CharField(max_length=100, blank=True)
    fabric_type = models.CharField(max_length=100, blank=True)
    frame_material = models.CharField(max_length=100, blank=True)
    cushion_filling = models.CharField(max_length=100, blank=True)
    color_options = models.CharField(max_length=255, blank=True, help_text="Comma-separated colour choices.")
    dimensions = models.CharField(max_length=100, blank=True)
    weight_kg = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    warranty = models.CharField(max_length=100, blank=True)
    seats = models.PositiveSmallIntegerField(null=True, blank=True)
    stock = models.PositiveIntegerField(default=0)
    featured = models.BooleanField(default=False)
    best_seller = models.BooleanField(default=False)
    new_arrival = models.BooleanField(default=False)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="active")
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if self.price not in (None, ""):
            self.price = Decimal(str(self.price))
        if self.regular_price not in (None, ""):
            self.regular_price = Decimal(str(self.regular_price))
        if self.price and not self.regular_price:
            self.regular_price = (self.price * Decimal("1.10")).quantize(
                Decimal("1"), rounding=ROUND_HALF_UP
            )
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(
        upload_to="products/%Y/%m/",
        help_text="Upload an original or properly licensed photo, ideally at least 1600 px on the longest side.",
    )
    alt_text = models.CharField(max_length=180, blank=True)
    is_primary = models.BooleanField(default=False)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ("sort_order", "id")

    def __str__(self):
        return f"{self.product.name} image"


class Offer(models.Model):
    DISCOUNT_TYPES = [
        ("percent", "Percentage"),
        ("fixed", "Fixed amount"),
    ]

    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    banner_image = models.ImageField(upload_to="offers/%Y/%m/", blank=True)
    banner_alt_text = models.CharField(max_length=180, blank=True)
    coupon = models.ForeignKey("Coupon", on_delete=models.SET_NULL, null=True, blank=True, related_name="offer_cards")
    discount_type = models.CharField(max_length=10, choices=DISCOUNT_TYPES, default="percent")
    discount_value = models.DecimalField(max_digits=8, decimal_places=2)
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    products = models.ManyToManyField(Product, blank=True, related_name="offers")
    categories = models.ManyToManyField(Category, blank=True, related_name="offers")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class FooterPageContent(models.Model):
    key = models.SlugField(max_length=80, unique=True)
    title = models.CharField(max_length=140)
    eyebrow = models.CharField(max_length=120, blank=True)
    summary = models.CharField(max_length=300, blank=True)
    body = models.TextField(blank=True)
    image = models.ImageField(upload_to="footer_pages/%Y/%m/", blank=True)
    image_alt_text = models.CharField(max_length=180, blank=True)
    action_label = models.CharField(max_length=80, blank=True)
    action_url = models.CharField(max_length=240, blank=True)
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("title",)
        verbose_name = "Footer page content"
        verbose_name_plural = "Footer page content"

    def __str__(self):
        return self.title


class SiteBranding(models.Model):
    logo = models.ImageField(upload_to="branding/", blank=True)
    logo_alt_text = models.CharField(max_length=180, default="EROMA Furniture — Elegance in Every Corner")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Site branding"
        verbose_name_plural = "Site branding"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def __str__(self):
        return "EROMA site logo"


class Coupon(models.Model):
    DISCOUNT_TYPES = [
        ("percent", "Percentage"),
        ("fixed", "Fixed amount"),
    ]

    code = models.CharField(max_length=40, unique=True)
    description = models.CharField(max_length=240, blank=True)
    categories = models.ManyToManyField(Category, blank=True, related_name="coupons", help_text="Leave empty for a store-wide coupon.")
    discount_type = models.CharField(max_length=10, choices=DISCOUNT_TYPES, default="percent")
    discount_value = models.DecimalField(max_digits=8, decimal_places=2)
    minimum_order = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    usage_limit = models.PositiveIntegerField(null=True, blank=True)
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        self.code = self.code.strip().upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.code


class ProductReview(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="reviews")
    customer = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="product_reviews",
    )
    customer_name = models.CharField(max_length=150, blank=True)
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    body = models.TextField(blank=True)
    is_approved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        constraints = [models.UniqueConstraint(fields=("product", "customer"), name="unique_customer_product_review")]

    def __str__(self):
        return f"{self.product.name} ({self.rating}/5)"


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="store_profile")
    phone = models.CharField(max_length=20, blank=True, validators=[validate_phone])

    def __str__(self):
        return f"{self.user.username} profile"


class Address(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="addresses")
    label = models.CharField(max_length=60, default="Home")
    full_name = models.CharField(max_length=150)
    phone = models.CharField(max_length=20, validators=[validate_phone])
    address = models.TextField()
    city = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=12, validators=[validate_pin])
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-is_default", "-created_at")

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.is_default:
            Address.objects.filter(user=self.user).exclude(pk=self.pk).update(is_default=False)

    def __str__(self):
        return f"{self.label}: {self.city}"


class WishlistItem(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="wishlist_items")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="wishlisted_by")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        constraints = [models.UniqueConstraint(fields=("user", "product"), name="unique_user_wishlist_product")]

    def __str__(self):
        return f"{self.user.username}: {self.product.name}"


class CouponRedemption(models.Model):
    coupon = models.ForeignKey(Coupon, on_delete=models.PROTECT, related_name="redemptions")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="coupon_redemptions")
    order = models.OneToOneField("Order", on_delete=models.CASCADE, related_name="coupon_redemption")
    redeemed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.coupon.code} on order {self.order_id}"


class HomepageBanner(models.Model):
    THEME_CHOICES = [
        ("ruby", "Ruby festive"),
        ("midnight", "Midnight blue"),
        ("walnut", "Warm walnut"),
        ("olive", "Olive living"),
    ]

    title = models.CharField(max_length=120)
    subtitle = models.CharField(max_length=240, blank=True)
    description = models.CharField(max_length=280, blank=True)
    eyebrow = models.CharField(max_length=100, blank=True)
    offer_text = models.CharField(max_length=160, blank=True)
    offer_code = models.CharField(max_length=40, blank=True)
    card_title = models.CharField(max_length=100, blank=True)
    card_subtitle = models.CharField(max_length=140, blank=True)
    cta_label = models.CharField(max_length=80, blank=True, default="Explore collection")
    category_name = models.CharField(max_length=100, blank=True)
    theme = models.CharField(max_length=12, choices=THEME_CHOICES, default="ruby")
    image = models.ImageField(
        upload_to="banners/%Y/%m/",
        help_text="Upload an original, licensed, high-resolution banner image.",
    )
    alt_text = models.CharField(max_length=180, blank=True)
    link_url = models.URLField(blank=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ("sort_order", "id")

    def __str__(self):
        return self.title


class StoreLocation(models.Model):
    city = models.CharField(max_length=90)
    state = models.CharField(max_length=90)
    address = models.CharField(max_length=255, blank=True)
    store_count = models.PositiveSmallIntegerField(null=True, blank=True)
    description = models.CharField(max_length=240, blank=True)
    image = models.ImageField(upload_to="stores/%Y/%m/", blank=True)
    image_credit = models.CharField(max_length=180, blank=True)
    image_source_url = models.URLField(blank=True)
    map_url = models.URLField(blank=True)
    sort_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=False)

    class Meta:
        ordering = ("sort_order", "city", "id")
        constraints = [
            models.UniqueConstraint(fields=("city", "state"), name="unique_eroma_store_city_state")
        ]

    def clean(self):
        if self.is_active and (not self.address or not self.image):
            raise ValidationError("Add a verified showroom address and image before publishing this location.")

    def __str__(self):
        return f"{self.city}, {self.state}"

class Order(models.Model):
    STATUS_CHOICES = [
        ("placed", "Placed"), ("ready_to_pack", "Ready to pack"),
        ("packed", "Packed"), ("dispatched", "Dispatched"),
        ("in_transit", "In transit"), ("out_for_delivery", "Out for delivery"),
        ("delivered", "Delivered"), ("cancelled", "Cancelled"),
    ]
    PAYMENT_CHOICES = [("cod", "Cash on Delivery"), ("razorpay", "Razorpay"), ("test_card", "Test card (simulated)")]
    PAYMENT_STATUS_CHOICES = [
        ("pending", "Pending"),
        ("paid", "Paid"),
        ("failed", "Failed"),
        ("refunded", "Refunded"),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="orders")
    full_name = models.CharField(max_length=150)
    email = models.EmailField()
    phone = models.CharField(max_length=20, validators=[validate_phone])
    address = models.TextField()
    city = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=12, validators=[validate_pin])
    payment_method = models.CharField(max_length=20, choices=PAYMENT_CHOICES, default="cod")
    razorpay_order_id = models.CharField(max_length=64, blank=True)
    razorpay_payment_id = models.CharField(max_length=64, blank=True)
    emi_requested = models.BooleanField(default=False)
    payment_instrument = models.CharField(max_length=20, blank=True)
    coupon = models.ForeignKey(Coupon, on_delete=models.SET_NULL, null=True, blank=True, related_name="orders")
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    payment_status = models.CharField(
        max_length=12, choices=PAYMENT_STATUS_CHOICES, default="pending"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="placed")
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    shipping_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tracking_code = models.CharField(max_length=32, unique=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    def save(self, *args, **kwargs):
        if not self.tracking_code:
            import uuid
            self.tracking_code = uuid.uuid4().hex[:12].upper()
        super().save(*args, **kwargs)
    def __str__(self): return f"Order #{self.pk} — {self.user.username}"

class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    product_name = models.CharField(max_length=180)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    color = models.CharField(max_length=50, blank=True)
    def __str__(self): return f"{self.product_name} x {self.quantity}"


class CallbackRequest(models.Model):
    STATUS_CHOICES = [("new", "New"), ("contacted", "Contacted"), ("closed", "Closed")]

    name = models.CharField(max_length=120)
    email = models.EmailField()
    phone = models.CharField(max_length=40, validators=[validate_phone])
    postal_code = models.CharField(max_length=12, validators=[validate_pin])
    city = models.CharField(max_length=100, blank=True)
    message = models.TextField(max_length=2000)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="new")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"Callback request from {self.name} ({self.phone})"


class ContactMessage(models.Model):
    STATUS_CHOICES = [("new", "New"), ("reviewed", "Reviewed"), ("closed", "Closed")]

    name = models.CharField(max_length=120)
    email = models.EmailField()
    phone = models.CharField(max_length=40, blank=True, validators=[validate_phone])
    message = models.TextField(max_length=4000)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="new")
    notification_sent = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return f"Website enquiry from {self.name} ({self.created_at:%Y-%m-%d})"
