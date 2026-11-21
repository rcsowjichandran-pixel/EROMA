# Deployment, testing, and data handoff

## Checks

Run from the project root:

```powershell
cd backend
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe manage.py test
cd ..\frontend
npm test
npm run build
```

`manage.py check --deploy` also checks production security settings. The project enables HTTPS redirect, HSTS, and secure cookies by default when `DEBUG=False`. Set a unique `SECRET_KEY` of at least 50 random characters in the backend service environment. Do not copy it into source control or a `VITE_` variable.

## Render environment

Set secrets on the **EROMA Python backend service**, not the frontend service. Keep `DATABASE_URL`, `SECRET_KEY`, Gemini and Razorpay secrets, SMTP credentials, and object-storage credentials in Render's backend Environment settings. The frontend needs only `VITE_API_URL`, set to the public backend API base ending in `/api`.

Production security settings can be explicitly overridden with `SECURE_SSL_REDIRECT`, `SECURE_HSTS_SECONDS`, `SESSION_COOKIE_SECURE`, and `CSRF_COOKIE_SECURE`. On Render, leave HTTPS redirect enabled and use the Render proxy's forwarded protocol header. HSTS subdomain and preload options are intentionally not enabled automatically; enable those only after confirming every affected hostname will remain HTTPS-only.

## Email

For local development, `EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend` prints reset messages to the Django terminal. With `DEBUG=True`, the password-reset endpoint also returns a development-only reset URL.

For deployed password-reset emails, configure these on the backend service:

- `EMAIL_HOST`, `EMAIL_PORT`
- `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`
- `EMAIL_USE_TLS` or `EMAIL_USE_SSL`
- `DEFAULT_FROM_EMAIL`, `FRONTEND_URL`

Contact Us messages and callback requests are saved in Django admin even if email notification fails. Check the message's `notification_sent` field to see whether email delivery also succeeded. Password resets still require a functioning email provider outside local development.

## Durable uploaded product images

Committed catalogue images are deployed with the frontend/backend source assets. New images uploaded through Django admin need durable media storage. The project can route Django file uploads to an S3-compatible bucket using `django-storages`.

Set the following on the backend service to enable it:

- `AWS_STORAGE_BUCKET_NAME`
- `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`
- `AWS_S3_REGION_NAME`
- `AWS_S3_ENDPOINT_URL` for S3-compatible services that need a custom endpoint
- `AWS_S3_CUSTOM_DOMAIN` if the bucket is served through a CDN or public media hostname

The bucket must allow public reads for the furniture images displayed on product pages. Keep write credentials private and grant them only the access needed to upload and delete media. Leave the bucket name empty to use local filesystem storage (suitable for local development, not durable on a typical Render instance). `django-storages` uses Django's `STORAGES` configuration and the S3 backend; see the [S3 backend setup guide](https://django-storages.readthedocs.io/en/latest/backends/amazon-S3.html).

## Database handoff and backups

Migrations are the repeatable schema source; `backend/db.sqlite3` is deliberately excluded from Git. A complete live database backup can contain customer addresses, order history, emails, and password hashes, so keep it private and out of GitHub.

To export the product catalogue for a clean database handoff, run from `backend` after `DATABASE_URL` points at the intended database:

```powershell
.\.venv\Scripts\python.exe manage.py dumpdata store.category store.categoryimage store.product store.productimage store.coupon store.offer store.homepagebanner store.storelocation store.footerpagecontent store.sitebranding --natural-foreign --indent 2 --output ..\eroma-catalog.json
```

Copy `eroma-catalog.json` and the matching media files through a private channel. Restore into an empty database after running migrations:

```powershell
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py loaddata ..\eroma-catalog.json
```

For a full PostgreSQL backup, use `pg_dump` with the database's external connection URL and store the resulting backup in a private, access-controlled location. Do not put a full production database dump or any database URL/password in the repository. Back up uploaded media separately unless an object-storage provider already protects and versions it.

## Payment and tracking limits

Razorpay Checkout and server-side payment verification are implemented. Use test keys for a project demonstration. A production launch still needs live credentials, verified webhook handling for asynchronous events, and a refund/reconciliation process. The development-only simulated card option does not collect card data. Order tracking reads EROMA's saved order status; it is not connected to a carrier's live shipment API.

## WhatsApp contact

The EROMA-styled chat gathers a message on the site and opens a prefilled WhatsApp conversation to `VITE_WHATSAPP_NUMBER`. The customer must press Send in WhatsApp. The destination number must be registered with WhatsApp; the display name shown inside WhatsApp is controlled by that account's WhatsApp profile, not by the website.
