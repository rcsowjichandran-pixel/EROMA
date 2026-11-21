from rest_framework.routers import DefaultRouter
from django.urls import path, include
from .views import ProductViewSet, CategoryViewSet, HomepageBannerViewSet, OrderViewSet, OrderTrackingLookupView, ContactMessageView, MeView, ProfileView, AddressViewSet, WishlistViewSet, ProductReviewViewSet, CouponValidationView, AvailableCouponsView, AdminStatsView, ProductRecommendationView, StoreLocationViewSet, OfferBannerViewSet, FooterPageContentViewSet, StoreChatView, RazorpayConfigView, RazorpayCreateOrderView, RazorpayVerifyView, RazorpayCancelView, SiteBrandingView
router = DefaultRouter()
router.register("products", ProductViewSet, basename="product")
router.register("categories", CategoryViewSet)
router.register("banners", HomepageBannerViewSet, basename="banner")
router.register("stores", StoreLocationViewSet, basename="store-location")
router.register("offers", OfferBannerViewSet, basename="offer-banner")
router.register("footer-content", FooterPageContentViewSet, basename="footer-content")
router.register("orders", OrderViewSet, basename="order")
router.register("addresses", AddressViewSet, basename="address")
router.register("wishlist", WishlistViewSet, basename="wishlist")
router.register("reviews", ProductReviewViewSet, basename="review")
urlpatterns = [
    path("orders/track/", OrderTrackingLookupView.as_view()),
    path("contact/", ContactMessageView.as_view()),
    path("branding/", SiteBrandingView.as_view()),
    path("", include(router.urls)),
    path("me/", MeView.as_view()),
    path("profile/", ProfileView.as_view()),
    path("coupons/validate/", CouponValidationView.as_view()),
    path("coupons/available/", AvailableCouponsView.as_view()),
    path("admin/stats/", AdminStatsView.as_view()),
    path("recommendations/", ProductRecommendationView.as_view()),
    path("assistant/chat/", StoreChatView.as_view()),
    path("payments/razorpay/config/", RazorpayConfigView.as_view()),
    path("payments/razorpay/create-order/", RazorpayCreateOrderView.as_view()),
    path("payments/razorpay/verify/", RazorpayVerifyView.as_view()),
    path("payments/razorpay/cancel/", RazorpayCancelView.as_view()),
]
