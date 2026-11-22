import json
import base64
import hashlib
import hmac
import logging
import urllib.error
import urllib.request
import re
import time
from collections import Counter
from decimal import Decimal
from rest_framework import generics, viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.throttling import ScopedRateThrottle
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.mail import EmailMessage, send_mail
from django.db.models import Sum, Q, F, Avg, Count, Prefetch
from django.utils import timezone
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.contrib.auth.tokens import default_token_generator
from .models import Address, CallbackRequest, ContactMessage, Coupon, CouponRedemption, Product, ProductImage, ProductReview, Category, HomepageBanner, Order, OrderItem, UserProfile, WishlistItem, StoreLocation, Offer, FooterPageContent, SiteBranding
from .serializers import AddressSerializer, RegisterSerializer, ProductSerializer, ProductImageSerializer, CategorySerializer, HomepageBannerSerializer, OrderSerializer, CreateOrderSerializer, ProductReviewSerializer, UserProfileSerializer, WishlistItemSerializer, OrderLineInputSerializer, StoreLocationSerializer, OfferBannerSerializer, FooterPageContentSerializer, SiteBrandingSerializer, coupon_category_ids
from .permissions import IsStaffOrReadOnly
from .contact_fields import PHONE_PATTERN, PIN_PATTERN, PHONE_ERROR, PIN_ERROR

logger = logging.getLogger(__name__)


def _search_category_name(query):
    """Resolve common furniture search terms to their catalog parent category."""
    words = set(re.findall(r"[a-z0-9]+", str(query).casefold()))
    category_terms = (
        ({"sofa", "sofas", "couch", "couches"}, "Sofas"),
        ({"chair", "chairs", "armchair", "armchairs", "recliner", "recliners"}, "Chairs & Armchairs"),
        ({"lounger", "loungers", "ottoman", "ottomans", "pouffe", "pouffes"}, "Loungers & Ottomans"),
        ({"dining", "diningtable", "diningset"}, "Dining Furniture"),
        ({"bed", "beds", "bedroom", "bedside"}, "Beds & Bedroom"),
        ({"table", "tables", "desk", "desks"}, "Tables"),
        ({"storage", "cabinet", "cabinets", "wardrobe", "wardrobes"}, "Storage Furniture"),
        ({"office", "officechair", "officedesk"}, "Office Furniture"),
        ({"decor", "lighting", "lamp", "lamps", "floorlamp", "floorlamps"}, "Home Decor & Lighting"),
    )
    for terms, category_name in category_terms:
        if words.intersection(terms):
            return category_name
    return None

def collective_product_rating():
    reviews = ProductReview.objects.filter(is_approved=True)
    return {
        "real_average": reviews.exclude(customer_name__endswith=" (Sample)").aggregate(
            average=Avg("rating"), count=Count("id")
        ),
        "sample_average": reviews.filter(customer_name__endswith=" (Sample)").aggregate(
            average=Avg("rating"), count=Count("id")
        ),
    }

class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

class ProductViewSet(viewsets.ModelViewSet):
    serializer_class = ProductSerializer
    permission_classes = [IsStaffOrReadOnly]
    parser_classes = [JSONParser, FormParser, MultiPartParser]
    queryset = Product.objects.select_related("category").prefetch_related("images").annotate(
        average_rating=Avg("reviews__rating", filter=Q(reviews__is_approved=True) & ~Q(reviews__customer_name__endswith=" (Sample)")),
        review_count=Count("reviews", filter=Q(reviews__is_approved=True) & ~Q(reviews__customer_name__endswith=" (Sample)")),
    ).all().order_by("-created_at")

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["collective_product_rating"] = collective_product_rating()
        return context

    def get_queryset(self):
        qs = super().get_queryset()
        if not self.request.user.is_staff:
            qs = qs.filter(status="active")
        search = self.request.query_params.get("search")
        category = self.request.query_params.get("category")
        if search:
            category_name = _search_category_name(search)
            if category_name:
                parent = Category.objects.filter(name=category_name, parent__isnull=True).first()
                qs = qs.filter(Q(category=parent) | Q(category__parent=parent)) if parent else qs.none()
            else:
                # Prefer actual product/category/material matches so incidental
                # description mentions do not dominate product search results.
                direct_matches = qs.filter(
                    Q(name__icontains=search)
                    | Q(material__icontains=search)
                    | Q(category__name__icontains=search)
                )
                qs = direct_matches if direct_matches.exists() else qs.filter(
                    Q(short_description__icontains=search) | Q(description__icontains=search)
                )
        if category: qs = qs.filter(category__slug=category)
        if self.request.query_params.get("featured") == "true": qs = qs.filter(featured=True)
        return qs

    @action(detail=True, methods=["post"], url_path="image")
    def upload_image(self, request, pk=None):
        product = self.get_object()
        image = request.FILES.get("image")
        if image is None:
            return Response({"image": ["Choose an image to upload."]}, status=status.HTTP_400_BAD_REQUEST)

        image_serializer = ProductImageSerializer(data={
            "image": image,
            "alt_text": request.data.get("alt_text", product.name),
            "is_primary": True,
            "sort_order": 0,
        }, context={"request": request})
        image_serializer.is_valid(raise_exception=True)
        ProductImage.objects.filter(product=product, is_primary=True).update(is_primary=False)
        image_serializer.save(product=product)
        product.refresh_from_db()
        return Response(ProductSerializer(product, context={
            "request": request,
            "collective_product_rating": collective_product_rating(),
        }).data)


class ProductRecommendationView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "recommendations"

    def post(self, request):
        query = str(request.data.get("query", "")).strip()[:160]
        if len(query) < 2:
            return Response({"detail": "Enter at least two characters to get recommendations."}, status=status.HTTP_400_BAD_REQUEST)

        products_query = Product.objects.filter(status="active", stock__gt=0).select_related("category")
        category_name = _search_category_name(query)
        if category_name:
            parent = Category.objects.filter(name=category_name, parent__isnull=True).first()
            products_query = products_query.filter(Q(category=parent) | Q(category__parent=parent)) if parent else products_query.none()
        products = list(products_query[:100])
        words = {word.casefold() for word in query.split() if len(word) > 1}
        scored = []
        for product in products:
            searchable = " ".join((product.name, product.short_description, product.description, product.material, product.category.name)).casefold()
            score = sum(3 if word in product.name.casefold() else 1 for word in words if word in searchable)
            if score:
                scored.append((score, product))
        fallback = [product for _, product in sorted(scored, key=lambda row: (-row[0], -row[1].featured, row[1].name))[:4]]
        recommendations = fallback or list((products_query if category_name else Product.objects.filter(status="active", stock__gt=0).select_related("category")).order_by("-featured", "-best_seller", "-created_at")[:4])
        reason = "Picked from matching words in our product descriptions." if fallback else "Popular in the EROMA collection."
        source = "catalog"

        if settings.GEMINI_API_KEY and products:
            catalog = [{
                "id": product.id,
                "name": product.name,
                "category": product.category.name,
                "description": (product.short_description or product.description)[:180],
                "material": product.material,
                "price": str(product.price),
            } for product in products]
            prompt = (
                "You recommend furniture for EROMA, an Indian furniture store. Use only the product IDs in the catalog. "
                "Return valid JSON with keys product_ids (up to 4 integer IDs, best first) and reason (one short sentence). "
                "Never invent availability, product details, delivery promises, or IDs. "
                f"Customer search: {query!r}. Catalog: {json.dumps(catalog, ensure_ascii=False)}"
            )
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"responseMimeType": "application/json", "temperature": 0.2},
            }
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.GEMINI_MODEL}:generateContent"
            gemini_request = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json", "x-goog-api-key": settings.GEMINI_API_KEY},
                method="POST",
            )
            try:
                with urllib.request.urlopen(gemini_request, timeout=12) as response:
                    generated = json.loads(response.read().decode("utf-8"))
                text = generated["candidates"][0]["content"]["parts"][0]["text"]
                suggestion = json.loads(text)
                valid_ids = {product.id for product in products}
                ids = [int(value) for value in suggestion.get("product_ids", []) if str(value).isdigit() and int(value) in valid_ids][:4]
                by_id = {product.id: product for product in products}
                if ids:
                    recommendations = [by_id[product_id] for product_id in ids]
                    reason = str(suggestion.get("reason", "Selected for your search."))[:180]
                    source = "gemini"
            except (urllib.error.URLError, TimeoutError, ValueError, KeyError, IndexError, TypeError):
                pass

        return Response({
            "query": query,
            "source": source,
            "reason": reason,
            "products": ProductSerializer(recommendations, many=True, context={
                "request": request,
                "collective_product_rating": collective_product_rating(),
            }).data,
        })

class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = (
        Category.objects.select_related("parent")
        .prefetch_related("gallery_images")
        .all()
        .order_by("name")
    )
    serializer_class = CategorySerializer

class HomepageBannerViewSet(viewsets.ModelViewSet):
    serializer_class = HomepageBannerSerializer
    parser_classes = [JSONParser, FormParser, MultiPartParser]

    def get_permissions(self):
        if self.request.method in permissions.SAFE_METHODS:
            return [permissions.AllowAny()]
        return [permissions.IsAdminUser()]

    def get_queryset(self):
        queryset = HomepageBanner.objects.all().order_by("sort_order", "id")
        if not (self.request.user.is_staff and self.request.query_params.get("manage") == "1"):
            now = timezone.now()
            queryset = queryset.filter(is_active=True).filter(
                Q(starts_at__isnull=True) | Q(starts_at__lte=now),
                Q(ends_at__isnull=True) | Q(ends_at__gte=now),
            )
        return queryset

    @action(detail=False, methods=["post"], url_path="hero")
    def upload_hero(self, request):
        image = request.FILES.get("image")
        if image is None:
            return Response({"image": ["Choose a hero image to upload."]}, status=status.HTTP_400_BAD_REQUEST)

        banner = HomepageBanner.objects.filter(title="Homepage hero").order_by("id").first()
        created = banner is None
        payload = {
            "title": "Homepage hero",
            "subtitle": request.data.get("subtitle", "Furniture for every space."),
            "image": image,
            "alt_text": request.data.get("alt_text", "EROMA contemporary furniture hero"),
            "link_url": request.data.get("link_url", ""),
            "sort_order": 0,
            "is_active": True,
        }
        serializer = self.get_serializer(banner, data=payload, partial=bool(banner))
        serializer.is_valid(raise_exception=True)
        banner = serializer.save()
        return Response(
            self.get_serializer(banner).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class StoreLocationViewSet(viewsets.ModelViewSet):
    serializer_class = StoreLocationSerializer
    parser_classes = [JSONParser, FormParser, MultiPartParser]

    def get_permissions(self):
        if self.request.method in permissions.SAFE_METHODS:
            return [permissions.AllowAny()]
        return [permissions.IsAdminUser()]

    def get_queryset(self):
        queryset = StoreLocation.objects.all()
        if not self.request.user.is_staff:
            queryset = queryset.filter(is_active=True)
        return queryset


class SiteBrandingView(APIView):
    parser_classes = [JSONParser, FormParser, MultiPartParser]

    def get_permissions(self):
        if self.request.method in permissions.SAFE_METHODS:
            return [permissions.AllowAny()]
        return [permissions.IsAdminUser()]

    def get(self, request):
        branding, _ = SiteBranding.objects.get_or_create(pk=1)
        return Response(SiteBrandingSerializer(branding, context={"request": request}).data)

    def patch(self, request):
        branding, _ = SiteBranding.objects.get_or_create(pk=1)
        serializer = SiteBrandingSerializer(branding, data=request.data, partial=True, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class OfferBannerViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = OfferBannerSerializer
    permission_classes = [permissions.AllowAny]
    queryset = Offer.objects.none()

    def get_queryset(self):
        now = timezone.now()
        return Offer.objects.filter(is_active=True).filter(
            Q(starts_at__isnull=True) | Q(starts_at__lte=now),
            Q(ends_at__isnull=True) | Q(ends_at__gte=now),
        ).select_related("coupon").prefetch_related("categories", "products").order_by("-created_at")


class FooterPageContentViewSet(viewsets.ModelViewSet):
    serializer_class = FooterPageContentSerializer
    parser_classes = [JSONParser, FormParser, MultiPartParser]

    def get_permissions(self):
        if self.request.method in permissions.SAFE_METHODS:
            return [permissions.AllowAny()]
        return [permissions.IsAdminUser()]

    def get_queryset(self):
        queryset = FooterPageContent.objects.all()
        if not self.request.user.is_staff:
            queryset = queryset.filter(is_active=True)
        return queryset


class StoreChatView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "store_chat"

    @staticmethod
    def _public_site_context():
        """Build a compact public snapshot for Eri; never include customer data."""
        now = timezone.now()
        products = list(Product.objects.filter(status="active").select_related("category").order_by(
            "-featured", "-best_seller", "name"
        ).values(
            "name", "category__name", "short_description", "description", "material", "fabric_type",
            "frame_material", "cushion_filling", "color_options", "dimensions", "warranty", "price", "stock",
        )[:60])
        for product in products:
            product["description"] = (product["description"] or "")[:240]
            product["short_description"] = (product["short_description"] or "")[:160]

        categories = list(Category.objects.order_by("parent__name", "name").values("name", "parent__name")[:80])
        offers = Offer.objects.filter(is_active=True).filter(
            Q(starts_at__isnull=True) | Q(starts_at__lte=now),
            Q(ends_at__isnull=True) | Q(ends_at__gte=now),
        ).select_related("coupon").prefetch_related("categories", "products").order_by("name")[:20]
        current_offers = []
        for offer in offers:
            coupon = offer.coupon
            if coupon and (
                not coupon.is_active
                or (coupon.starts_at and coupon.starts_at > now)
                or (coupon.ends_at and coupon.ends_at < now)
            ):
                coupon = None
            current_offers.append({
                "name": offer.name,
                "description": offer.description[:200],
                "discount": f"{offer.discount_value}{'%' if offer.discount_type == 'percent' else ' INR'}",
                "coupon": coupon.code if coupon else "",
                "coupon_description": coupon.description if coupon else "",
                "eligible_categories": list(offer.categories.values_list("name", flat=True)),
                "eligible_products": list(offer.products.values_list("name", flat=True)[:10]),
            })

        stores = list(StoreLocation.objects.filter(is_active=True).values(
            "city", "state", "address", "store_count", "description", "map_url"
        )[:40])
        pages = list(FooterPageContent.objects.filter(is_active=True).values(
            "key", "title", "summary", "body"
        )[:20])
        for page in pages:
            page["body"] = (page["body"] or "")[:1200]

        return {
            "products": products,
            "categories": categories,
            "current_offers": current_offers,
            "published_store_locations": stores,
            "help_and_policy_pages": pages,
            "website_help": [
                "Search by product name, category, material, or room; category pages support price, stock, sale, and sorting filters.",
                "Product pages show available product details, dimensions, materials, color choices, warranty, price, stock, and reviews when provided.",
                "Use the delivery PIN checker in the header to check the postal area and the delivery availability shown by the site.",
                "The bag supports quantity changes and coupon application. Checkout uses a signed-in customer's saved address when available and allows address entry or editing.",
                "The site supports Cash on Delivery and Razorpay checkout. Payment methods and availability are confirmed during checkout.",
                "Sign in and open My Orders to view the order history and status saved for each order. Eri cannot see private order or account records.",
                "For returns, exchanges, damage, complaints, or service appointments, use Contact Us or hello@eroma.in. Do not promise an outcome or policy term unless it appears in the published policy pages.",
                "Eri can give general advice about furniture materials, cleaning, room planning, measurements, seating, style, and budget. Distinguish general advice from EROMA product specifications.",
            ],
        }

    def post(self, request):
        raw_messages = request.data.get("messages", [])
        if not isinstance(raw_messages, list):
            return Response({"detail": "Send chat messages as a list."}, status=status.HTTP_400_BAD_REQUEST)
        messages = []
        for message in raw_messages[-8:]:
            if not isinstance(message, dict) or message.get("role") not in ("user", "assistant"):
                continue
            text = str(message.get("text", "")).strip()[:700]
            if text:
                messages.append({"role": message["role"], "text": text})
        if not messages or messages[-1]["role"] != "user":
            return Response({"detail": "Type a message to start the conversation."}, status=status.HTTP_400_BAD_REQUEST)

        latest = messages[-1]["text"].casefold()
        material_comparison = (
            "leather" in latest and "fabric" in latest
            and any(word in latest for word in ("difference", "different", "compare", "versus", " vs ", "better"))
            and any(word in latest for word in ("sofa", "sofas", "couch"))
        )
        care_question = any(word in latest for word in ("clean", "cleaning", "care", "maintain", "maintenance", "remove stain"))
        recommendation_intent = any(phrase in latest for phrase in (
            "recommend", "suggest", "show me", "find me", "looking for", "available options", "browse", "shop for", "do you have", "in stock"
        ))
        room_colour_question = bool(
            re.search(r"\bcolou?rs?\b", latest) and re.search(r"\b(rooms?|walls?)\b", latest)
        )
        support_reply = None
        if any(phrase in latest for phrase in ("return", "returns", "refund", "exchange")):
            support_reply = (
                "I can help with a return or exchange. Please share your order number and the item name so our team can check the next step and the terms for that order. "
                "You can also email hello@eroma.in with those details."
            )
        elif any(phrase in latest for phrase in ("complaint", "damaged", "damage", "broken", "missing part", "service")):
            support_reply = (
                "I’m sorry you’re dealing with that. Please send your order number, item name, and a short description of the issue to hello@eroma.in. "
                "Our support team can review the order and guide you."
            )
        fallback = (
            "Check your six-digit PIN in the header to see the delivery area we found."
            if any(word in latest for word in ("deliver", "delivery", "pincode", "pin code")) else
            "Sign in and open My orders to see your order status and tracking details."
            if any(word in latest for word in ("order", "track", "tracking")) else
            "Offer cards show a coupon and the eligible furniture category. Add an eligible item to your bag, enter the code in the order summary, and choose Apply."
            if any(word in latest for word in ("coupon", "offer", "discount")) else
            "I’m here to help you find the right piece. What room are you furnishing, and what style or budget do you have in mind?"
        )
        if material_comparison:
            fallback = (
                "Leather sofas have a smooth, structured look and are usually quick to wipe clean. Fabric sofas come in more textures and colours and often feel softer. "
                "Care and durability depend on the specific upholstery, so check each product's material and care details. Would you like me to find EROMA sofas in either material or within a budget?"
            )
        elif not care_question and any(term in latest for term in ("leather", "fabric", "velvet", "wood", "engineered wood", "foam", "upholstery", "upholstered")):
            if "leather" in latest and "fabric" in latest:
                fallback = "In general, leather has a smooth, structured finish and is easy to wipe, while fabric offers more textures and can feel softer. Comfort, upkeep, and wear vary by the exact upholstery. I can compare the EROMA options if you tell me the furniture type and budget."
            elif "velvet" in latest:
                fallback = "Velvet has a soft pile and a rich, light-catching look. It can show pressure marks and needs gentle care: brush with the pile, blot spills, and follow the product care label."
            elif "engineered wood" in latest:
                fallback = "Engineered wood is made by binding wood fibres, particles, or layers into a stable panel. The exact strength and moisture resistance depend on the panel type and finish, so check the product specification and keep it dry unless its care guide says otherwise."
            elif "foam" in latest:
                fallback = "Foam comfort depends on its density, firmness, thickness, and the seat construction around it. For a particular EROMA sofa or chair, check the listed cushion filling; if it is not listed, ask us and we can help confirm it."
            elif "wood" in latest:
                fallback = "Solid wood shows natural grain and can often be refinished, while engineered wood is made from bonded wood layers or particles and can offer consistent panels. Durability depends on the wood or panel type, joinery, finish, and care. Check each EROMA product's listed frame and material details."
            else:
                fallback = "Furniture materials affect feel, appearance, upkeep, and durability. Tell me which piece you are choosing and what matters most—easy cleaning, softness, natural grain, or budget—and I can narrow it down."
        elif care_question and "velvet" in latest:
            fallback = (
                "For velvet, gently brush in the direction of the pile to lift dust. Blot a spill with a clean, dry cloth; avoid rubbing. "
                "Check the sofa's care label before using water or cleaner, and test any approved cleaner on a hidden area first."
            )
        elif care_question and "leather" in latest:
            fallback = (
                "For leather upholstery, dust with a soft dry cloth and wipe small spills promptly. Avoid soaking it or using household cleaners; "
                "follow the care instructions for that sofa and test any approved product on a hidden area first."
            )
        elif care_question and any(word in latest for word in ("fabric", "sofa", "couch", "chair")):
            fallback = (
                "For fabric upholstery, vacuum gently with an upholstery attachment and blot spills rather than rubbing them. "
                "Check the care label before using water or cleaner, since the right method depends on the fabric."
            )
        if any(word in latest for word in ("hello@eroma", "email", "mail", "click")):
            fallback = "Tap hello@eroma.in in my reply to open a prefilled email draft for our support team. Include your order number and item name if your question is about an order."
        product_terms = {
            "sofa": ("sofa", "sofas"), "couch": ("sofa", "sofas"), "chair": ("chair", "chairs"),
            "bed": ("bed", "beds"), "mattress": ("mattress", "bed"), "dining": ("dining",),
            "table": ("table", "tables"), "storage": ("storage", "cabinet"),
            "recliner": ("recliner",), "desk": ("desk", "office"),
        }
        matched_terms = next((terms for word, terms in product_terms.items() if word in latest), ())
        if room_colour_question:
            if re.search(r"\b(lavender|lilac|light purple|pale purple)\b", latest):
                fallback = (
                    "For a light purple room, try an oatmeal or warm ivory sofa or chaise and a light oak bed frame. "
                    "For an upholstered headboard, choose warm ivory or soft beige. Add sage-green cushions or a throw for gentle contrast. "
                    "If you prefer a cooler palette, pair a soft grey lounge with a charcoal headboard."
                )
            else:
                fallback = (
                    "Warm ivory, oatmeal and light oak are good starting points for furniture in a room with coloured walls. "
                    "Use cushions or bedding to echo the wall colour, and compare fabric samples against the wall in daylight. "
                    "What shade are your walls? I can suggest a more specific pairing."
                )
        elif matched_terms and recommendation_intent and not material_comparison and not care_question:
            matches = Product.objects.filter(status="active", stock__gt=0).filter(
                Q(category__name__icontains=matched_terms[0]) | Q(name__icontains=matched_terms[0])
            ).order_by("-featured", "-best_seller", "name")[:3]
            if matches:
                fallback = "Here are a few available options: " + "; ".join(
                    f"{product.name} ({product.price} INR)" for product in matches
                ) + ". Ask me about a style or material to narrow the choice."
        site_context = self._public_site_context()
        if any(term in latest for term in ("store", "showroom", "location", "address")):
            locations = site_context["published_store_locations"]
            if locations:
                fallback = "Published EROMA showroom locations: " + "; ".join(
                    f"{item['city']}, {item['state']}" + (f" — {item['address']}" if item.get("address") else "")
                    for item in locations[:8]
                ) + ". Check the Store Locator for directions and current details."
            else:
                fallback = "I don't have a published showroom address to share yet. Please use the Store Locator or contact hello@eroma.in for location help."
        elif any(term in latest for term in ("coupon", "offer", "discount", "sale")):
            offers = site_context["current_offers"]
            if offers:
                fallback = "Current offers: " + "; ".join(
                    f"{offer['name']}: {offer['description']}" + (f" Use {offer['coupon']}" if offer.get("coupon") else "")
                    for offer in offers[:5]
                ) + ". Check each offer's eligible items and minimum order in the offer details."
            else:
                fallback = "There are no active offer cards listed right now. Check the home page for the latest campaigns."
        elif any(term in latest for term in ("warranty", "return policy", "delivery policy", "cancellation")):
            pages = site_context["help_and_policy_pages"]
            matched_pages = [page for page in pages if any(word in f"{page['key']} {page['title']}".casefold() for word in latest.split())]
            if matched_pages:
                fallback = " ".join(f"{page['title']}: {page['summary']} {page['body'][:700]}" for page in matched_pages[:2]).strip()
            else:
                fallback = "I couldn't find that policy detail in the published help pages. Please open Policies in the footer or contact hello@eroma.in."
        if support_reply:
            fallback = support_reply
        if not settings.GEMINI_API_KEY:
            return Response({"answer": fallback, "source": "store-help"})

        instructions = (
            "You are Eri, EROMA's friendly, lively furniture guide. Answer the customer's actual question directly and naturally, using earlier turns for follow-ups. "
            "Infer obvious typos from context. If a customer asks you to tell or write a 'poet' about furniture, treat it as a request for a poem. "
            "For creative requests about furniture or homes, lead with the requested creative work. Only add shopping advice or specific products if the customer asks for them. "
            "Use plain text and line breaks for formatting, without Markdown emphasis or bullets made of asterisks. "
            "You can explain furniture materials (including leather, fabric, velvet, wood, engineered wood, foam, and upholstery), compare trade-offs, suggest care and cleaning, "
            "help with room planning, measurements, seating, styles, and choosing furniture for a budget. General furniture knowledge is allowed; label it as general guidance "
            "and do not present it as an EROMA product specification. For EROMA products, prices, stock, colors, dimensions, materials, warranty, current offers, coupons, "
            "locations, or policies, use only matching facts in the live website context below. Never invent stock, prices, coupon eligibility, store addresses, delivery promises, "
            "warranty or return terms. If a specific fact is absent, say it is not listed and give the relevant page or hello@eroma.in. "
            "For recommendations, ask a short follow-up only when needed; otherwise suggest relevant in-stock catalog items with prices. For return, refund, exchange, damage, "
            "complaint, or service requests, respond empathetically, ask for the order number and item, and direct the customer to Contact Us or hello@eroma.in. "
            "This chat receives no private account data: never claim to look up a customer's order, profile, PIN result, or saved address. Signed-in customers can use My Orders "
            "for their own order status. Keep answers useful and specific, and avoid repeating fixed fallback advice when the question is specific. All listed prices are INR.\n"
            f"Live public website context: {json.dumps(site_context, ensure_ascii=False, default=str)}\n"
            "If you mention hello@eroma.in, include it exactly so the website can make it clickable."
        )
        payload = {
            "systemInstruction": {"parts": [{"text": instructions}]},
            "contents": [
                {"role": "user" if message["role"] == "user" else "model", "parts": [{"text": message["text"]}]}
                for message in messages
            ],
            "generationConfig": {
                "maxOutputTokens": 700,
                "thinkingConfig": {"thinkingLevel": "low"},
            },
        }
        try:
            generated = None
            model_names = list(dict.fromkeys((settings.GEMINI_MODEL, settings.GEMINI_FALLBACK_MODEL)))
            for model_index, model_name in enumerate(model_names):
                gemini_request = urllib.request.Request(
                    f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent",
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json", "x-goog-api-key": settings.GEMINI_API_KEY},
                    method="POST",
                )
                try:
                    with urllib.request.urlopen(gemini_request, timeout=12) as response:
                        generated = json.loads(response.read().decode("utf-8"))
                    break
                except urllib.error.HTTPError as error:
                    retryable = error.code in (429, 500, 502, 503, 504)
                    if not retryable or model_index == len(model_names) - 1:
                        raise
                    logger.warning("Gemini model %s returned HTTP %s; trying the configured fallback model", model_name, error.code)
                    time.sleep(0.5)
                except (urllib.error.URLError, TimeoutError) as error:
                    if model_index == len(model_names) - 1:
                        raise
                    logger.warning("Gemini model %s is unreachable; trying the configured fallback model (%s)", model_name, type(error).__name__)
                    time.sleep(0.3)
            parts = generated.get("candidates", [{}])[0].get("content", {}).get("parts", [])
            answer = next((part.get("text", "") for part in parts if part.get("text") and not part.get("thought")), "").strip()[:4000]
            return Response({"answer": answer or fallback, "source": "gemini" if answer else "store-help"})
        except urllib.error.HTTPError as error:
            logger.warning("Gemini chat request rejected: HTTP %s %s", error.code, error.reason)
            return Response({"answer": fallback, "source": "store-help"})
        except urllib.error.URLError as error:
            logger.warning("Gemini chat connection failed: %s", error.reason)
            return Response({"answer": fallback, "source": "store-help"})
        except (TimeoutError, ValueError, KeyError, IndexError, TypeError) as error:
            logger.warning("Gemini chat response could not be read: %s", type(error).__name__)
            return Response({"answer": fallback, "source": "store-help"})


def _razorpay_request(method, path, payload=None):
    credentials = base64.b64encode(f"{settings.RAZORPAY_KEY_ID}:{settings.RAZORPAY_KEY_SECRET}".encode()).decode()
    request = urllib.request.Request(
        f"https://api.razorpay.com/v1/{path.lstrip('/')}",
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={"Authorization": f"Basic {credentials}", "Content-Type": "application/json"},
        method=method,
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode())


def _release_razorpay_order(order_id, user):
    from django.db import transaction
    with transaction.atomic():
        try:
            order = Order.objects.select_for_update().get(pk=order_id, user=user, payment_method="razorpay")
        except Order.DoesNotExist:
            return False
        if order.payment_status != "pending":
            return False
        for line in order.items.select_related("product").all():
            Product.objects.filter(pk=line.product_id).update(stock=F("stock") + line.quantity)
        CouponRedemption.objects.filter(order=order).delete()
        order.payment_status = "failed"
        order.status = "cancelled"
        order.save(update_fields=["payment_status", "status"])
        return True


class RazorpayConfigView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        enabled = bool(settings.RAZORPAY_KEY_ID and settings.RAZORPAY_KEY_SECRET)
        return Response({
            "enabled": enabled,
            "key_id": settings.RAZORPAY_KEY_ID if enabled else "",
            "gst_rate": str(settings.ORDER_GST_RATE),
            "free_delivery_threshold": str(settings.ORDER_FREE_DELIVERY_THRESHOLD),
            "standard_delivery_fee": str(settings.ORDER_STANDARD_DELIVERY_FEE),
        })


class RazorpayCreateOrderView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        if not settings.RAZORPAY_KEY_ID or not settings.RAZORPAY_KEY_SECRET:
            return Response({"detail": "Online payment is not configured yet. Please choose Cash on Delivery."}, status=503)
        payload = request.data.copy()
        emi_requested = payload.pop("emi_requested", False) is True
        payload["payment_method"] = "razorpay"
        serializer = CreateOrderSerializer(data=payload, context={"request": request})
        serializer.is_valid(raise_exception=True)
        order = serializer.save()
        order.emi_requested = emi_requested
        if emi_requested:
            order.save(update_fields=["emi_requested"])
        try:
            gateway_order = _razorpay_request("POST", "orders", {
                "amount": int((order.total * 100).quantize(Decimal("1"))),
                "currency": "INR",
                "receipt": f"eroma-{order.id}",
                "notes": {"eroma_order_id": str(order.id)},
            })
            order.razorpay_order_id = gateway_order["id"]
            order.save(update_fields=["razorpay_order_id"])
        except (urllib.error.URLError, TimeoutError, ValueError, KeyError):
            _release_razorpay_order(order.id, request.user)
            return Response({"detail": "Razorpay could not start the payment. Your stock and coupon have been released; please retry."}, status=502)
        return Response({"order_id": order.id, "razorpay_order_id": order.razorpay_order_id,
                         "amount": gateway_order["amount"], "currency": gateway_order["currency"],
                         "key_id": settings.RAZORPAY_KEY_ID, "name": "EROMA", "description": "EROMA furniture order",
                         "prefill": {"name": order.full_name, "email": order.email, "contact": order.phone}})


class RazorpayVerifyView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        order_id = request.data.get("order_id")
        payment_id = str(request.data.get("razorpay_payment_id", ""))
        gateway_order_id = str(request.data.get("razorpay_order_id", ""))
        signature = str(request.data.get("razorpay_signature", ""))
        try:
            order = Order.objects.get(pk=order_id, user=request.user, payment_method="razorpay")
        except (Order.DoesNotExist, ValueError, TypeError):
            return Response({"detail": "Order not found."}, status=404)
        if order.payment_status == "paid" and order.razorpay_payment_id == payment_id:
            return Response(OrderSerializer(order).data)
        if order.payment_status != "pending" or not order.razorpay_order_id or gateway_order_id != order.razorpay_order_id:
            return Response({"detail": "This Razorpay order is not awaiting payment."}, status=400)
        expected = hmac.new(settings.RAZORPAY_KEY_SECRET.encode(), f"{order.razorpay_order_id}|{payment_id}".encode(), hashlib.sha256).hexdigest()
        if not payment_id or not hmac.compare_digest(expected, signature):
            return Response({"detail": "Razorpay payment signature could not be verified."}, status=400)
        try:
            payment = _razorpay_request("GET", f"payments/{payment_id}")
            expected_amount = int((order.total * 100).quantize(Decimal("1")))
            if (payment.get("order_id") != order.razorpay_order_id or payment.get("amount") != expected_amount
                    or payment.get("currency") != "INR"):
                return Response({"detail": "Razorpay payment details do not match this order."}, status=400)
            if order.emi_requested and payment.get("method") != "emi":
                return Response({"detail": "No EMI payment was confirmed. Choose EMI in Razorpay Checkout, or retry with a card payment."}, status=400)
            if payment.get("status") == "authorized":
                payment = _razorpay_request("POST", f"payments/{payment_id}/capture", {"amount": expected_amount, "currency": "INR"})
        except (urllib.error.URLError, TimeoutError, ValueError):
            return Response({"detail": "Payment was received, but its status could not be confirmed. Please contact support before retrying."}, status=503)
        if (payment.get("order_id") != order.razorpay_order_id or payment.get("amount") != expected_amount
                or payment.get("currency") != "INR" or payment.get("status") != "captured"):
            return Response({"detail": "Razorpay has not confirmed a captured payment for this order."}, status=400)
        order.payment_status = "paid"
        order.razorpay_payment_id = payment_id
        order.payment_instrument = str(payment.get("method", ""))[:20]
        order.save(update_fields=["payment_status", "razorpay_payment_id", "payment_instrument"])
        return Response(OrderSerializer(order).data)


class RazorpayCancelView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            order = Order.objects.get(pk=request.data.get("order_id"), user=request.user, payment_method="razorpay")
        except (Order.DoesNotExist, ValueError, TypeError):
            return Response({"cancelled": False})
        if order.razorpay_order_id and settings.RAZORPAY_KEY_ID and settings.RAZORPAY_KEY_SECRET:
            try:
                gateway_order = _razorpay_request("GET", f"orders/{order.razorpay_order_id}")
                if gateway_order.get("status") == "paid":
                    return Response({"cancelled": False, "detail": "Razorpay has already recorded a payment for this order."})
            except (urllib.error.URLError, TimeoutError, ValueError):
                return Response({"cancelled": False, "detail": "Payment status could not be checked; the order is kept pending."}, status=503)
        if _release_razorpay_order(order.id, request.user):
            return Response({"cancelled": True})
        return Response({"cancelled": False})

class OrderViewSet(viewsets.ModelViewSet):
    serializer_class = OrderSerializer
    http_method_names = ["get", "post", "patch", "head", "options"]
    def get_permissions(self):
        if self.request.user and self.request.user.is_staff:
            return [permissions.IsAuthenticated()]
        if self.request.method == "POST":
            return [permissions.IsAuthenticated()]
        return [permissions.IsAuthenticated()]
    def get_queryset(self):
        qs = Order.objects.prefetch_related("items").order_by("-created_at")
        return qs if self.request.user.is_staff else qs.filter(user=self.request.user)
    def create(self, request, *args, **kwargs):
        if request.data.get("payment_method") == "razorpay":
            return Response({"detail": "Start Razorpay payments through the secure Razorpay checkout endpoint."}, status=400)
        serializer = CreateOrderSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        order = serializer.save()
        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)
    def partial_update(self, request, *args, **kwargs):
        if not request.user.is_staff: return Response({"detail":"Staff only."}, status=403)
        order = self.get_object()
        new_status = request.data.get("status")
        if new_status not in dict(Order.STATUS_CHOICES):
            return Response({"detail":"Invalid status."}, status=400)
        order.status = new_status
        order.save(update_fields=["status"])
        return Response(OrderSerializer(order).data)


class OrderTrackingLookupView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "order_tracking_lookup"

    def get(self, request):
        code = str(request.query_params.get("code", "")).strip().upper()
        if len(code) < 12 or len(code) > 32:
            return Response({"detail": "Enter the tracking number from your order confirmation."}, status=400)
        try:
            order = Order.objects.prefetch_related("items").get(tracking_code__iexact=code)
        except Order.DoesNotExist:
            return Response({"detail": "We couldn’t find an order with that tracking number. Check it and try again."}, status=404)
        data = OrderSerializer(order).data
        # Only expose the shipment details needed to follow the parcel.
        return Response({
            "order_number": order.pk,
            "tracking_code": order.tracking_code,
            "created_at": data["created_at"],
            "status": data["tracking_status"],
            "tracking_demo": data["tracking_demo"],
            "items": data["items"],
        })


class ContactMessageView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "contact_message"

    def post(self, request):
        name = str(request.data.get("name", "")).strip()[:120]
        email = str(request.data.get("email", "")).strip()[:254]
        phone = str(request.data.get("phone", "")).strip()
        if phone and not PHONE_PATTERN.fullmatch(phone):
            return Response({"detail": PHONE_ERROR}, status=status.HTTP_400_BAD_REQUEST)
        message = str(request.data.get("message", "")).strip()[:4000]
        if not name or not email or len(message) < 10:
            return Response({"detail": "Please provide your name, email, and a message of at least 10 characters."}, status=400)
        try:
            from django.core.validators import validate_email
            validate_email(email)
        except Exception:
            return Response({"detail": "Enter a valid email address."}, status=400)
        enquiry = ContactMessage.objects.create(name=name, email=email, phone=phone, message=message)
        body = f"Name: {name}\nEmail: {email}\nPhone: {phone or 'Not provided'}\n\nMessage:\n{message}"
        try:
            EmailMessage(
                subject=f"EROMA website enquiry from {name}",
                body=body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=["hello@eroma.in"],
                reply_to=[email],
            ).send(fail_silently=False)
            enquiry.notification_sent = True
            enquiry.save(update_fields=("notification_sent",))
        except Exception:
            logger.exception("Unable to deliver EROMA contact enquiry")
        return Response({
            "detail": "Thanks for contacting EROMA. Your enquiry has been saved for our support team."
            if not enquiry.notification_sent else "Thanks for contacting EROMA. Your enquiry has been sent to our support team."
        }, status=201)


class CallbackRequestView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "contact_message"

    def post(self, request):
        name = str(request.data.get("name", "")).strip()[:120]
        email = str(request.data.get("email", "")).strip()[:254]
        phone = str(request.data.get("phone", "")).strip()
        postal_code = str(request.data.get("postal_code", "")).strip()
        city = str(request.data.get("city", "")).strip()[:100]
        message = str(request.data.get("message", "")).strip()[:2000]

        if not all((name, email, phone, postal_code)) or len(message) < 5:
            return Response(
                {"detail": "Please provide your name, email, phone number, PIN code, and a short message."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            from django.core.validators import validate_email
            validate_email(email)
        except Exception:
            return Response({"detail": "Enter a valid email address."}, status=status.HTTP_400_BAD_REQUEST)
        if not PHONE_PATTERN.fullmatch(phone):
            return Response({"detail": PHONE_ERROR}, status=status.HTTP_400_BAD_REQUEST)
        if not PIN_PATTERN.fullmatch(postal_code):
            return Response({"detail": PIN_ERROR}, status=status.HTTP_400_BAD_REQUEST)

        callback = CallbackRequest.objects.create(
            name=name,
            email=email,
            phone=phone,
            postal_code=postal_code,
            city=city,
            message=message,
        )
        try:
            EmailMessage(
                subject=f"EROMA callback request #{callback.pk} from {name}",
                body=(
                    f"Name: {name}\nEmail: {email}\nPhone: {phone}\n"
                    f"PIN code: {postal_code}\nCity: {city or 'Not provided'}\n\n"
                    f"Message:\n{message}"
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=["hello@eroma.in"],
                reply_to=[email],
            ).send(fail_silently=False)
        except Exception:
            logger.exception("Callback request %s was saved but its notification email failed", callback.pk)

        return Response(
            {"detail": "Thanks. Your callback request has been received. EROMA support will contact you using the phone number provided."},
            status=status.HTTP_201_CREATED,
        )

class MeView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    def get(self, request):
        return Response({"id": request.user.id, "username": request.user.username,
                         "email": request.user.email, "is_staff": request.user.is_staff})


class ProfileView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        data = UserProfileSerializer(request.user).data
        data["phone"] = profile.phone
        return Response(data)

    def patch(self, request):
        serializer = UserProfileSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        profile, _ = UserProfile.objects.get_or_create(user=user)
        data = UserProfileSerializer(user).data
        data["phone"] = profile.phone
        return Response(data)


class AddressViewSet(viewsets.ModelViewSet):
    serializer_class = AddressSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Address.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class WishlistViewSet(viewsets.ModelViewSet):
    serializer_class = WishlistItemSerializer
    permission_classes = [permissions.IsAuthenticated]
    http_method_names = ["get", "post", "delete", "head", "options"]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["collective_product_rating"] = collective_product_rating()
        return context

    def get_queryset(self):
        products = Product.objects.select_related("category").prefetch_related("images").annotate(
            average_rating=Avg("reviews__rating", filter=Q(reviews__is_approved=True) & ~Q(reviews__customer_name__endswith=" (Sample)")),
            review_count=Count("reviews", filter=Q(reviews__is_approved=True) & ~Q(reviews__customer_name__endswith=" (Sample)")),
        )
        return WishlistItem.objects.filter(user=self.request.user).prefetch_related(
            Prefetch("product", queryset=products)
        )

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class ProductReviewViewSet(viewsets.ModelViewSet):
    serializer_class = ProductReviewSerializer
    http_method_names = ["get", "post", "head", "options"]

    def get_permissions(self):
        if getattr(self, "action", None) == "eligibility":
            return [permissions.IsAuthenticated()]
        if self.request.method in permissions.SAFE_METHODS:
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        reviews = ProductReview.objects.select_related("product", "customer")
        if not self.request.user.is_staff:
            reviews = reviews.filter(is_approved=True)
        product_id = self.request.query_params.get("product")
        return reviews.filter(product_id=product_id) if product_id else reviews.filter(is_approved=True)[:8]

    @action(detail=False, methods=["get"], permission_classes=[permissions.IsAuthenticated], url_path="eligibility")
    def eligibility(self, request):
        from rest_framework.exceptions import ValidationError

        try:
            product_id = int(request.query_params.get("product", ""))
            product = Product.objects.get(pk=product_id, status="active")
        except (ValueError, TypeError, Product.DoesNotExist):
            raise ValidationError({"detail": "Choose a valid product to check review eligibility."})
        purchased = OrderItem.objects.filter(
            order__user=request.user,
            product=product,
        ).exclude(order__status="cancelled").filter(
            Q(order__payment_status="paid") | Q(order__status="delivered")
        ).exists()
        already_reviewed = ProductReview.objects.filter(product=product, customer=request.user).exists()
        return Response({"purchased": purchased, "already_reviewed": already_reviewed})

    def perform_create(self, serializer):
        product = serializer.validated_data["product"]
        user = self.request.user
        if not OrderItem.objects.filter(order__user=user, product=product).exclude(
            order__status="cancelled"
        ).filter(Q(order__payment_status="paid") | Q(order__status="delivered")).exists():
            from rest_framework.exceptions import ValidationError
            raise ValidationError({"detail": "Only customers who purchased this item can review it."})
        if ProductReview.objects.filter(product=product, customer=user).exists():
            from rest_framework.exceptions import ValidationError
            raise ValidationError({"detail": "You have already reviewed this item."})
        name = user.get_full_name() or user.username
        serializer.save(customer=user, customer_name=name, is_approved=False)


class CouponValidationView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        code = str(request.data.get("code", "")).strip().upper()
        lines = OrderLineInputSerializer(data=request.data.get("items", []), many=True)
        lines.is_valid(raise_exception=True)
        if not code or not lines.validated_data:
            return Response({"detail": "Enter a coupon and add products to your bag."}, status=400)
        products = {p.id: p for p in Product.objects.filter(
            id__in=[line["product_id"] for line in lines.validated_data], status="active"
        )}
        quantities = Counter()
        for line in lines.validated_data:
            quantities[line["product_id"]] += line["quantity"]
        subtotal = 0
        for product_id, quantity in quantities.items():
            product = products.get(product_id)
            if not product or product.stock < quantity:
                return Response({"detail": "A product is unavailable or no longer has enough stock."}, status=400)
            subtotal += product.price * quantity
        try:
            coupon = Coupon.objects.get(code=code, is_active=True)
        except Coupon.DoesNotExist:
            return Response({"detail": "This coupon is invalid or inactive."}, status=400)
        applicable_category_ids = coupon_category_ids(coupon)
        if applicable_category_ids:
            eligible_subtotal = sum(
                products[line["product_id"]].price * line["quantity"]
                for line in lines.validated_data
                if line["product_id"] in products and products[line["product_id"]].category_id in applicable_category_ids
            )
            if not eligible_subtotal:
                return Response({"detail": "This coupon only applies to selected furniture categories."}, status=400)
            subtotal = eligible_subtotal
        now = timezone.now()
        if (coupon.starts_at and coupon.starts_at > now) or (coupon.ends_at and coupon.ends_at < now):
            return Response({"detail": "This coupon is outside its valid dates."}, status=400)
        if subtotal < coupon.minimum_order:
            return Response({"detail": f"Minimum order is ₹{coupon.minimum_order}."}, status=400)
        if coupon.usage_limit is not None and coupon.redemptions.count() >= coupon.usage_limit:
            return Response({"detail": "This coupon has reached its usage limit."}, status=400)
        from decimal import Decimal
        discount = subtotal * coupon.discount_value / Decimal("100") if coupon.discount_type == "percent" else coupon.discount_value
        discount = min(discount, subtotal)
        return Response({"code": coupon.code, "subtotal": subtotal, "discount": discount, "total": subtotal-discount})


class AvailableCouponsView(APIView):
    """Expose currently usable storefront coupons for the order summary."""
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        now = timezone.now()
        coupons = Coupon.objects.filter(is_active=True).filter(
            Q(starts_at__isnull=True) | Q(starts_at__lte=now),
            Q(ends_at__isnull=True) | Q(ends_at__gte=now),
        ).annotate(redemption_count=Count("redemptions")).prefetch_related("categories").order_by("-created_at")
        result = []
        for coupon in coupons:
            if coupon.usage_limit is not None and coupon.redemption_count >= coupon.usage_limit:
                continue
            result.append({
                "code": coupon.code,
                "description": coupon.description,
                "discount_value": coupon.discount_value,
                "discount_type": coupon.discount_type,
                "minimum_order": coupon.minimum_order,
                "categories": list(coupon.categories.values_list("id", flat=True)),
            })
        return Response(result)


class AdminStatsView(APIView):
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        return Response({
            "products": Product.objects.count(),
            "users": get_user_model().objects.filter(is_staff=False).count(),
            "orders": Order.objects.count(),
            "pending_orders": Order.objects.filter(status="placed").count(),
            "sales": Order.objects.exclude(status="cancelled").aggregate(total=Sum("total"))["total"] or 0,
            "low_stock": Product.objects.filter(stock__lte=5, status="active").count(),
        })


class PasswordResetRequestView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "password_reset"

    def post(self, request):
        email = str(request.data.get("email", "")).strip()
        users = get_user_model().objects.filter(email__iexact=email, is_active=True)
        reset_link = None
        for user in users:
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            frontend = getattr(settings, "FRONTEND_URL", "http://localhost:5173").rstrip("/")
            reset_link = f"{frontend}/?reset={uid}.{token}"
            try:
                send_mail("Reset your EROMA password", f"Use this link to reset your password: {reset_link}",
                          getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@eroma.in"), [user.email], fail_silently=False)
            except Exception:
                logger.exception("Unable to send password reset email")
                return Response({"detail": "The password reset email service is unavailable right now. Please try again later or contact support."}, status=503)
        response = {"detail": "If an account matches that email, password reset instructions have been sent."}
        if settings.DEBUG and reset_link:
            response["development_reset_link"] = reset_link
        return Response(response)


class PasswordResetConfirmView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "password_reset_confirm"

    def post(self, request):
        uid = request.data.get("uid", "")
        token = request.data.get("token", "")
        password = request.data.get("new_password", "")
        try:
            user_id = force_str(urlsafe_base64_decode(uid))
            user = get_user_model().objects.get(pk=user_id, is_active=True)
        except (TypeError, ValueError, OverflowError, get_user_model().DoesNotExist):
            return Response({"detail": "This reset link is invalid or expired."}, status=400)
        if not default_token_generator.check_token(user, token):
            return Response({"detail": "This reset link is invalid or expired."}, status=400)
        try:
            validate_password(password, user)
        except Exception as error:
            from django.core.exceptions import ValidationError
            if isinstance(error, ValidationError):
                return Response({"new_password": list(error.messages)}, status=400)
            raise
        user.set_password(password)
        user.save(update_fields=("password",))
        return Response({"detail": "Password updated. You can now sign in."})
