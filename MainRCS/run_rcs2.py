"""Trình khởi chạy cho PC RCS. Trong PyCharm: chuột phải vào file này -> Run.

    python run_rcs2.py                  chế độ thật (cần config/settings.json và config/sequences.json)
    python run_rcs2.py --demo --autorun robot mô phỏng + ATS giả, không cần phần cứng
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rcs2.ui.main import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
