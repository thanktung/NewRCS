"""Điểm vào. Chạy được cả dạng  `python -m rcs2`  lẫn khi chạy trực tiếp file này (nút "Run" của IDE)."""
import os
import sys

if __package__ in (None, ""):
    # chạy như script thường: cho phép import thư mục gốc dự án và dùng import tuyệt đối
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from rcs2.ui.main import main
else:
    from .ui.main import main

if __name__ == "__main__":
    sys.exit(main())
