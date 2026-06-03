import json
import os
import secrets
import sqlite3
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path

from flask import (
    abort,
    Flask,
    flash,
    g,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "taxcopilot.db"

DEFAULT_CONTENT = {
    "site_meta": {
        "product_name": "TaxCopilot",
        "product_badge": "BETA",
        "headline": "Saudi SME Tax Compliance, Automated by AI",
        "subheadline": "TaxCopilot automates Zakat, Corporate Tax, and VAT for Saudi SMEs — from trial balance to ZATCA-ready filing in minutes, not months.",
        "vision_badges": [
            "Built for Saudi Vision 2030",
            "ZATCA Compliant",
            "Live Beta",
        ],
        "cta_primary": "Start Free 30-Day Trial",
        "cta_secondary": "See How It Works",
    },
    "trust_badges": [
        "No credit card required",
        "Saudi-hosted data",
        "ZATCA certified",
        "FATOORAH ready",
    ],
    "dashboard_preview": {
        "company": "Al-Noor Trading — FY 2024 Tax Dashboard",
        "status": "LIVE",
        "metrics": [
            {"label": "Revenue", "value": "SAR 42.7M", "note": "▲ 8.3% YoY"},
            {"label": "Zakat Due", "value": "SAR 491K", "note": "2.5% of base"},
            {"label": "Corp. Tax", "value": "SAR 405K", "note": "20% foreign"},
            {"label": "Risk Alerts", "value": "2 High", "note": "Action needed"},
        ],
        "review_note": "AI classified 23 accounts with 95.8% avg confidence — 5 pending review",
    },
    "stats_strip": [
        {"label": "Tax Managed", "value": "SAR 2.8B+"},
        {"label": "SMEs Onboarded", "value": "340+"},
        {"label": "Filing Accuracy", "value": "99.2%"},
        {"label": "Saved Per Month", "value": "40h"},
        {"label": "AI Confidence Avg", "value": "95.8%"},
    ],
    "problem": {
        "title": "Saudi SMEs are drowning in compliance complexity",
        "intro": "With ZATCA's accelerated reform agenda, VAT at 15%, dual-regime Zakat + CIT, and mandatory e-invoicing — the compliance burden on Saudi SMEs has never been heavier.",
        "items": [
            "40–80 hours per filing cycle spent manually mapping GL accounts, computing Zakat bases, and preparing VAT returns.",
            "Mixed ownership is a compliance minefield, causing Zakat/CIT split errors and penalties.",
            "No single platform handles Zakat + CIT + VAT + FATOORAH + risk scoring together.",
        ],
    },
    "solution": {
        "title": "One AI-powered platform. End-to-end Saudi compliance.",
        "body": "Upload your trial balance. Our AI classifies accounts, computes exact obligations, flags risk in real time, and generates ZATCA-ready filings automatically.",
        "kpis": [
            {"label": "From TB upload to filing draft", "value": "10 min"},
            {"label": "AI classification accuracy", "value": "95%+"},
            {"label": "Consultant fees for standard filings", "value": "SAR 0"},
            {"label": "Compliance modules in one platform", "value": "6-in-1"},
        ],
    },
    "modules": [
        {
            "icon": "☪️",
            "name": "Zakat Engine",
            "description": "ZATCA-compliant Zakat base computation with automatic nisab verification and Saudi-portion isolation.",
            "features": [
                "Zakatable assets auto-classification",
                "Deductible liabilities mapping",
                "2.5% on Saudi ownership portion only",
                "Hijri deadline tracking",
                "Schedule Z worksheets",
            ],
        },
        {
            "icon": "🏦",
            "name": "Corporate Income Tax",
            "description": "20% CIT on taxable income attributable to foreign shareholders, with treaty and reconciliation support.",
            "features": [
                "Mixed-ownership split",
                "EBT-to-taxable reconciliation",
                "Withholding tax computation",
                "Treaty flags",
                "CIT-02 auto-population",
            ],
        },
        {
            "icon": "🧾",
            "name": "VAT Automation",
            "description": "15% VAT output/input reconciliation with quarterly return generation and FATOORAH integration.",
            "features": [
                "Output vs input reconciliation",
                "Partial exemption apportionment",
                "VAT-02 auto-fill",
                "FATOORAH API ready",
                "Quarterly alerts",
            ],
        },
        {
            "icon": "🤖",
            "name": "AI Account Classification",
            "description": "LLM-powered mapping to ZATCA chart of accounts with confidence and reviewer workflow.",
            "features": [
                "95%+ classification accuracy",
                "Confidence scoring",
                "Impact flagging",
                "Approve/reject workflow",
                "Custom mapping library",
            ],
        },
        {
            "icon": "🛡️",
            "name": "Compliance Risk Scoring",
            "description": "Real-time risk matrix with ZATCA-aligned severity and remediation guidance.",
            "features": [
                "100-point compliance score",
                "High/Medium/Low alerts",
                "Deadline countdown",
                "Transfer pricing exposure",
                "Board-ready reports",
            ],
        },
        {
            "icon": "📊",
            "name": "Audit-Ready Reports",
            "description": "IFRS-aligned, ZATCA-formatted filing packs exportable as PDF, Excel, and JSON.",
            "features": [
                "Zakat return package",
                "CIT-02 generation",
                "VAT-02 quarterly filings",
                "Management summary",
                "Classified TB export",
            ],
        },
    ],
    "how_it_works": [
        {"step": "Upload TB", "description": "Upload Excel, CSV, or ZATCA XML trial balance."},
        {"step": "AI Classifies", "description": "LLM maps accounts to ZATCA CoA with confidence."},
        {"step": "Human Review", "description": "Finance team approves or adjusts flagged mappings."},
        {"step": "Tax Computed", "description": "Zakat, CIT, and VAT are calculated per ZATCA methodology."},
        {"step": "File & Report", "description": "Download filing-ready returns or submit via API."},
    ],
    "integrations": [
        "ZATCA Portal",
        "FATOORAH",
        "SAP",
        "Oracle",
        "Microsoft Dynamics 365",
        "Business Central",
        "QuickBooks",
        "Zoho Books",
        "Xero",
    ],
    "customers": [
        {
            "name": "Trading & Distribution Companies",
            "description": "High inventory volumes and complex VAT chains.",
            "tags": ["Zakat Heavy", "VAT Complex", "10–500 staff"],
        },
        {
            "name": "Construction & Contracting Firms",
            "description": "Long-term contracts, retention, and WIP valuation.",
            "tags": ["WIP Zakat", "CIT Exposure", "Project-based"],
        },
        {
            "name": "Healthcare & Pharma",
            "description": "Zero-rated items, exemptions, and dual-license structures.",
            "tags": ["VAT Exempt Mix", "Foreign JV", "Regulated"],
        },
        {
            "name": "Tech & SaaS Startups",
            "description": "First filing support with FATOORAH Phase 2 readiness.",
            "tags": ["First Filing", "FATOORAH", "Seed–Series B"],
        },
        {
            "name": "Manufacturing & Industrial",
            "description": "Asset-heavy compliance with export VAT relief.",
            "tags": ["Asset Heavy", "Export VAT", "Vision 2030"],
        },
        {
            "name": "Accounting & Tax Firms",
            "description": "White-label multi-client compliance operations.",
            "tags": ["Multi-Client", "White Label", "Partner Tier"],
        },
    ],
    "impact": [
        {"label": "Tax Managed", "value": "SAR 2.8B+"},
        {"label": "Saved Per Month", "value": "40 hrs"},
        {"label": "Filing Accuracy", "value": "99.2%"},
        {"label": "SMEs Onboarded", "value": "340+"},
        {"label": "Penalties Avoided", "value": "SAR 18M"},
        {"label": "AI Accuracy", "value": "95.8%"},
    ],
    "testimonials": [
        {
            "quote": "TaxCopilot cut our quarterly VAT filing time from 3 days to under 2 hours.",
            "author": "CFO, Al-Noor Trading Company Ltd. · Riyadh",
        },
        {
            "quote": "White-label support transformed our delivery for 40 SME clients.",
            "author": "Managing Partner, Saudi Regional Accounting Firm · Jeddah",
        },
    ],
    "vision_2030": {
        "title": "Built on Saudi Arabia's digital transformation agenda",
        "intro": "TaxCopilot supports ZATCA's digital compliance mandate and Vision 2030 SME growth goals.",
        "pillars": [
            "FATOORAH e-Invoicing",
            "ZATCA Regulatory Alignment",
            "SME Formalization",
            "Saudi-Hosted Infrastructure",
        ],
        "metrics": [
            {"label": "Compliance target", "value": "100% Digital"},
            {"label": "FATOORAH rollout", "value": "Phase 2 Live"},
            {"label": "SME GDP target", "value": "35% by 2030"},
            {"label": "Market size", "value": "SAR 2.1B TAM"},
        ],
    },
    "roadmap": [
        {
            "phase": "Shipped",
            "timeline": "Q1–Q2 2024",
            "items": [
                "Zakat base engine",
                "CIT mixed-ownership calc",
                "VAT output/input reconciliation",
                "AI classification v1",
                "Risk scoring dashboard",
                "PDF report generation",
            ],
        },
        {
            "phase": "Now",
            "timeline": "Q3–Q4 2024",
            "items": [
                "FATOORAH Phase 2 API",
                "Multi-entity dashboard",
                "ERP integrations",
                "AI classification v2",
                "Accountant partner portal",
            ],
        },
        {
            "phase": "Next",
            "timeline": "Q1–Q2 2025",
            "items": [
                "Withholding tax module",
                "Transfer pricing disclosure",
                "Arabic UI",
                "Mobile app",
                "Audit support mode",
            ],
        },
        {
            "phase": "Future",
            "timeline": "H2 2025+",
            "items": [
                "GCC expansion",
                "Tax forecasting",
                "AI audit defense assistant",
                "Embedded payroll tax",
                "Banking API integration",
            ],
        },
    ],
    "team": [
        {
            "name": "Azeem Hassan",
            "role": "Founder & CEO",
            "details": "17+ years in FP&A, ZATCA compliance, ERP implementation, and tax advisory.",
        },
        {
            "name": "Open Role",
            "role": "Chief Technology Officer",
            "details": "Seeking AI/ML leader with NLP and Arabic tax classification experience.",
        },
        {
            "name": "Open Role",
            "role": "VP Tax & Compliance",
            "details": "Seeking ZATCA-qualified CA/CPA with Big 4 KSA background.",
        },
        {
            "name": "Open Role",
            "role": "GM Sales & Partnerships",
            "details": "Seeking Saudi B2B SaaS growth leader.",
        },
    ],
    "pricing": [
        {
            "plan": "Starter",
            "price": "1,200 SAR /mo",
            "description": "For small businesses filing first Zakat or VAT return.",
            "features": [
                "1 legal entity",
                "Zakat Engine",
                "VAT quarterly return",
                "AI classification (up to 200 accounts)",
                "2 users",
            ],
        },
        {
            "plan": "Growth",
            "price": "3,500 SAR /mo",
            "description": "For mixed-ownership SMEs with Zakat + CIT obligations.",
            "features": [
                "Up to 3 entities",
                "Zakat + CIT + VAT",
                "FATOORAH integration",
                "Unlimited AI classification",
                "Risk scoring dashboard",
                "10 users",
            ],
        },
        {
            "plan": "Enterprise",
            "price": "Custom",
            "description": "For firms and groups needing white-label and API access.",
            "features": [
                "Unlimited entities/users",
                "All modules",
                "ERP deep integration",
                "Dedicated compliance manager",
                "Custom SLA",
            ],
        },
    ],
    "contact": {
        "email": "hello@taxcopilot.sa",
        "demo_email": "demo@taxcopilot.sa",
        "help_options": [
            "Zakat Filing",
            "Corporate Tax (CIT)",
            "VAT Returns",
            "Full Compliance Suite",
            "Partnership / Reseller",
        ],
    },
    "footer": {
        "badges": ["ZATCA", "FATOORAH", "SOC 2", "ISO 27001"],
        "legal_links": ["Privacy Policy", "Terms of Service", "Data Residency", "Help Center"],
        "copyright": "© 2024 TaxCopilot. All rights reserved. Registered in Saudi Arabia.",
    },
}

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("FLASK_SECRET_KEY") or secrets.token_hex(32)
app.config["DATABASE"] = str(DB_PATH)


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
    return g.db


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def get_csrf_token():
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return token


def require_csrf():
    token = request.form.get("csrf_token", "")
    if not token or token != session.get("csrf_token"):
        abort(400, "Invalid CSRF token.")


@app.teardown_appcontext
def close_db(_error):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS content_sections (
            section_key TEXT PRIMARY KEY,
            section_label TEXT NOT NULL,
            section_value TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    db.commit()


def seed_admin():
    db = get_db()
    existing_count = db.execute("SELECT COUNT(*) AS total FROM admins").fetchone()["total"]
    if existing_count > 0:
        return
    username = os.environ.get("ADMIN_USERNAME")
    password = os.environ.get("ADMIN_PASSWORD")
    if not username or not password:
        raise RuntimeError(
            "ADMIN_USERNAME and ADMIN_PASSWORD must be set before first run to create the initial admin account."
        )
    db.execute(
        "INSERT INTO admins (username, password_hash, created_at) VALUES (?, ?, ?)",
        (username, generate_password_hash(password), utc_now()),
    )
    db.commit()


def seed_sections():
    db = get_db()
    count = db.execute("SELECT COUNT(*) AS total FROM content_sections").fetchone()["total"]
    if count > 0:
        return
    for key, value in DEFAULT_CONTENT.items():
        db.execute(
            """
            INSERT INTO content_sections (section_key, section_label, section_value, updated_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                key,
                key.replace("_", " ").title(),
                json.dumps(value, ensure_ascii=False, indent=2),
                utc_now(),
            ),
        )
    db.commit()


def ensure_setup():
    init_db()
    seed_admin()
    seed_sections()


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "admin_id" not in session:
            return redirect(url_for("admin_login"))
        return view(*args, **kwargs)

    return wrapped


def load_sections(raw: bool = False):
    db = get_db()
    rows = db.execute(
        "SELECT section_key, section_label, section_value, updated_at FROM content_sections ORDER BY section_key"
    ).fetchall()
    sections = []
    as_map = {}
    for row in rows:
        parsed = row["section_value"]
        if not raw:
            try:
                parsed = json.loads(parsed)
            except json.JSONDecodeError:
                pass
        entry = {
            "key": row["section_key"],
            "label": row["section_label"],
            "value": parsed,
            "updated_at": row["updated_at"],
        }
        sections.append(entry)
        as_map[row["section_key"]] = parsed
    return sections, as_map


@app.before_request
def _bootstrap():
    ensure_setup()


@app.route("/")
def index():
    _sections, content = load_sections(raw=False)
    return render_template("index.html", content=content)


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        require_csrf()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        db = get_db()
        admin = db.execute("SELECT id, username, password_hash FROM admins WHERE username = ?", (username,)).fetchone()
        if admin and check_password_hash(admin["password_hash"], password):
            session["admin_id"] = admin["id"]
            session["admin_username"] = admin["username"]
            return redirect(url_for("admin_panel"))
        flash("Invalid username or password.", "error")
    return render_template("login.html", csrf_token=get_csrf_token())


@app.post("/admin/logout")
def admin_logout():
    require_csrf()
    session.clear()
    return redirect(url_for("index"))


@app.route("/admin")
@admin_required
def admin_panel():
    sections, _content = load_sections(raw=True)
    db = get_db()
    totals = {
        "sections": db.execute("SELECT COUNT(*) AS total FROM content_sections").fetchone()["total"],
        "admin_users": db.execute("SELECT COUNT(*) AS total FROM admins").fetchone()["total"],
    }
    return render_template(
        "admin.html", sections=sections, totals=totals, csrf_token=get_csrf_token()
    )


@app.post("/admin/section/<section_key>")
@admin_required
def update_section(section_key: str):
    require_csrf()
    payload = request.form.get("section_value", "")
    if not payload.strip():
        flash(f"{section_key}: content cannot be empty.", "error")
        return redirect(url_for("admin_panel"))

    try:
        parsed = json.loads(payload)
        normalized = json.dumps(parsed, ensure_ascii=False, indent=2)
    except json.JSONDecodeError as error:
        flash(f"{section_key}: invalid JSON ({error.msg} at line {error.lineno}).", "error")
        return redirect(url_for("admin_panel"))

    db = get_db()
    updated = db.execute(
        """
        UPDATE content_sections
        SET section_value = ?, updated_at = ?
        WHERE section_key = ?
        """,
        (normalized, utc_now(), section_key),
    )
    db.commit()
    if updated.rowcount == 0:
        flash(f"Section '{section_key}' not found.", "error")
    else:
        flash(f"Section '{section_key}' updated.", "success")
    return redirect(url_for("admin_panel"))


@app.post("/admin/sections/reset")
@admin_required
def reset_sections():
    require_csrf()
    db = get_db()
    db.execute("DELETE FROM content_sections")
    for key, value in DEFAULT_CONTENT.items():
        db.execute(
            """
            INSERT INTO content_sections (section_key, section_label, section_value, updated_at)
            VALUES (?, ?, ?, ?)
            """,
            (
                key,
                key.replace("_", " ").title(),
                json.dumps(value, ensure_ascii=False, indent=2),
                utc_now(),
            ),
        )
    db.commit()
    flash("All sections reset to default TaxCopilot content.", "success")
    return redirect(url_for("admin_panel"))


@app.route("/admin/export")
@admin_required
def export_sections():
    sections, _content = load_sections(raw=True)
    payload = {item["key"]: json.loads(item["value"]) for item in sections}
    target = BASE_DIR / "content-export.json"
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return send_file(target, as_attachment=True, download_name="taxcopilot-content-export.json")


@app.post("/admin/import")
@admin_required
def import_sections():
    require_csrf()
    uploaded = request.files.get("content_file")
    if not uploaded or not uploaded.filename:
        flash("Please upload a JSON file.", "error")
        return redirect(url_for("admin_panel"))

    try:
        incoming = json.loads(uploaded.read().decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        flash("Invalid JSON file.", "error")
        return redirect(url_for("admin_panel"))

    if not isinstance(incoming, dict):
        flash("JSON root must be an object keyed by section name.", "error")
        return redirect(url_for("admin_panel"))

    db = get_db()
    valid_keys = {
        row["section_key"]
        for row in db.execute("SELECT section_key FROM content_sections").fetchall()
    }

    updated_count = 0
    for key, value in incoming.items():
        if key not in valid_keys:
            continue
        db.execute(
            "UPDATE content_sections SET section_value = ?, updated_at = ? WHERE section_key = ?",
            (json.dumps(value, ensure_ascii=False, indent=2), utc_now(), key),
        )
        updated_count += 1

    db.commit()
    flash(f"Imported {updated_count} section(s).", "success")
    return redirect(url_for("admin_panel"))


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=os.environ.get("FLASK_DEBUG", "false").lower() == "true",
    )
