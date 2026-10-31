import ast
import os

files_to_check = [
    'bot/attack_engine.py',
    'bot/state_machine.py',
    'ai/troop_knowledge.py',
    'core/humanizer.py',
    'core/adb_client.py',
    'bot/wall_upgrader.py',
    'vision/ocr_reader.py'
]

class NameChecker(ast.NodeVisitor):
    def __init__(self, filename):
        self.filename = filename
        self.undefined = []
        self.scopes = [{}]
        
    def visit_FunctionDef(self, node):
        self.scopes.append({})
        self.generic_visit(node)
        self.scopes.pop()

    def visit_AsyncFunctionDef(self, node):
        self.scopes.append({})
        self.generic_visit(node)
        self.scopes.pop()

    def visit_ClassDef(self, node):
        self.scopes.append({})
        self.generic_visit(node)
        self.scopes.pop()

    def visit_Import(self, node):
        for alias in node.names:
            name = alias.asname or alias.name
            self.scopes[-1][name] = True

    def visit_ImportFrom(self, node):
        for alias in node.names:
            name = alias.asname or alias.name
            self.scopes[-1][name] = True

for path in files_to_check:
    if not os.path.exists(path):
        continue
    with open(path, 'r', encoding='utf-8') as f:
        src = f.read()
    try:
        tree = ast.parse(src, filename=path)
        print(f"[OK] Parsed {path} successfully without AST errors.")
    except Exception as e:
        print(f"[ERROR] In {path}: {e}")
