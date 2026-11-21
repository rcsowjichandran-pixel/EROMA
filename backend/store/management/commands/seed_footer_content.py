from django.core.management.base import BaseCommand
from django.utils.text import slugify

from store.models import FooterPageContent


PAGES = {
    "Blogs": ("Ideas for living", "Thoughtful ideas for more comfortable, personal spaces.", "Explore room inspiration, furniture styling ideas, and practical tips for making the most of your home. Our journal is here to help you find a look that feels like you.", "home-decor-lighting.jpg"),
    "Media": ("Media & press", "For press, editorial, and brand enquiries.", "For interviews, product information, or editorial requests, write to hello@eroma.in with your publication, deadline, and the details you need. Our team will direct your request to the right person.", "sofas.jpg"),
    "Careers": ("Careers at EROMA", "Help us make everyday spaces feel more like home.", "We welcome people who care about thoughtful design, useful service, and creating a warm experience for customers. Share your profile and the kind of role you are looking for at hello@eroma.in.", "office-furniture.jpg"),
    "Become a Franchisee": ("Become an EROMA franchisee", "Bring considered furniture and warm service to your city.", "Tell us about your city, retail experience, and the kind of showroom you hope to build. Our partnerships team can share the next steps and current requirements.", "sofas.jpg"),
    "Rent Your Property": ("Partner with us", "Have a space that could become an EROMA showroom?", "Share the city, neighbourhood, approximate area, and a few details about your property. Our team will review the information and get in touch if it suits our showroom plans.", "storage-furniture.jpg"),
    "Sell with EROMA": ("Product partnerships", "Introduce us to your furniture or home living collection.", "Send a short introduction to your business, product range, materials, and supply capabilities. Our team will review your details and contact you about a suitable partnership opportunity.", "dining-furniture.jpg"),
    "Bulk Enquiry": ("Furnish a larger space", "Furniture support for homes, offices, and projects.", "Tell us what spaces you are furnishing, the product categories you need, quantities, delivery city, and preferred timeline. We will help you explore suitable EROMA pieces and next steps.", "dining-tables.jpg"),
    "Dismantling": ("Furniture dismantling", "Need help preparing furniture for a move or room change?", "Share your order number, product name, location, and a suitable time. Our team will confirm the available service options and any applicable charges before arranging assistance.", "storage-furniture.jpg"),
    "Re-installation": ("Furniture re-installation", "Get help setting your furniture up again.", "Contact us with your order number, product details, and delivery PIN code. We will check service availability and confirm the appointment details with you.", "beds-bedroom.jpg"),
    "Loose Fitting": ("Furniture fitting support", "We can help with a fitting or assembly concern.", "Please include your order number, a short description of the issue, and a clear photo if possible. Our support team will help identify the right next step.", "study-tables.jpg"),
    "Complaints": ("We are here to help", "Tell us what happened and we will look into it.", "Share your order number, contact details, and a clear description of the concern. We will review the information and get back to you with an update.", "sofas.jpg"),
    "My Account": ("Your EROMA account", "Keep your profile, saved pieces, and orders in one place.", "Sign in to manage your details, revisit your wishlist, and check the progress of your orders. If you need help accessing your account, contact our support team.", "home-decor-lighting.jpg"),
    "Track Order": ("Track your order", "Follow your order from confirmation to delivery.", "Sign in using the account used at checkout, then open My Orders and choose Track Order. You can see the current preparation and delivery stage there.", "storage-furniture.jpg"),
    "Contact Us": ("Contact EROMA", "Questions about a product, order, or service? We are ready to help.", "Start a chat with our EROMA assistant, or email hello@eroma.in. For order support, include the order number and the phone number used at checkout so we can guide you faster.", "sofas.jpg"),
    "Policies": ("Customer policies", "Helpful information for shopping with EROMA.", "Delivery coverage, service availability, returns, and promotions may depend on the product and delivery area. Check the details shown at checkout and contact us if you need help understanding a policy for your order.", "home-decor-lighting.jpg"),
    "Privacy Policy": ("Privacy at EROMA", "We use your details to support your shopping experience.", "Account, delivery, and order information is used to operate the store, fulfil purchases, and provide customer support. Contact hello@eroma.in for privacy questions or requests relating to your information.", "office-furniture.jpg"),
    "Terms & Conditions": ("Terms & conditions", "A clear guide to orders and offers.", "Product availability, delivery estimates, service options, and promotions can vary. Any offer is subject to its displayed dates, eligible products, minimum order value, and coupon conditions. Contact our team if you need help with a specific order.", "dining-furniture.jpg"),
    "Free Delivery": ("Delivery information", "Check the delivery area for your PIN code before ordering.", "Enter your six-digit PIN code in the delivery checker at the top of the page. Delivery availability and any charges are confirmed for the selected product and address during checkout.", "storage-furniture.jpg"),
    "Easy Returns": ("Returns & exchanges", "We can guide you through a return or exchange request.", "Contact support with your order number and the item you need help with. Our team will explain the applicable return or exchange terms and help you with the next step.", "sofas.jpg"),
    "Secure Payment": ("Secure payment", "Choose the payment option that works for you.", "Online payments are completed through Razorpay Checkout. Orders are marked paid only after payment verification. Cash on Delivery is available when shown as an option at checkout.", "home-decor-lighting.jpg"),
    "Dining Table Size Guide": ("Dining table size guide", "Make room for meals and comfortable movement.", "Measure the table area and allow space to pull chairs out and walk around them. Compare the room dimensions with the size listed on each product page, and check doorways for delivery access.", "dining-tables.jpg"),
    "Mattress Size Guide": ("Mattress size guide", "Match your mattress to the inside of your bed frame.", "Measure the interior width and length of the bed frame, not the outside edges. Compare those measurements with the mattress listing and leave enough room for bedding and fitted sheets.", "beds-bedroom.jpg"),
    "Bed Size Guide": ("Bed size guide", "Plan for the bed, bedside space, and room to move.", "Measure the bedroom, access route, and doorway before choosing a bed. Check the product dimensions and allow clearance around the frame for drawers, doors, and walking space.", "beds-bedroom.jpg"),
    "Sofa Size Guide": ("Sofa size guide", "Choose a sofa that fits your room and your route in.", "Measure the available wall and floor space, then check the sofa width, depth, and height. Measure doorways, stair turns, and lifts too, so the piece can reach its intended room.", "sofas.jpg"),
    "Study Table Size Guide": ("Study table size guide", "Create a comfortable space to focus.", "Measure the desk area and allow enough room for a chair to move back. Compare the table height and width with your chair, monitor, and storage needs.", "study-tables.jpg"),
    "Living Room Decor Guide": ("Living room decor guide", "Bring the room together with considered finishing touches.", "Start with the room's colours, natural light, and available surface space. Layer a few useful accents such as lighting, mirrors, and decor, keeping the scale balanced with your furniture.", "home-decor-lighting.jpg"),
}


class Command(BaseCommand):
    help = "Create editable EROMA footer pages with starter copy and local imagery."

    def handle(self, *args, **options):
        created = 0
        for title, (eyebrow, summary, body, image_name) in PAGES.items():
            _, was_created = FooterPageContent.objects.get_or_create(
                key=slugify(title),
                defaults={
                    "title": title,
                    "eyebrow": eyebrow,
                    "summary": summary,
                    "body": body,
                    "image": f"footer_pages/defaults/{image_name}",
                    "image_alt_text": f"EROMA furniture inspiration for {title.lower()}",
                    "action_label": "Talk to EROMA",
                    "action_url": "support",
                    "is_active": True,
                },
            )
            created += int(was_created)
        self.stdout.write(self.style.SUCCESS(f"Footer content ready: {created} pages created, {len(PAGES)} pages available for editing."))
