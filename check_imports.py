import sys
sys.path.insert(0, r"e:\talkfiesta\backend")

try:
    import app.main
    print("OK")
except Exception as e:
    import traceback
    traceback.print_exc()
    sys.exit(1)
