#!/bin/bash
set -euo pipefail
cd "C:/Users/HomePC/dev/ai-proposal-workflow/backend"
PYTHON="C:/Users/HomePC/AppData/Local/hermes/hermes-agent/venv/Scripts/python.exe"
export SUPABASE_URL="https://placeholder.supabase.co"
export SUPABASE_KEY="placeholder-key"
export SUPABASE_JWT_SECRET="dev-jwt-secret"
export DATABASE_URL="sqlite+aiosqlite:///:memory:"
export ENVIRONMENT="testing"
export WEBHOOK_SECRET="dev-webhook-secret"
export RESEND_API_KEY="re_placeholder"
export EMAIL_FROM_ADDRESS="noreply@example.com"
export EMAIL_FROM_NAME="Koya Talent"
export CLAUDE_MODEL="claude-sonnet-5"
export CLAUDE_MAX_TOKENS="500"
export CLAUDE_API_KEY="sk-placeholder"
export PYTHONPATH="."
"$PYTHON" _boot_check.py
rm -f _boot_check.py _boot_launcher.py _check_all.py _check_imports.py _check_structure.py
