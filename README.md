# TaxCopilot Admin-Managed Website

This repository now includes a complete Flask-based website + admin panel for managing TaxCopilot landing-page content.

## What's included

- `app.py` (single Python backend file)
- `templates/index.html` (public website)
- `templates/admin.html` (full content management panel)
- `templates/login.html` (admin login)
- `taxcopilot.db` (auto-created SQLite database on first run)

## Features

- Full section-by-section content management from `/admin`
- JSON-based content model covering all core page sections
- Import/export content as JSON
- Reset content to defaults
- Admin authentication (session-based)

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install flask
python app.py
```

Open:

- Website: `http://127.0.0.1:5000/`
- Admin: `http://127.0.0.1:5000/admin`

## Default admin credentials

- Username: `admin`
- Password: `admin123`

Set your own securely:

```bash
export ADMIN_USERNAME='your-admin-user'
export ADMIN_PASSWORD='your-strong-password'
export FLASK_SECRET_KEY='your-random-secret'
python app.py
```

## Admin workflow

1. Login to `/admin`.
2. Expand any section (Hero, Modules, Pricing, Team, etc.).
3. Update JSON and click save.
4. Changes go live immediately on the website.
5. Optional: export/import JSON backups.
