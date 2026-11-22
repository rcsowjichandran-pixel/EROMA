from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import Group, User
from django.db.models import Sum
from django.utils.html import format_html
from django.urls import reverse

from .models import (
    Category,
    CategoryImage,
    Address,
    CallbackRequest,
    ContactMessage,
    Coupon,
    CouponRedemption,
    FooterPageContent,
    HomepageBanner,
    Offer,
    Order,
    OrderItem,
    Product,
    ProductImage,
    ProductReview,
    StoreLocation,
    SiteBranding,
    UserProfile,
    WishlistItem,
)


class SofaLuxAdminSite(admin.AdminSite):
    site_header = "EROMA Admin Studio"
    site_title = "EROMA Admin"
    index_title = "Furniture for every space."
    index_template = "store/admin/index.html"

    def index(self, request, extra_context=None):
        extra_context = dict(extra_context or {})
        extra_context["studio_metrics"] = [
            {
                "label": "Products",
                "value": Product.objects.count(),
                "detail": "Catalogue items",
                "url": reverse(f"{self.name}:store_product_changelist"),
            },
            {
                "label": "Categories",
                "value": Category.objects.filter(parent__isnull=True).count(),
                "detail": "Parent collections",
                "url": reverse(f"{self.name}:store_category_changelist"),
            },
            {
                "label": "Orders",
                "value": Order.objects.count(),
                "detail": "All customer orders",
                "url": reverse(f"{self.name}:store_order_changelist"),
            },
            {
                "label": "Offers",
                "value": Offer.objects.filter(is_active=True).count(),
                "detail": "Active promotions",
                "url": reverse(f"{self.name}:store_offer_changelist"),
            },
            {
                "label": "Store locations",
                "value": StoreLocation.objects.filter(is_active=True).count(),
                "detail": "Published showroom cards",
                "url": reverse(f"{self.name}:store_storelocation_changelist"),
            },
            {
                "label": "Customers",
                "value": User.objects.filter(is_staff=False).count(),
                "detail": "Registered customers",
                "url": reverse("admin:auth_user_changelist"),
            },
            {
                "label": "Sales",
                "value": Order.objects.exclude(status="cancelled").aggregate(total=Sum("total"))["total"] or 0,
                "detail": "Non-cancelled order value",
                "url": reverse(f"{self.name}:store_order_changelist"),
            },
        ]
        return super().index(request, extra_context)


admin_site = SofaLuxAdminSite(name="admin")
admin_site.register(User, UserAdmin)
admin_site.register(Group)


@admin.register(CallbackRequest, site=admin_site)
class CallbackRequestAdmin(admin.ModelAdmin):
    list_display = ("name", "phone", "email", "city", "postal_code", "status", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("name", "email", "phone", "city", "postal_code", "message")
    list_editable = ("status",)
    readonly_fields = ("created_at",)
    ordering = ("-created_at",)


@admin.register(ContactMessage, site=admin_site)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "phone", "status", "notification_sent", "created_at")
    list_filter = ("status", "notification_sent", "created_at")
    search_fields = ("name", "email", "phone", "message")
    list_editable = ("status",)
    readonly_fields = ("created_at", "notification_sent")
    ordering = ("-created_at",)


@admin.register(FooterPageContent, site=admin_site)
class FooterPageContentAdmin(admin.ModelAdmin):
    list_display = ("title", "key", "is_active", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("title", "key", "summary", "body")
    list_editable = ("is_active",)
    readonly_fields = ("updated_at",)
    fields = ("key", "title", "eyebrow", "summary", "body", "image", "image_alt_text", "action_label", "action_url", "is_active", "updated_at")


@admin.register(Address, site=admin_site)
class AddressAdmin(admin.ModelAdmin):
    list_display = ("label", "full_name", "user", "city", "postal_code", "is_default")
    list_filter = ("is_default", "city")
    search_fields = ("full_name", "user__username", "phone", "city", "postal_code")


@admin.register(UserProfile, site=admin_site)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "phone")
    search_fields = ("user__username", "user__email", "phone")


@admin.register(WishlistItem, site=admin_site)
class WishlistItemAdmin(admin.ModelAdmin):
    list_display = ("user", "product", "created_at")
    search_fields = ("user__username", "product__name")


@admin.register(CouponRedemption, site=admin_site)
class CouponRedemptionAdmin(admin.ModelAdmin):
    list_display = ("coupon", "user", "order", "redeemed_at")
    list_filter = ("coupon", "redeemed_at")
    search_fields = ("coupon__code", "user__username", "order__id")


class CategoryInline(admin.TabularInline):
    model = Category
    fk_name = "parent"
    extra = 0
    fields = ("image_thumbnail", "name", "slug", "image")
    readonly_fields = ("image_thumbnail",)
    prepopulated_fields = {"slug": ("name",)}
    verbose_name = "Subcategory"
    verbose_name_plural = "Subcategories"

    @admin.display(description="Image")
    def image_thumbnail(self, obj):
        if not obj or not obj.image:
            return "No image"
        return format_html('<img src="{}" alt="" class="category-admin-thumb">', obj.image.url)


@admin.register(Category, site=admin_site)
class CategoryAdmin(admin.ModelAdmin):
    class Media:
        css = {"all": ("store/admin.css",)}

    list_display = ("image_thumbnail", "name", "slug", "subcategory_count")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    fields = ("image_preview", "name", "slug", "image")
    readonly_fields = ("image_preview",)
    inlines = [CategoryInline]

    def get_queryset(self, request):
        return super().get_queryset(request).filter(parent__isnull=True)

    @admin.display(description="Subcategories")
    def subcategory_count(self, obj):
        return obj.subcategories.count()

    @admin.display(description="Image")
    def image_thumbnail(self, obj):
        if not obj.image:
            return "No image"
        return format_html('<img src="{}" alt="" class="category-admin-thumb">', obj.image.url)

    @admin.display(description="Current category image")
    def image_preview(self, obj):
        if not obj or not obj.image:
            return "Upload a category image."
        return format_html('<img src="{}" alt="{}" class="product-admin-preview">', obj.image.url, obj.name)


@admin.register(CategoryImage, site=admin_site)
class CategoryImageAdmin(admin.ModelAdmin):
    class Media:
        css = {"all": ("store/admin.css",)}

    list_display = ("image_thumbnail", "category", "alt_text", "sort_order")
    list_filter = ("category",)
    search_fields = ("category__name", "alt_text", "source_name")
    list_editable = ("sort_order",)
    fields = ("image_preview", "category", "image", "alt_text", "source_name", "sort_order")
    readonly_fields = ("image_preview",)

    @admin.display(description="Image")
    def image_thumbnail(self, obj):
        if not obj.image:
            return "No image"
        return format_html('<img src="{}" alt="" class="category-admin-thumb">', obj.image.url)

    @admin.display(description="Current gallery image")
    def image_preview(self, obj):
        if not obj or not obj.image:
            return "Upload a gallery image."
        return format_html(
            '<img src="{}" alt="{}" class="product-admin-preview">',
            obj.image.url,
            obj.alt_text or obj.category.name,
        )


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1
    fields = ("image", "alt_text", "is_primary", "sort_order")

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        field = super().formfield_for_dbfield(db_field, request, **kwargs)
        if db_field.name == "alt_text":
            field.help_text = "For a colour-specific product photo, enter Colour: Olive (use the exact configured colour name)."
        return field


@admin.register(Product, site=admin_site)
class ProductAdmin(admin.ModelAdmin):
    class Media:
        css = {"all": ("store/admin.css",)}

    list_display = (
        "image_thumbnail",
        "name",
        "sku",
        "category",
        "price",
        "stock",
        "status",
        "featured",
        "best_seller",
        "new_arrival",
    )
    readonly_fields = ("image_preview",)
    list_filter = ("category", "status", "featured", "best_seller", "new_arrival")
    list_editable = ("price", "stock", "status", "featured", "best_seller", "new_arrival")
    search_fields = ("name", "sku", "slug", "description")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [ProductImageInline]
    fieldsets = (
        (None, {"fields": ("name", "slug", "sku", "category", "status")}),
        ("Product image", {"fields": ("image_preview", "image_url")}),
        ("Pricing and inventory", {"fields": ("regular_price", "price", "stock")}),
        ("Descriptions", {"fields": ("short_description", "description")}),
        (
            "Product specifications",
            {
                "fields": (
                    "material",
                    "fabric_type",
                    "frame_material",
                    "cushion_filling",
                    "color_options",
                    "dimensions",
                    "weight_kg",
                    "warranty",
                    "seats",
                )
            },
        ),
        ("Merchandising", {"fields": ("featured", "best_seller", "new_arrival")}),
    )

    def _image_url(self, obj):
        primary_image = obj.images.filter(is_primary=True).first()
        if primary_image and primary_image.image:
            return primary_image.image.url
        return obj.image_url

    @admin.display(description="Image")
    def image_thumbnail(self, obj):
        url = self._image_url(obj)
        if not url:
            return "No image"
        return format_html('<img src="{}" alt="" class="product-admin-thumb">', url)

    @admin.display(description="Current product image")
    def image_preview(self, obj):
        if not obj:
            return "Save the product to add or preview its image."
        url = self._image_url(obj)
        if not url:
            return "No image assigned yet. Add an image URL or upload one below."
        return format_html('<img src="{}" alt="{}" class="product-admin-preview">', url, obj.name)


@admin.register(ProductImage, site=admin_site)
class ProductImageAdmin(admin.ModelAdmin):
    class Media:
        css = {"all": ("store/admin.css",)}

    list_display = ("image_thumbnail", "product", "alt_text", "is_primary", "sort_order")
    list_filter = ("is_primary",)
    search_fields = ("product__name", "alt_text")

    @admin.display(description="Image")
    def image_thumbnail(self, obj):
        if not obj.image:
            return "No image"
        return format_html('<img src="{}" alt="" class="category-admin-thumb">', obj.image.url)


@admin.register(Offer, site=admin_site)
class OfferAdmin(admin.ModelAdmin):
    list_display = ("name", "banner_thumbnail", "coupon", "discount_type", "discount_value", "is_active", "starts_at", "ends_at")
    list_filter = ("is_active", "discount_type")
    search_fields = ("name", "description")
    filter_horizontal = ("products", "categories")

    @admin.display(description="Campaign card")
    def banner_thumbnail(self, obj):
        if not obj.banner_image:
            return "No campaign image"
        return format_html('<img src="{}" alt="{}" style="width:84px;height:64px;object-fit:cover;border-radius:5px">', obj.banner_image.url, obj.banner_alt_text or obj.name)


@admin.register(Coupon, site=admin_site)
class CouponAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "discount_type",
        "discount_value",
        "minimum_order",
        "usage_limit",
        "is_active",
        "ends_at",
    )
    list_filter = ("is_active", "discount_type")
    search_fields = ("code", "description")
    filter_horizontal = ("categories",)


@admin.register(ProductReview, site=admin_site)
class ProductReviewAdmin(admin.ModelAdmin):
    list_display = ("product", "customer_name", "rating", "is_approved", "created_at")
    list_filter = ("rating", "is_approved", "created_at")
    search_fields = ("product__name", "customer_name", "body")
    list_editable = ("is_approved",)


@admin.register(HomepageBanner, site=admin_site)
class HomepageBannerAdmin(admin.ModelAdmin):
    list_display = ("title", "theme", "sort_order", "is_active", "starts_at", "ends_at")
    list_filter = ("is_active", "theme")
    search_fields = ("title", "subtitle", "eyebrow", "offer_code")
    list_editable = ("sort_order", "is_active")
    fields = ("title", "subtitle", "description", "eyebrow", "offer_text", "offer_code", "card_title", "card_subtitle", "cta_label", "category_name", "theme", "image", "alt_text", "link_url", "sort_order", "starts_at", "ends_at", "is_active")


@admin.register(StoreLocation, site=admin_site)
class StoreLocationAdmin(admin.ModelAdmin):
    list_display = ("city", "state", "store_count", "sort_order", "is_active")
    list_filter = ("state", "is_active")
    search_fields = ("city", "state", "address", "description")
    list_editable = ("sort_order", "is_active")
    fieldsets = (
        ("Showroom", {"fields": ("city", "state", "address", "store_count", "description", "map_url")}),
        ("Card image", {"fields": ("image", "image_credit", "image_source_url")}),
        ("Homepage", {"fields": ("sort_order", "is_active")}),
    )


@admin.register(SiteBranding, site=admin_site)
class SiteBrandingAdmin(admin.ModelAdmin):
    list_display = ("id", "logo_alt_text", "updated_at")
    fields = ("logo", "logo_alt_text")


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("product", "product_name", "quantity", "unit_price")


@admin.register(Order, site=admin_site)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "full_name",
        "total",
        "status",
        "payment_status",
        "emi_requested",
        "payment_instrument",
        "created_at",
    )
    list_filter = ("status", "payment_status", "payment_method", "created_at")
    search_fields = ("full_name", "email", "phone")
    list_editable = ("status", "payment_status")
    inlines = [OrderItemInline]
