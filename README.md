# zainbahi

## TaxCopilot backend + admin panel

This repository now includes a Python backend that serves the frontend template and provides an admin panel for managing:

- Tax modules (Zakat, CIT, VAT, AI classification, risk, reports)
- E-file submissions
- Compliance risk records
- Audit report records
- Contact requests from the website form

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open:

- Frontend: `http://127.0.0.1:5000/`
- Admin panel: `http://127.0.0.1:5000/admin`

## API example

`POST /api/calculate/<module_code>` with JSON body:

- `zakat` keys: `zakatable_assets`, `deductible_liabilities`, `saudi_ownership`
- `cit` keys: `ebt`, `addbacks`, `deductions`, `foreign_ownership`
- `vat` keys: `output_vat`, `input_vat`, `partial_exemption_ratio`
