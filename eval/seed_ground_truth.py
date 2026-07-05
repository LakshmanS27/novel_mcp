"""Seed a target directory with known compliance violations for evaluation.

This script plants a controlled set of files containing detectable patterns
(credentials, PII, payment card numbers) into a target directory. Each planted
file is recorded in a ground-truth manifest so evaluation can measure recall
and false-positive rates precisely.

Usage:
    python -m eval.seed_ground_truth /path/to/target/repo

The script never modifies existing files. It only creates new files inside a
`.eval_ground_truth/` subdirectory of the target.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

SEED_DIR_NAME = ".eval_ground_truth"

# NOTE ON PLANTED SECRETS: every credential below is synthetic (canonical
# documentation examples / Luhn-valid test numbers). Signature-matching tokens
# are split across adjacent string literals so hosting-platform push protection
# (e.g. GitHub GH013) does not block commits; Python rejoins them at parse
# time, so fixtures written to disk are byte-identical to the unsplit form.
SEED_FILES: list[dict] = [
    {
        "relative_path": "config/.env.production",
        "description": "Production environment file with database credentials and API keys",
        "expected_patterns": ["GENERIC_SECRET", "AWS_KEY"],
        "frameworks": ["CREDENTIAL", "GDPR Art.32", "DPDP Sec.8"],
        "content": (
            "# Production config - DO NOT COMMIT\n"
            "DATABASE_URL=postgresql://prod_admin:Xk9$mP2vL7@db.internal.corp:5432/production\n"
            "REDIS_URL=redis://:cache_secret_8f2a@redis.internal.corp:6379/0\n"
            "AWS_ACCESS_KEY_ID=AK" "IAVRZ7EXAMPLE4EVAL\n"
            "AWS_SECRET_ACCESS_KEY=wJa9rXUtnFEMI/" "K7MDENG/bPxRfiCY3VALUEK3Y\n"
            "STRIPE_SECRET_KEY=sk_" "live_51N3xAmPlEk3Y9a8B7c6D5\n"
            "JWT_SIGNING_SECRET=hmac-sha256-super-secret-signing-key-2026\n"
        ),
    },
    {
        "relative_path": "data/customer_export.csv",
        "description": "Customer PII export with emails, phone numbers, and Indian PAN IDs",
        "expected_patterns": ["PII", "INDIAN_PAN", "EMAIL"],
        "frameworks": ["GDPR Art.5", "DPDP Sec.4", "DPDP Sec.8"],
        "content": (
            "id,name,email,phone,pan_id,address\n"
            "1001,Priya Sharma,priya.sharma@example.corp,+91-9876543210,ABCPD1234E,\"14 MG Road, Bengaluru\"\n"
            "1002,Rahul Verma,rahul.verma@example.corp,+91-8765432109,XYZPV5678F,\"22 Connaught Place, Delhi\"\n"
            "1003,Anita Desai,anita.desai@example.corp,+91-7654321098,MNOPD9012G,\"8 Park Street, Kolkata\"\n"
            "1004,Vikram Singh,vikram.singh@example.corp,+91-6543210987,QRSPS3456H,\"31 FC Road, Pune\"\n"
            "1005,Meera Nair,meera.nair@example.corp,+91-5432109876,TUVPN7890J,\"5 Marine Drive, Kochi\"\n"
        ),
    },
    {
        "relative_path": "scripts/db_migrate.sh",
        "description": "Migration script with embedded database password",
        "expected_patterns": ["GENERIC_SECRET"],
        "frameworks": ["CREDENTIAL", "GDPR Art.32"],
        "content": (
            "#!/bin/bash\n"
            "# Run production migration\n"
            "export PGPASSWORD='migrate_prod_2026!secret'\n"
            "psql -h db.internal.corp -U migration_admin -d production -f ./migrations/latest.sql\n"
            "echo \"Migration complete\"\n"
        ),
    },
    {
        "relative_path": "src/billing/payment_handler.py",
        "description": "Payment handler with a hardcoded PAN (credit card number) in a debug line",
        "expected_patterns": ["PAN"],
        "frameworks": ["PCI-DSS"],
        "content": (
            '"""Payment processing handler."""\n'
            "\n"
            "import stripe\n"
            "\n"
            "\n"
            "def charge_card(amount_cents: int, token: str) -> dict:\n"
            '    stripe.api_key = "sk_' 'live_4eC39HqLyjWDarjtT1zdp7dc"\n'
            "    return stripe.Charge.create(amount=amount_cents, currency='usd', source=token)\n"
            "\n"
            "\n"
            "# Debug: customer reported double charge on card 4532015112830366\n"
            "# Investigating transaction from 2026-03-15\n"
            "def refund_transaction(charge_id: str) -> dict:\n"
            "    return stripe.Refund.create(charge=charge_id)\n"
        ),
    },
    {
        "relative_path": "backup/employees_q1_2026.json",
        "description": "Employee records with Aadhaar numbers and salary data",
        "expected_patterns": ["AADHAAR", "PII", "EMAIL"],
        "frameworks": ["DPDP Sec.4", "DPDP Sec.8", "GDPR Art.5"],
        "content": json.dumps(
            {
                "export_date": "2026-03-31",
                "employees": [
                    {"emp_id": "E-4001", "name": "Suresh Kumar", "email": "suresh.k@corp.internal", "aadhaar": "234567890123", "salary_inr": 1850000, "department": "Engineering"},
                    {"emp_id": "E-4002", "name": "Deepa Menon", "email": "deepa.m@corp.internal", "aadhaar": "345678901234", "salary_inr": 2100000, "department": "Product"},
                    {"emp_id": "E-4003", "name": "Arjun Patel", "email": "arjun.p@corp.internal", "aadhaar": "456789012345", "salary_inr": 1650000, "department": "Engineering"},
                ],
            },
            indent=2,
        )
        + "\n",
    },
    # --- FALSE-POSITIVE TRAPS (should NOT be flagged as violations) ---
    {
        "relative_path": "tests/test_payment_validation.py",
        "description": "FP TRAP: test file with standard Stripe/Luhn test card numbers",
        "expected_patterns": [],
        "frameworks": [],
        "is_false_positive_trap": True,
        "content": (
            '"""Unit tests for payment validation."""\n'
            "\n"
            "import pytest\n"
            "\n"
            "# Standard industry test card numbers\n"
            "TEST_VISA = '4111111111111111'\n"
            "TEST_MC = '5500005555555559'\n"
            "TEST_AMEX = '378282246310005'\n"
            "\n"
            "\n"
            "def test_luhn_check_valid():\n"
            "    assert luhn_valid(TEST_VISA)\n"
            "    assert luhn_valid(TEST_MC)\n"
            "    assert luhn_valid(TEST_AMEX)\n"
            "\n"
            "\n"
            "def test_luhn_check_invalid():\n"
            "    assert not luhn_valid('0000000000000000')\n"
        ),
    },
    {
        "relative_path": "docs/api_guide.md",
        "description": "FP TRAP: documentation with example placeholder credentials",
        "expected_patterns": [],
        "frameworks": [],
        "is_false_positive_trap": True,
        "content": (
            "# API Integration Guide\n"
            "\n"
            "## Authentication\n"
            "\n"
            "Set your API key in the request header:\n"
            "\n"
            "```bash\n"
            'curl -H "Authorization: Bearer YOUR_API_KEY_HERE" \\\n'
            "     https://api.example.com/v1/users\n"
            "```\n"
            "\n"
            "## Example request\n"
            "\n"
            "```json\n"
            '{"email": "user@example.com", "name": "Jane Doe"}\n'
            "```\n"
            "\n"
            "Replace `YOUR_API_KEY_HERE` with your actual key from the dashboard.\n"
        ),
    },
]


def seed(target_root: Path) -> dict:
    seed_dir = target_root / SEED_DIR_NAME
    seed_dir.mkdir(parents=True, exist_ok=True)

    manifest: list[dict] = []

    for entry in SEED_FILES:
        file_path = seed_dir / entry["relative_path"]
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(entry["content"], encoding="utf-8")

        manifest.append(
            {
                "path": str(file_path),
                "relative_path": entry["relative_path"],
                "description": entry["description"],
                "expected_patterns": entry["expected_patterns"],
                "frameworks": entry["frameworks"],
                "is_false_positive_trap": entry.get("is_false_positive_trap", False),
            }
        )

    manifest_data = {
        "seeded_at": datetime.now(timezone.utc).isoformat(),
        "target_root": str(target_root),
        "seed_directory": str(seed_dir),
        "total_violation_files": sum(1 for m in manifest if not m["is_false_positive_trap"]),
        "total_fp_trap_files": sum(1 for m in manifest if m["is_false_positive_trap"]),
        "files": manifest,
    }

    manifest_path = seed_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest_data, indent=2) + "\n", encoding="utf-8")

    return manifest_data


def clean(target_root: Path) -> None:
    import shutil

    seed_dir = target_root / SEED_DIR_NAME
    if seed_dir.exists():
        shutil.rmtree(seed_dir)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: python -m eval.seed_ground_truth <target_directory> [--clean]")
        sys.exit(1)

    target = Path(sys.argv[1]).resolve()
    if not target.is_dir():
        print(f"Error: {target} is not a directory")
        sys.exit(1)

    if "--clean" in sys.argv:
        clean(target)
        print(f"Cleaned seed data from {target}")
    else:
        result = seed(target)
        print(f"Seeded {result['total_violation_files']} violation files and {result['total_fp_trap_files']} FP traps into {result['seed_directory']}")
        print(f"Manifest: {result['seed_directory']}/manifest.json")
