from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from rest_framework import serializers
from .checkout_amounts import checkout_amounts, coupon_discount
from .contact_fields import PHONE_PATTERN, PIN_PATTERN, PHONE_ERROR, PIN_ERROR
from .models import Address, Category, CategoryImage, HomepageBanner, Product, ProductImage, Order, OrderItem, ProductReview, UserProfile, WishlistItem, StoreLocation, Offer, FooterPageContent, SiteBranding
from .models import SOCIAL_PLATFORMS, social_link_errors


def coupon_category_ids(coupon):
    roots = list(coupon.categories.all())
    ids = {category.id for category in roots}
    for category in roots:
        ids.update(category.subcategories.values_list("id", flat=True))
    return ids

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    class Meta:
        model = User
        fields = ("id", "username", "email", "password")

    def validate(self, attrs):
        customer = User(username=attrs["username"], email=attrs.get("email", ""))
        try:
            validate_password(attrs["password"], user=customer)
        except DjangoValidationError as error:
            raise serializers.ValidationError({"password": error.messages}) from error
        return attrs

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)

class CategoryImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = CategoryImage
        fields = ("id", "image", "alt_text", "sort_order")


class CategorySerializer(serializers.ModelSerializer):
    parent_name = serializers.CharField(source="parent.name", read_only=True, allow_null=True)
    images = CategoryImageSerializer(source="gallery_images", many=True, read_only=True)

    class Meta:
        model = Category
        fields = ("id", "name", "slug", "image", "images", "parent", "parent_name")


class HomepageBannerSerializer(serializers.ModelSerializer):
    class Meta:
        model = HomepageBanner
        fields = ("id", "title", "subtitle", "description", "eyebrow", "offer_text", "offer_code", "card_title", "card_subtitle", "cta_label", "category_name", "theme", "image", "alt_text", "link_url", "sort_order", "is_active")


class StoreLocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = StoreLocation
        fields = ("id", "city", "state", "address", "store_count", "description", "image", "image_credit", "image_source_url", "map_url", "sort_order", "is_active")

    def validate(self, attrs):
        active = attrs.get("is_active", getattr(self.instance, "is_active", False))
        address = attrs.get("address", getattr(self.instance, "address", ""))
        image = attrs.get("image", getattr(self.instance, "image", None))
        if active and (not address or not image):
            raise serializers.ValidationError("Add a verified showroom address and image before publishing this location.")
        return attrs


class OfferBannerSerializer(serializers.ModelSerializer):
    categories = serializers.PrimaryKeyRelatedField(many=True, read_only=True)
    products = serializers.PrimaryKeyRelatedField(many=True, read_only=True)
    coupon_code = serializers.CharField(source="coupon.code", read_only=True, allow_null=True)
    coupon_discount_value = serializers.DecimalField(source="coupon.discount_value", max_digits=8, decimal_places=2, read_only=True, allow_null=True)
    coupon_discount_type = serializers.CharField(source="coupon.discount_type", read_only=True, allow_null=True)
    coupon_minimum_order = serializers.DecimalField(source="coupon.minimum_order", max_digits=10, decimal_places=2, read_only=True, allow_null=True)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        coupon = instance.coupon
        now = timezone.now()
        if coupon and (
            not coupon.is_active
            or (coupon.starts_at and coupon.starts_at > now)
            or (coupon.ends_at and coupon.ends_at < now)
            or (coupon.usage_limit is not None and coupon.redemptions.count() >= coupon.usage_limit)
        ):
            for name in ("coupon_code", "coupon_discount_value", "coupon_discount_type", "coupon_minimum_order"):
                data[name] = None
        return data

    class Meta:
        model = Offer
        fields = ("id", "name", "description", "discount_type", "discount_value", "banner_image", "banner_alt_text", "categories", "products", "coupon_code", "coupon_discount_value", "coupon_discount_type", "coupon_minimum_order", "starts_at", "ends_at")


class FooterPageContentSerializer(serializers.ModelSerializer):
    class Meta:
        model = FooterPageContent
        fields = ("id", "key", "title", "eyebrow", "summary", "body", "image", "image_alt_text", "action_label", "action_url", "is_active", "updated_at")


class NewsletterSignupSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)


class SiteBrandingSerializer(serializers.ModelSerializer):
    class Meta:
        model = SiteBranding
        fields = ("id", "logo", "logo_alt_text", "updated_at", "assistant_mode", *SOCIAL_PLATFORMS)

    def validate(self, attrs):
        errors = social_link_errors(attrs)
        if errors:
            raise serializers.ValidationError(errors)
        return attrs

    def update(self, instance, validated_data):
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save(update_fields=[*validated_data, "updated_at"])
        instance.refresh_from_db()
        return instance


class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ("id", "image", "alt_text", "is_primary", "sort_order")

class ProductSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)
    images = ProductImageSerializer(many=True, read_only=True)
    average_rating = serializers.FloatField(read_only=True, allow_null=True, required=False)
    review_count = serializers.IntegerField(read_only=True, default=0, required=False)
    collective_rating = serializers.SerializerMethodField()
    collective_review_count = serializers.SerializerMethodField()
    collective_is_sample = serializers.SerializerMethodField()

    def get_collective_rating(self, obj):
        collective = self.context.get("collective_product_rating", {})
        real_rating = collective.get("real_average", {})
        return real_rating.get("average") if real_rating.get("count") else collective.get("sample_average", {}).get("average")

    def get_collective_review_count(self, obj):
        collective = self.context.get("collective_product_rating", {})
        real_rating = collective.get("real_average", {})
        return real_rating.get("count") if real_rating.get("count") else collective.get("sample_average", {}).get("count", 0)

    def get_collective_is_sample(self, obj):
        collective = self.context.get("collective_product_rating", {})
        return not bool(collective.get("real_average", {}).get("count")) and bool(collective.get("sample_average", {}).get("count"))

    class Meta:
        model = Product
        fields = (
            "id", "name", "slug", "sku", "short_description", "category", "category_name",
            "description", "price", "regular_price", "image_url", "images", "material",
            "fabric_type", "frame_material", "cushion_filling", "color_options", "dimensions",
            "weight_kg", "warranty", "seats", "stock", "featured", "best_seller",
            "new_arrival", "status", "created_at", "average_rating", "review_count",
            "collective_rating", "collective_review_count", "collective_is_sample",
        )

    def to_representation(self, instance):
        data = super().to_representation(instance)
        images = list(instance.images.all())
        primary_image = next((image for image in images if image.is_primary and image.image), None)
        if not primary_image and not data["image_url"]:
            primary_image = next((image for image in images if image.image), None)
        if primary_image and primary_image.image:
            image_url = primary_image.image.url
            request = self.context.get("request")
            data["image_url"] = request.build_absolute_uri(image_url) if request else image_url
        return data


class AddressSerializer(serializers.ModelSerializer):
    phone = serializers.RegexField(PHONE_PATTERN, error_messages={"invalid": PHONE_ERROR})
    postal_code = serializers.RegexField(PIN_PATTERN, error_messages={"invalid": PIN_ERROR})

    class Meta:
        model = Address
        exclude = ("user",)
        read_only_fields = ("id", "created_at")


class UserProfileSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField(allow_blank=True)
    first_name = serializers.CharField(max_length=150, allow_blank=True, required=False)
    last_name = serializers.CharField(max_length=150, allow_blank=True, required=False)
    phone = serializers.RegexField(PHONE_PATTERN, allow_blank=True, required=False, error_messages={"invalid": PHONE_ERROR})
    is_staff = serializers.BooleanField(read_only=True)

    def validate_username(self, value):
        if User.objects.exclude(pk=self.instance.pk).filter(username=value).exists():
            raise serializers.ValidationError("That username is already in use.")
        return value

    def validate_email(self, value):
        if value and User.objects.exclude(pk=self.instance.pk).filter(email__iexact=value).exists():
            raise serializers.ValidationError("That email address is already in use.")
        return value

    def update(self, instance, validated_data):
        phone = validated_data.pop("phone", None)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save()
        if phone is not None:
            profile, _ = UserProfile.objects.get_or_create(user=instance)
            profile.phone = phone
            profile.save(update_fields=("phone",))
        return instance

    def create(self, validated_data):
        raise NotImplementedError


class WishlistItemSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(
        source="product", queryset=Product.objects.filter(status="active"), write_only=True
    )

    class Meta:
        model = WishlistItem
        fields = ("id", "product", "product_id", "created_at")
        read_only_fields = ("id", "created_at")


class ProductReviewSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(read_only=True)
    product_name = serializers.CharField(source="product.name", read_only=True)

    class Meta:
        model = ProductReview
        fields = ("id", "product", "product_name", "customer_name", "rating", "body", "created_at")
        read_only_fields = ("id", "customer_name", "created_at")

    def validate_rating(self, value):
        if value < 1 or value > 5:
            raise serializers.ValidationError("Choose a rating from 1 to 5.")
        return value

class OrderItemSerializer(serializers.ModelSerializer):
    class Meta: model = OrderItem; fields = ("id", "product", "product_name", "quantity", "unit_price", "color")

class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    bill_available = serializers.BooleanField(read_only=True)
    coupon_code = serializers.CharField(source="coupon.code", read_only=True, allow_null=True)
    tracking_status = serializers.SerializerMethodField()
    tracking_demo = serializers.SerializerMethodField()

    def get_tracking_status(self, order):
        from django.conf import settings
        from django.utils import timezone

        if not settings.ORDER_TRACKING_DEMO_AUTO_ADVANCE or order.status in ("cancelled", "delivered"):
            return order.status
        statuses = [status for status, _ in order.STATUS_CHOICES if status != "cancelled"]
        actual_index = statuses.index(order.status) if order.status in statuses else 0
        elapsed_days = max(0, (timezone.localdate() - timezone.localdate(order.created_at)).days)
        return statuses[min(max(actual_index, elapsed_days), len(statuses) - 1)]

    def get_tracking_demo(self, order):
        from django.conf import settings
        return settings.ORDER_TRACKING_DEMO_AUTO_ADVANCE and order.status not in ("cancelled", "delivered")

    class Meta:
        model = Order
        fields = ("id", "full_name", "email", "phone", "address", "city", "postal_code",
                  "payment_method", "payment_status", "payment_instrument", "emi_requested", "status", "total", "discount_amount",
                  "shipping_amount", "tax_amount", "coupon_code", "tracking_code", "created_at",
                  "tracking_status", "tracking_demo", "bill_available", "items")
        read_only_fields = ("payment_instrument", "emi_requested")

class OrderLineInputSerializer(serializers.Serializer):
    product_id = serializers.IntegerField(min_value=1)
    quantity = serializers.IntegerField(min_value=1)
    color = serializers.CharField(max_length=50, allow_blank=True, required=False, default="")


class CreateOrderSerializer(serializers.Serializer):
    full_name = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    phone = serializers.RegexField(PHONE_PATTERN, error_messages={"invalid": PHONE_ERROR})
    address = serializers.CharField()
    city = serializers.CharField(max_length=100)
    postal_code = serializers.RegexField(PIN_PATTERN, error_messages={"invalid": PIN_ERROR})
    payment_method = serializers.ChoiceField(choices=["cod", "razorpay", "test_card"], default="cod")
    coupon_code = serializers.CharField(max_length=40, allow_blank=True, required=False)
    items = OrderLineInputSerializer(many=True, allow_empty=False)

    def validate(self, attrs):
        from django.conf import settings
        if attrs["payment_method"] == "test_card" and not settings.DEBUG:
            raise serializers.ValidationError({"payment_method": "Simulated payments are available only in DEBUG mode."})
        return attrs

    def create(self, validated):
        from django.db import transaction
        from decimal import Decimal
        from django.utils import timezone
        from .models import Coupon, CouponRedemption

        with transaction.atomic():
            quantities = {}
            for row in validated["items"]:
                quantities[row["product_id"]] = quantities.get(row["product_id"], 0) + row["quantity"]
            products = {}
            for product_id in sorted(quantities):
                quantity = quantities[product_id]
                try:
                    product = Product.objects.select_for_update().get(pk=product_id, status="active")
                except Product.DoesNotExist:
                    raise serializers.ValidationError({"items": f"Product {product_id} is unavailable."})
                if product.stock < quantity:
                    raise serializers.ValidationError({"items": f"Insufficient stock for {product.name}."})
                products[product.pk] = product

            for row in validated["items"]:
                product = products[row["product_id"]]
                color = row.get("color", "").strip()
                options = [choice.strip().casefold() for choice in product.color_options.split(",") if choice.strip()]
                if color and options and color.casefold() not in options:
                    raise serializers.ValidationError({"items": f"{color} is not an available colour for {product.name}."})

            total = Decimal("0.00")
            for product_id, qty in quantities.items():
                product = products[product_id]
                product.stock -= qty
                product.save(update_fields=["stock"])
                total += product.price * qty

            coupon = None
            discount = Decimal("0.00")
            code = validated.get("coupon_code", "").strip().upper()
            if code:
                try:
                    coupon = Coupon.objects.select_for_update().get(code=code, is_active=True)
                except Coupon.DoesNotExist:
                    raise serializers.ValidationError({"coupon_code": "This coupon is invalid or inactive."})
                now = timezone.now()
                if coupon.starts_at and coupon.starts_at > now or coupon.ends_at and coupon.ends_at < now:
                    raise serializers.ValidationError({"coupon_code": "This coupon is outside its valid dates."})
                applicable_category_ids = coupon_category_ids(coupon)
                eligible_total = total
                if applicable_category_ids:
                    eligible_total = sum(
                        product.price * quantities[product_id]
                        for product_id, product in products.items()
                        if product.category_id in applicable_category_ids
                    )
                    if not eligible_total:
                        raise serializers.ValidationError({"coupon_code": "This coupon only applies to selected furniture categories."})
                if eligible_total < coupon.minimum_order:
                    raise serializers.ValidationError({"coupon_code": f"Minimum order is ₹{coupon.minimum_order}."})
                if coupon.usage_limit is not None and coupon.redemptions.count() >= coupon.usage_limit:
                    raise serializers.ValidationError({"coupon_code": "This coupon has reached its usage limit."})
                discount = coupon_discount(coupon, eligible_total)

            tax_amount, shipping_amount, payable_total = checkout_amounts(total, discount)

            order = Order.objects.create(
                user=self.context["request"].user,
                full_name=validated["full_name"], email=validated["email"], phone=validated["phone"],
                address=validated["address"], city=validated["city"], postal_code=validated["postal_code"],
                payment_method=validated.get("payment_method", "cod"),
                payment_status="paid" if validated.get("payment_method") == "test_card" else "pending",
                coupon=coupon, discount_amount=discount, tax_amount=tax_amount,
                shipping_amount=shipping_amount, total=payable_total,
            )
            # Order rows are written after the order exists to preserve FK consistency.
            for row in validated["items"]:
                product = products[row["product_id"]]
                OrderItem.objects.create(order=order, product=product, product_name=product.name,
                                         quantity=row["quantity"], unit_price=product.price,
                                         color=row.get("color", "").strip()[:50])
            if coupon:
                CouponRedemption.objects.create(coupon=coupon, user=self.context["request"].user, order=order)
            return order
