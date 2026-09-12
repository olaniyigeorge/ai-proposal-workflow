import sys, os

python311 = 'C:/Users/HomePC/AppData/Roaming/uv/python/cpython-3.11-windows-x86_64-none/python.exe'
print('trying', python311, 'exists=', os.path.exists(python311))
if os.path.exists(python311):
    # re-exec through the uv-managed python that has the project deps
    os.environ['SUPABASE_URL'] = 'https://placeholder.supabase.co'
    os.environ['SUPABASE_KEY'] = 'placeholder-key'
    os.environ['SUPABASE_JWT_SECRET'] = 'dev-jwt-secret'
    os.environ['DATABASE_URL'] = 'sqlite+aiosqlite:///:memory:'
    os.environ['ENVIRONMENT'] = 'testing'
    os.environ['WEBHOOK_SECRET'] = 'dev-webhook-secret'
    os.environ['RESEND_API_KEY'] = 're_placeholder'
    os.environ['EMAIL_FROM_ADDRESS'] = 'noreply@example.com'
    os.environ['EMAIL_FROM_NAME'] = 'Koya Talent'
    os.environ['CLAUDE_MODEL'] = 'claude-sonnet-5'
    os.environ['CLAUDE_MAX_TOKENS'] = '500'
    os.environ['CLAUDE_API_KEY'] = 'sk-placeholder'
    os.environ['PYTHONPATH'] = 'C:/Users/HomePC/dev/ai-proposal-workflow/backend'
    os.execv(python311, [python311, 'C:/Users/HomePC/dev/ai-proposal-workflow/backend/_boot_check.py'])
else:
    print('uv python not found')
