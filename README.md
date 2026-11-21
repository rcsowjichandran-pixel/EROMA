# SOFALUX — Sofa E-commerce (Full-stack MVP)

Stack: React + Vite + Django REST Framework + SQLite for local development / PostgreSQL-ready configuration.

Included:
- Product catalogue with categories, search, sorting, product detail, stock visibility, and staff product management
- Customer registration, JWT login, logout, forgot/reset password
- Browser cart with quantity controls, stock validation, and database-backed checkout
- Cash on Delivery orders; development-only simulated card payment (not a real gateway)
- Order history, tracking codes, staff order status updates, and atomic stock deduction
- Database-backed wishlist, user profile, saved delivery addresses, coupon validation/redemption
- Verified-buyer product reviews with staff moderation in Django admin
- Admin dashboard statistics for sales, orders, customers, products, and low-stock items
- Category, product, inventory, coupon, user, order, review, and media management in Django admin
- Responsive dark storefront with homepage hero and category carousels

Payment note: no payment provider is configured. The optional test-card flow is a development simulation that immediately marks a successful simulated payment; it never collects or processes real card data. Configure a provider and verified webhooks before accepting online payments.

Password reset shows a one-time reset link in local development. For deployed email delivery, set `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, TLS settings, `DEFAULT_FROM_EMAIL`, and `FRONTEND_URL` in the backend environment.

## Requirements
- Python 3.11+
- Node.js 20+
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
npm install
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
Create a superuser using `python manage.py createsuperuser`. Staff/superusers can access Django admin and the React `/admin` screen. The React admin screen supports product creation and listing. Protect staff accounts carefully.

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
- `POST /api/coupons/validate/` (authenticated)
- `GET /api/admin/stats/` (staff only)
- `POST /api/auth/password-reset/` and `/api/auth/password-reset/confirm/`
- `POST /api/products/` (staff only)
- `PATCH /api/products/<id>/` (staff only)
- `DELETE /api/products/<id>/` (staff only)
- Django admin: `/admin/`

This is a learning/development MVP. Before production, configure a real email service, payment provider and signed webhooks, shipping/tax rules, durable private media storage, rate limiting, monitoring, backups, and deployment HTTPS/security settings. Run `python manage.py test` and `npm run build` before release.
