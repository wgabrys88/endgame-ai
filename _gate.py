import sys, json, py_compile
f = sys.argv[1]
if f.endswith('.py'):
    py_compile.compile(f, doraise=True)
elif f.endswith('.json'):
    json.load(open(f, encoding='utf-8'))
