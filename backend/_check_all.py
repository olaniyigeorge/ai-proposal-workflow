import ast, os, sys

root = "C:/Users/HomePC/dev/ai-proposal-workflow/backend"
problems = []
checked = 0
for p, _, files in os.walk(root):
    for f in files:
        if not f.endswith(".py"):
            continue
        full = os.path.join(p, f)
        if full.endswith("_check_imports.py") or full.endswith("_check_structure.py"):
            continue
        try:
            with open(full) as fh:
                ast.parse(fh.read())
            checked += 1
        except SyntaxError as e:
            problems.append(f"{full}: {e}")

print(f"checked {checked} py files")
if problems:
    print("SYNTAX PROBLEMS:")
    for pr in problems:
        print(pr)
else:
    print("OK — all backend .py files parse")
