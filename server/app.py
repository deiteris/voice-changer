import os
import sys
from const import ROOT_PATH
# NOTE: This is required to fix current working directory on macOS
os.chdir(ROOT_PATH)
if sys.platform == 'darwin':
    # Enable fallback to CPU since some operations may be not supported by MPS.
    os.environ['PYTORCH_ENABLE_MPS_FALLBACK'] = '1'
# Reset CUDA_PATH since all libraries are already bundled.
# Existing CUDA installations may be incompatible with PyTorch or ONNX runtime
os.environ['CUDA_PATH'] = ''
os.environ['CUDNN_PATH'] = ''
# Fix high CPU usage caused by faiss-cpu for AMD CPUs.
# https://github.com/facebookresearch/faiss/issues/53#issuecomment-288351188
os.environ['OMP_WAIT_POLICY'] = 'PASSIVE'

import torch
torch.set_float32_matmul_precision('high')
torch.backends.cuda.matmul.allow_tf32 = True
torch.backends.cudnn.allow_tf32 = True

from voice_changer.VoiceChangerManager import VoiceChangerManager
from sio.MMVC_SocketIOApp import MMVC_SocketIOApp
from restapi.MMVC_Rest import MMVC_Rest

voice_changer_manager = VoiceChangerManager()
fastapi = MMVC_Rest.get_instance(voice_changer_manager)
socketio = MMVC_SocketIOApp.get_instance(fastapi, voice_changer_manager)

# NOTE: Bundled executable overrides excepthook to pause on exception during startup.
# Here we revert to original excepthook once all initialization is done.
sys.excepthook = sys.__excepthook__
