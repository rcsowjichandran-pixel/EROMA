# EROMA — Furniture E-commerce (Full-stack application)

Stack: React + Vite + Django REST Framework + SQLite for local development / PostgreSQL in deployment.

Included:
- Product catalogue with categories, search, sorting, product detail, stock visibility, and staff product management
- Customer registration, JWT login, logout, forgot/reset password
- Browser cart with quantity controls, stock validation, and database-backed checkout
- Cash on Delivery and Razorpay Checkout integration (test credentials for non-production payments)
- Order history, tracking codes, staff order status updates, and atomic stock deduction
- Database-backed wishlist, user profile, saved delivery addresses, coupon validation/redemption
- Verified-buyer product reviews with staff moderation in Django admin
- Admin dashboard statistics for sales, orders, customers, products, and low-stock items
- Category, product, inventory, coupon, user, order, review, and media management in Django admin
- Responsive dark storefront with homepage hero and category carousels

Payment note: Razorpay Checkout is integrated and verifies payment details server-side. Use Razorpay test keys for project demonstrations. The simulated test-card method is development-only and never collects or processes card data. Configure live keys and payment webhooks before accepting production payments.

Password reset shows a one-time reset link in local development. On Render Free, configure `RESEND_API_KEY`, `DEFAULT_FROM_EMAIL`, and `FRONTEND_URL` on the backend for HTTPS email delivery. See the [email setup instructions](docs/DEPLOYMENT_AND_HANDOFF.md#email) for Resend and SMTP configuration.

## Requirements
- Python 3.11+
- Node.js 20.19 or later in the 20.x series, or Node.js 22.12 or later
- PostgreSQL 15+ (optional for first local run; SQLite is used if DATABASE_URL is not set)

## Backend — Windows PowerShell
Open PowerShell in the `sofalux` folder:

```powershell
cd backend
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

If PowerShell blocks activation, run:
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

Backend: http://127.0.0.1:8000
Django admin: http://127.0.0.1:8000/admin/

## Frontend — second PowerShell window
```powershell
cd sofalux\frontend
npm ci
Copy-Item .env.example .env
npm run dev
```
Frontend: http://localhost:5173

## PostgreSQL setup
Create a PostgreSQL database and user, then edit `backend/.env`:
```env
DATABASE_URL=postgresql://sofalux_user:YOUR_PASSWORD@localhost:5432/sofalux_db
```
Install PostgreSQL and ensure its service is running. Then run:
```powershell
cd backend
.\.venv\Scripts\Activate.ps1
python manage.py migrate
```
Never commit `.env` or expose `SECRET_KEY` / database credentials.

## Add sample products
Use Django admin at `/admin/` and add categories/products. Upload product and category photos through the staff tools or Django admin. Files are stored under `backend/media/` locally. Configure durable object storage for deployment.

## Admin access
Create a superuser using `python manage.py createsuperuser`. Staff can open Admin Studio from their storefront account menu, or sign in to Django admin. Django admin provides product, category, stock, order, user, review, coupon, and content management. Admin Studio provides dashboard metrics, product creation, and product photo uploads. Protect staff accounts carefully.

## API endpoints
- `POST /api/auth/register/`
- `POST /api/auth/token/`
- `POST /api/auth/token/refresh/`
- `GET /api/products/` (supports `?search=` and `?category=`)
- `GET /api/products/<id>/`
- `POST /api/orders/` (authenticated)
- `GET /api/orders/` (authenticated; staff sees all)
- `GET/PATCH /api/profile/` (authenticated)
- `GET/POST/PATCH/DELETE /api/addresses/` (authenticated)
- `GET/POST/DELETE /api/wishlist/` (authenticated)
- `GET/POST /api/reviews/` (verified buyers can submit; staff moderates)
- `POST /api/coupons/validate/` (public quote; order placement requires authentication)
- `GET /api/admin/stats/` (staff only)
- `POST /api/auth/password-reset/` and `/api/auth/password-reset/confirm/`
- `POST /api/products/` (staff only)
- `PATCH /api/products/<id>/` (staff only)
- `DELETE /api/products/<id>/` (staff only)
- Django admin: `/admin/`

Contact enquiries and callback requests are stored in Django admin. Password-reset email delivery still requires an email provider in the backend environment. In local development, reset links are returned in the API response.

New admin uploads can use an S3-compatible media bucket by configuring the `AWS_*` variables in `backend/.env` or the backend service environment. Without that configuration, local media is stored on the application filesystem and is not durable across typical Render redeploys.

Shipping fees and included-GST calculations are configurable in the backend environment (`ORDER_STANDARD_DELIVERY_FEE`, `ORDER_FREE_DELIVERY_THRESHOLD`, and `ORDER_GST_RATE`). Order tracking reports stored order statuses; it is not connected to a courier's live tracking feed.

Before production, configure live payment credentials and signed webhooks, an email provider, durable media storage, a strong `SECRET_KEY`, and backups. See [deployment, testing, and data handoff](docs/DEPLOYMENT_AND_HANDOFF.md). Run `python manage.py test`, `npm test`, and `npm run build` before release.
