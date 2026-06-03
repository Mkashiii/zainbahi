import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict

from flask import Flask, flash, jsonify, redirect, render_template, request, url_for

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "taxcopilot.db"
APP_ENV = os.environ.get("APP_ENV", "development").lower()
# Default reflects 85g gold equivalent in SAR for nisab checks and should be updated as regulations/market values change.
NISAB_THRESHOLD_SAR = float(os.environ.get("NISAB_THRESHOLD_SAR", "20785"))

app = Flask(__name__)
secret_key = os.environ.get("SECRET_KEY")
if APP_ENV != "development" and not secret_key:
    raise RuntimeError("SECRET_KEY environment variable is required outside development.")
app.config["SECRET_KEY"] = secret_key or os.urandom(32).hex()


DEFAULT_MODULES = [
    {
        "code": "zakat",
        "name": "Zakat Engine",
        "description": "ZATCA-compliant Zakat base computation with automatic nisab verification and Saudi-portion isolation.",
        "rate": 0.025,
        "ownership_scope": "saudi",
    },
    {
        "code": "cit",
        "name": "Corporate Income Tax",
        "description": "20% CIT on taxable income attributable to foreign shareholders with treaty checks.",
        "rate": 0.20,
        "ownership_scope": "foreign",
    },
    {
        "code": "vat",
        "name": "VAT Automation",
        "description": "15% VAT output/input reconciliation with quarterly return generation.",
        "rate": 0.15,
        "ownership_scope": "entity",
    },
    {
        "code": "classification",
        "name": "AI Account Classification",
        "description": "LLM-powered trial balance mapping with confidence scoring and review workflow.",
        "rate": 0.0,
        "ownership_scope": "entity",
    },
    {
        "code": "risk",
        "name": "Compliance Risk Scoring",
        "description": "Real-time ZATCA-aligned risk matrix, severity alerts, and remediation guidance.",
        "rate": 0.0,
        "ownership_scope": "entity",
    },
    {
        "code": "reports",
        "name": "Audit-Ready Reports",
        "description": "IFRS-aligned, ZATCA-formatted PDF/Excel/JSON export package generation.",
        "rate": 0.0,
        "ownership_scope": "entity",
    },
]


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def init_db() -> None:
    with get_connection() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS modules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                description TEXT NOT NULL,
                rate REAL NOT NULL DEFAULT 0,
                ownership_scope TEXT NOT NULL DEFAULT 'entity',
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS filings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_name TEXT NOT NULL,
                module_code TEXT NOT NULL,
                period_label TEXT NOT NULL,
                tax_base REAL NOT NULL DEFAULT 0,
                tax_due REAL NOT NULL DEFAULT 0,
                saudi_ownership REAL NOT NULL DEFAULT 100,
                foreign_ownership REAL NOT NULL DEFAULT 0,
                hijri_deadline TEXT,
                status TEXT NOT NULL DEFAULT 'draft',
                notes TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS risk_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_name TEXT NOT NULL,
                module_code TEXT NOT NULL,
                severity TEXT NOT NULL,
                score INTEGER NOT NULL,
                description TEXT NOT NULL,
                remediation TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_name TEXT NOT NULL,
                report_type TEXT NOT NULL,
                format TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS contacts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT NOT NULL,
                company TEXT NOT NULL,
                email TEXT NOT NULL,
                help_topic TEXT NOT NULL,
                message TEXT,
                created_at TEXT NOT NULL
            );
            """
        )

        existing = conn.execute("SELECT COUNT(*) AS c FROM modules").fetchone()["c"]
        if existing == 0:
            now = utc_now_iso()
            conn.executemany(
                """
                INSERT INTO modules (code, name, description, rate, ownership_scope, created_at)
                VALUES (:code, :name, :description, :rate, :ownership_scope, :created_at)
                """,
                [{**module, "created_at": now} for module in DEFAULT_MODULES],
            )


def to_float(raw: str, default: float = 0.0) -> float:
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


def calculate_zakat(payload: Dict[str, float]) -> Dict[str, float]:
    nisab_threshold = NISAB_THRESHOLD_SAR
    zakatable_assets = payload.get("zakatable_assets", 0.0)
    deductible_liabilities = payload.get("deductible_liabilities", 0.0)
    saudi_ownership = payload.get("saudi_ownership", 100.0)

    zakat_base = max(zakatable_assets - deductible_liabilities, 0.0)
    saudi_portion_base = zakat_base * max(min(saudi_ownership, 100.0), 0.0) / 100.0
    nisab_met = saudi_portion_base >= nisab_threshold
    tax_due = round(saudi_portion_base * 0.025, 2) if nisab_met else 0.0

    return {
        "zakat_base": round(zakat_base, 2),
        "saudi_portion_base": round(saudi_portion_base, 2),
        "nisab_threshold": nisab_threshold,
        "nisab_met": nisab_met,
        "tax_due": tax_due,
    }


def calculate_cit(payload: Dict[str, float]) -> Dict[str, float]:
    ebt = payload.get("ebt", 0.0)
    addbacks = payload.get("addbacks", 0.0)
    deductions = payload.get("deductions", 0.0)
    foreign_ownership = payload.get("foreign_ownership", 0.0)

    taxable_income = max(ebt + addbacks - deductions, 0.0)
    foreign_portion_income = taxable_income * max(min(foreign_ownership, 100.0), 0.0) / 100.0
    tax_due = round(foreign_portion_income * 0.20, 2)

    return {
        "taxable_income": round(taxable_income, 2),
        "foreign_portion_income": round(foreign_portion_income, 2),
        "tax_due": tax_due,
    }


def calculate_vat(payload: Dict[str, float]) -> Dict[str, float]:
    output_vat = payload.get("output_vat", 0.0)
    input_vat = payload.get("input_vat", 0.0)
    partial_exemption_ratio = payload.get("partial_exemption_ratio", 100.0)

    recoverable_input = input_vat * max(min(partial_exemption_ratio, 100.0), 0.0) / 100.0
    net_vat = round(output_vat - recoverable_input, 2)

    return {
        "output_vat": round(output_vat, 2),
        "recoverable_input_vat": round(recoverable_input, 2),
        "net_vat_due": net_vat,
    }


CALCULATORS = {
    "zakat": calculate_zakat,
    "cit": calculate_cit,
    "vat": calculate_vat,
}

MODULE_INPUT_KEYS = {
    "zakat": {"zakatable_assets", "deductible_liabilities", "saudi_ownership"},
    "cit": {"ebt", "addbacks", "deductions", "foreign_ownership"},
    "vat": {"output_vat", "input_vat", "partial_exemption_ratio"},
}


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/contact", methods=["POST"])
def create_contact():
    payload = {
        "full_name": request.form.get("full_name", "").strip(),
        "company": request.form.get("company", "").strip(),
        "email": request.form.get("email", "").strip(),
        "help_topic": request.form.get("help_topic", "").strip(),
        "message": request.form.get("message", "").strip(),
        "created_at": utc_now_iso(),
    }

    if not all([payload["full_name"], payload["company"], payload["email"], payload["help_topic"]]):
        flash("Please complete all required contact fields.", "error")
        return redirect(url_for("index") + "#contact")

    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO contacts (full_name, company, email, help_topic, message, created_at)
            VALUES (:full_name, :company, :email, :help_topic, :message, :created_at)
            """,
            payload,
        )

    flash("Your message was submitted successfully.", "success")
    return redirect(url_for("index") + "#contact")


@app.route("/api/calculate/<module_code>", methods=["POST"])
def calculate_tax(module_code: str):
    module_code = module_code.lower()
    calculator = CALCULATORS.get(module_code)
    if not calculator:
        return jsonify({"error": "Unsupported module code"}), 400

    body = request.get_json(silent=True) or {}
    allowed_keys = MODULE_INPUT_KEYS[module_code]
    numeric_payload = {key: to_float(body.get(key)) for key in allowed_keys}
    result = calculator(numeric_payload)
    return jsonify({"module": module_code, "result": result})


@app.route("/efile", methods=["POST"])
def create_efile_submission():
    module_code = request.form.get("module_code", "").lower().strip()
    company_name = request.form.get("company_name", "").strip()
    period_label = request.form.get("period_label", "").strip()

    if module_code not in CALCULATORS or not company_name or not period_label:
        flash("E-file submission requires company, period, and a valid module.", "error")
        return redirect(url_for("admin_dashboard"))

    calc_input = {
        "zakatable_assets": to_float(request.form.get("zakatable_assets")),
        "deductible_liabilities": to_float(request.form.get("deductible_liabilities")),
        "saudi_ownership": to_float(request.form.get("saudi_ownership"), 100.0),
        "ebt": to_float(request.form.get("ebt")),
        "addbacks": to_float(request.form.get("addbacks")),
        "deductions": to_float(request.form.get("deductions")),
        "foreign_ownership": to_float(request.form.get("foreign_ownership")),
        "output_vat": to_float(request.form.get("output_vat")),
        "input_vat": to_float(request.form.get("input_vat")),
        "partial_exemption_ratio": to_float(request.form.get("partial_exemption_ratio"), 100.0),
    }

    result = CALCULATORS[module_code](calc_input)
    tax_due = result.get("tax_due", result.get("net_vat_due", 0.0))
    tax_base = (
        result.get("zakat_base")
        or result.get("taxable_income")
        or result.get("output_vat")
        or 0.0
    )

    filing_payload = {
        "company_name": company_name,
        "module_code": module_code,
        "period_label": period_label,
        "tax_base": tax_base,
        "tax_due": tax_due,
        "saudi_ownership": calc_input["saudi_ownership"],
        "foreign_ownership": calc_input["foreign_ownership"],
        "hijri_deadline": request.form.get("hijri_deadline", "").strip() or None,
        "status": request.form.get("status", "submitted").strip() or "submitted",
        "notes": request.form.get("notes", "").strip(),
        "created_at": utc_now_iso(),
    }

    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO filings (
                company_name, module_code, period_label, tax_base, tax_due,
                saudi_ownership, foreign_ownership, hijri_deadline, status, notes, created_at
            ) VALUES (
                :company_name, :module_code, :period_label, :tax_base, :tax_due,
                :saudi_ownership, :foreign_ownership, :hijri_deadline, :status, :notes, :created_at
            )
            """,
            filing_payload,
        )

    flash("E-file record created.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin", methods=["GET"])
def admin_dashboard():
    with get_connection() as conn:
        modules = conn.execute("SELECT * FROM modules ORDER BY id").fetchall()
        filings = conn.execute("SELECT * FROM filings ORDER BY id DESC LIMIT 30").fetchall()
        risks = conn.execute("SELECT * FROM risk_items ORDER BY id DESC LIMIT 30").fetchall()
        reports = conn.execute("SELECT * FROM reports ORDER BY id DESC LIMIT 30").fetchall()
        contacts = conn.execute("SELECT * FROM contacts ORDER BY id DESC LIMIT 30").fetchall()

    return render_template(
        "admin.html",
        modules=modules,
        filings=filings,
        risks=risks,
        reports=reports,
        contacts=contacts,
    )


@app.route("/admin/modules", methods=["POST"])
def add_module():
    payload = {
        "code": request.form.get("code", "").strip().lower(),
        "name": request.form.get("name", "").strip(),
        "description": request.form.get("description", "").strip(),
        "rate": to_float(request.form.get("rate")),
        "ownership_scope": request.form.get("ownership_scope", "entity").strip(),
        "created_at": utc_now_iso(),
    }

    if not all([payload["code"], payload["name"], payload["description"]]):
        flash("Module code, name, and description are required.", "error")
        return redirect(url_for("admin_dashboard"))

    with get_connection() as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO modules (id, code, name, description, rate, ownership_scope, is_active, created_at)
            VALUES (
                (SELECT id FROM modules WHERE code = :code),
                :code, :name, :description, :rate, :ownership_scope,
                COALESCE((SELECT is_active FROM modules WHERE code = :code), 1),
                COALESCE((SELECT created_at FROM modules WHERE code = :code), :created_at)
            )
            """,
            payload,
        )

    flash("Module saved successfully.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/modules/<int:module_id>/toggle", methods=["POST"])
def toggle_module(module_id: int):
    with get_connection() as conn:
        conn.execute(
            """
            UPDATE modules
            SET is_active = CASE WHEN is_active = 1 THEN 0 ELSE 1 END
            WHERE id = ?
            """,
            (module_id,),
        )
    flash("Module status updated.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/risk", methods=["POST"])
def add_risk():
    payload = {
        "company_name": request.form.get("company_name", "").strip(),
        "module_code": request.form.get("module_code", "").strip(),
        "severity": request.form.get("severity", "Medium").strip(),
        "score": int(to_float(request.form.get("score"), 0.0)),
        "description": request.form.get("description", "").strip(),
        "remediation": request.form.get("remediation", "").strip(),
        "created_at": utc_now_iso(),
    }

    if not all([payload["company_name"], payload["module_code"], payload["description"]]):
        flash("Risk entry requires company, module, and description.", "error")
        return redirect(url_for("admin_dashboard"))

    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO risk_items (company_name, module_code, severity, score, description, remediation, created_at)
            VALUES (:company_name, :module_code, :severity, :score, :description, :remediation, :created_at)
            """,
            payload,
        )

    flash("Risk record added.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/reports", methods=["POST"])
def add_report():
    payload = {
        "company_name": request.form.get("company_name", "").strip(),
        "report_type": request.form.get("report_type", "").strip(),
        "format": request.form.get("format", "PDF").strip(),
        "status": request.form.get("status", "Generated").strip(),
        "created_at": utc_now_iso(),
    }

    if not all([payload["company_name"], payload["report_type"]]):
        flash("Report entry requires company and report type.", "error")
        return redirect(url_for("admin_dashboard"))

    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO reports (company_name, report_type, format, status, created_at)
            VALUES (:company_name, :report_type, :format, :status, :created_at)
            """,
            payload,
        )

    flash("Report record added.", "success")
    return redirect(url_for("admin_dashboard"))


if __name__ == "__main__":
    init_db()
    app.run(
        host=os.environ.get("FLASK_HOST", "127.0.0.1"),
        port=int(os.environ.get("PORT", "5000")),
        debug=os.environ.get("FLASK_DEBUG") == "1",
    )
else:
    init_db()
