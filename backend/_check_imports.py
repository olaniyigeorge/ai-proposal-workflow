import sys, os

python311 = 'C:/Users/HomePC/AppData/Roaming/uv/python/cpython-3.11-windows-x86_64-none/python.exe'
print('trying', python311, 'exists=', os.path.exists(python311))
if os.path.exists(python311):
    os.execv(python311, [python311, '-c', (
        'import sys; '
        'sys.path.insert(0, "C:/Users/HomePC/dev/ai-proposal-workflow/backend"); '
        'import app.domain.exceptions as e; '
        'print("ClientResponseError:", e.ClientResponseError); '
        'print("FeedbackError:", e.FeedbackError); '
        'from app.models.client_feedback import ClientResponseType, FeedbackCategory; '
        'print("ClientResponseType:", [x.value for x in ClientResponseType]); '
        'print("FeedbackCategory:", [x.value for x in FeedbackCategory]); '
        'from app.schemas.extended import ClientResponseRequest, FeedbackEntryRequest; '
        'print("ClientResponseRequest imported OK"); '
        'print("FeedbackEntryRequest imported OK")'
    )])
