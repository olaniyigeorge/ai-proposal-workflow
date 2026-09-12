import sys
sys.path.insert(0, "C:/Users/HomePC/dev/ai-proposal-workflow/backend")
import ast

files = [
    "app/schemas/extended.py",
    "app/services/feedback_service.py",
    "app/services/client_response_service.py",
    "app/services/proposal_filter_service.py",
    "app/domain/aidraft.py",
    "app/api/v1/endpoints/feedback.py",
    "app/api/v1/endpoints/client_feedback.py",
    "app/domain/exceptions.py",
    "app/models/client_feedback.py",
    "app/api/v1/api.py",
]

for f in files:
    with open(f) as fh:
        ast.parse(fh.read())
    print("parse OK:", f)

print("---- checking schema has expected classes ----")
with open("app/schemas/extended.py") as fh:
    src = fh.read()

for name in ["ClientResponseRecordResponse", "ClientPageMetaResponse",
             "FeedbackEntryResponse", "ProposalFilterParams", "KpiSummaryResponse",
             "ClientResponseRequest", "FeedbackEntryRequest"]:
    print(f"  {name} present:", name in src)

print("---- checking feedback_service function names ----")
with open("app/services/feedback_service.py") as fh:
    src = fh.read()
for name in ["submit_feedback", "list_feedback"]:
    print(f"  {name} present:", name in src)
