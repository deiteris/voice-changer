import os, sys 
import tempfile

frontend_path = os.path.join(sys._MEIPASS, "dist") if hasattr(sys, "_MEIPASS") else "../client/demo/dist"
ERROR_NO_ONNX_SESSION = "ERROR_NO_ONNX_SESSION"


tmpdir = tempfile.TemporaryDirectory()
# print("generate tmpdir:::",tmpdir)
SSL_KEY_DIR  = os.path.join(tmpdir.name, "keys") if hasattr(sys, "_MEIPASS") else "keys"
MODEL_DIR = os.path.join(tmpdir.name, "logs") if hasattr(sys, "_MEIPASS") else "logs"
UPLOAD_DIR = os.path.join(tmpdir.name, "upload_dir") if hasattr(sys, "_MEIPASS") else "upload_dir"
# SSL_KEY_DIR  = os.path.join(sys._MEIPASS, "keys") if hasattr(sys, "_MEIPASS") else "keys"
# MODEL_DIR = os.path.join(sys._MEIPASS, "logs") if hasattr(sys, "_MEIPASS") else "logs"
# UPLOAD_DIR = os.path.join(sys._MEIPASS, "upload_dir") if hasattr(sys, "_MEIPASS") else "upload_dir"
