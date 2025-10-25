# main.py
import sys, platform
print("✅ Python is running!")
print(f"Python: {platform.python_version()}  ({sys.executable})")

# ライブラリの存在チェック
try:
    import numpy as np
    import pandas as pd
    import lightgbm as lgb
    import sklearn
    print("✅ libs OK:",
          f"numpy {np.__version__}, pandas {pd.__version__},",
          f"lightgbm {lgb.__version__}, scikit-learn {sklearn.__version__}")
except Exception as e:
    print("⚠️ ライブラリ読み込みエラー:", e)
    sys.exit(1)