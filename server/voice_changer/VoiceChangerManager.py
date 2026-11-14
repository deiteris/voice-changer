import json
import os
import sys
import shutil
import numpy as np
from downloader.SampleDownloader import downloadSample, getSampleInfos
import logging
from voice_changer.Local.ServerAudio import ServerAudio, ServerAudioCallbacks
from voice_changer.ModelSlotManager import ModelSlotManager
from voice_changer.RVC.RVCModelMerger import RVCModelMerger
from const import STORED_SETTING_FILE, UPLOAD_DIR
from voice_changer.VoiceChangerSettings import VoiceChangerSettings
from voice_changer.VoiceChangerV2 import VoiceChangerV2
from voice_changer.utils.LoadModelParams import LoadModelParamFile, LoadModelParams
from voice_changer.utils.ModelMerger import MergeElement, ModelMergerRequest
from voice_changer.utils.VoiceChangerModel import AudioInOutFloat
from settings import get_settings
from voice_changer.common.deviceManager.DeviceManager import DeviceManager
from Exceptions import (
    PipelineNotInitializedException,
    VoiceChangerIsNotSelectedException,
)
from traceback import format_exc
from typing import Callable, Any

from voice_changer.RVC.RVCr2 import RVCr2
from voice_changer.RVC.RVCModelSlotGenerator import RVCModelSlotGenerator  # 起動時にインポートするとパラメータが取れない。

logger = logging.getLogger(__name__)


class VoiceChangerManager(ServerAudioCallbacks):
    _instance = None

    ############################
    # ServerDeviceCallbacks
    ############################
    def on_audio(self, unpackedData: AudioInOutFloat):
        return self.change_voice(unpackedData)

    def emit_to(self, volume: float, performance: list[float], err):
        self.emitToFunc(volume, performance, err)

    ############################
    # VoiceChangerManager
    ############################
    def __init__(self):
        logger.info("Initializing...")
        self.params = get_settings()

        self.modelSlotManager = ModelSlotManager.get_instance(self.params.model_dir)
        # スタティックな情報を収集

        self.settings = VoiceChangerSettings()
        try:
            with open(STORED_SETTING_FILE, "r", encoding="utf-8") as f:
                settings = json.load(f)
            self.settings.set_properties(settings)
        except:
            pass

        self.device_manager = DeviceManager.get_instance()
        self.devices = self.device_manager.list_devices()
        self.device_manager.initialize(self.settings.gpu, self.settings.forceFp32, self.settings.disableJit)

        self.vc = VoiceChangerV2(self.settings)
        self.server_audio = ServerAudio(self, self.settings)

        logger.info("Initialized.")

        # Initialize the voice changer
        self.initialize(self.settings.modelSlotIndex)

    def store_setting(self):
        with open(STORED_SETTING_FILE, "w") as f:
            json.dump(self.settings.to_dict_stateless(), f)

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def load_model(self, params: LoadModelParams):
        if params.isSampleMode:
            # サンプルダウンロード
            logger.info(f"Sample download.... {params}")
            await downloadSample(self.params.sample_mode, params.sampleId, self.params.model_dir, params.slot, params.params)
            self.modelSlotManager.getAllSlotInfo(reload=True)
            if params.slot == self.settings.modelSlotIndex:
                self.initialize(params.slot)
            info = {"status": "OK"}
            return info

        # アップローダ
        # ファイルをslotにコピー
        slotDir = os.path.join(
            self.params.model_dir,
            str(params.slot),
        )
        if os.path.isdir(slotDir):
            shutil.rmtree(slotDir)

        for file in params.files:
            logger.info(f"FILE: {file}")
            srcPath = os.path.join(UPLOAD_DIR, file.dir, file.name)
            dstDir = os.path.join(
                self.params.model_dir,
                str(params.slot),
                file.dir,
            )
            dstPath = os.path.join(dstDir, file.name)
            os.makedirs(dstDir, exist_ok=True)
            logger.info(f"Moving {srcPath} -> {dstPath}")
            shutil.move(srcPath, dstPath)
            file.name = os.path.basename(dstPath)

        # メタデータ作成(各VCで定義)
        if params.voiceChangerType == "RVC":
            slotInfo = RVCModelSlotGenerator.load_model(params)
            self.modelSlotManager.save_model_slot(params.slot, slotInfo)
            if params.slot == self.settings.modelSlotIndex:
                self.initialize(params.slot)

        logger.info(f"params, {params}")
        return {"status": "OK"}

    def get_info(self):
        data = self.settings.to_dict()
        data["gpus"] = self.devices
        data["modelSlots"] = self.modelSlotManager.getAllSlotInfo(reload=True)
        data["sampleModels"] = getSampleInfos(self.params.sample_mode)
        data["python"] = sys.version
        data["voiceChangerParams"] = self.params

        data["status"] = "OK"

        info = self.server_audio.get_info()
        data.update(info)

        info = self.vc.get_info()
        data.update(info)

        return data

    def initialize(self, val: int):
        slotInfo = self.modelSlotManager.get_slot_info(val)
        if slotInfo is None or slotInfo.voiceChangerType is None:
            logger.warning(f"Model slot is not found {val}")
            return

        self.settings.set_properties({
            'tran': slotInfo.defaultTune,
            'formantShift': slotInfo.defaultFormantShift,
            'indexRatio': slotInfo.defaultIndexRatio,
            'protect': slotInfo.defaultProtect
        })

        if slotInfo.voiceChangerType == self.vc.get_type():
            self.vc.set_slot_info(slotInfo)
        elif slotInfo.voiceChangerType == "RVC":
            logger.info("Loading RVC...")
            self.vc.initialize(RVCr2(slotInfo, self.settings))
        else:
            logger.error(f"Unknown voice changer model: {slotInfo.voiceChangerType}")

    def update_settings(self, key: str, val: Any):
        logger.info(f"update configuration {key}: {val}")
        error, old_value = self.settings.set_property(key, val)
        if error:
            return self.get_info()
        # TODO: This is required to get type-casted setting. But maybe this should be done prior to setting.
        val = self.settings.get_property(key)
        if old_value == val:
            return self.get_info()
        # TODO: Storing settings on each change is suboptimal. Maybe timed autosave?
        self.store_setting()

        if key == "modelSlotIndex":
            logger.info(f"Model slot is changed {old_value} -> {val}")
            self.initialize(val)
        elif key == 'gpu':
            self.device_manager.set_device(val)
        elif key == 'forceFp32':
            self.device_manager.set_force_fp32(val)
        elif key == 'disableJit':
            self.device_manager.set_disable_jit(val)
        # FIXME: This is a very counter-intuitive handling of audio modes...
        # Map "serverAudioSampleRate" to "inputSampleRate" and "outputSampleRate"
        # since server audio can have its sample rate configured.
        # Revert change in case we switched back to client audio mode.
        elif key == 'enableServerAudio':
            if val:
                self.update_settings('inputSampleRate', self.settings.serverAudioSampleRate)
                self.update_settings('outputSampleRate', self.settings.serverAudioSampleRate)
            else:
                self.update_settings('inputSampleRate', 48000)
                self.update_settings('outputSampleRate', 48000)
        elif key == 'serverAudioSampleRate':
            self.update_settings('inputSampleRate', self.settings.serverAudioSampleRate)
            self.update_settings('outputSampleRate', self.settings.serverAudioSampleRate)

        self.server_audio.update_settings(key, val, old_value)
        self.vc.update_settings(key, val, old_value)

        return self.get_info()

    def change_voice(self, receivedData: AudioInOutFloat) -> tuple[AudioInOutFloat, tuple, tuple | None]:
        if self.settings.passThrough:  # パススルー
            vol = float(np.sqrt(
                np.square(receivedData).mean(dtype=np.float32)
            ))
            return receivedData, vol, [0, 0, 0], None

        try:
            with self.device_manager.lock:
                audio, vol, perf = self.vc.on_request(receivedData)
            return audio, vol, perf, None
        except VoiceChangerIsNotSelectedException as e:
            logger.exception(e)
            return np.zeros(1, dtype=np.float32), 0, [0, 0, 0], ('VoiceChangerIsNotSelectedException', format_exc())
        except PipelineNotInitializedException as e:
            logger.exception(e)
            return np.zeros(1, dtype=np.float32), 0, [0, 0, 0], ('PipelineNotInitializedException', format_exc())
        except Exception as e:
            logger.exception(e)
            return np.zeros(1, dtype=np.float32), 0, [0, 0, 0], ('Exception', format_exc())

    def export2onnx(self):
        return self.vc.export2onnx()

    async def merge_models(self, request: str) -> str | None:
        # self.vc.merge_models(request)
        req = json.loads(request)
        req = ModelMergerRequest(**req)
        req.files = [MergeElement(**f) for f in req.files]
        # Slots range is 0-499
        slot = len(self.modelSlotManager.getAllSlotInfo()) - 1
        if req.voiceChangerType == "RVC":
            RVCModelMerger.merge_models(self.params, req, slot)
        return self.get_info()

    def setEmitTo(self, emitTo: Callable[[Any], None]):
        self.emitToFunc = emitTo

    def update_model_default(self):
        # self.vc.update_model_default()
        if self.settings.modelSlotIndex < 0:
            return self.get_info()
        current_settings = self.vc.get_current_model_settings()
        for setting in current_settings:
            self.modelSlotManager.update_model_info(self.settings.modelSlotIndex, **setting)
        return self.get_info()

    def update_model_info(self, newData: str):
        # self.vc.update_model_info(newData)
        data = json.loads(newData)
        self.modelSlotManager.update_model_info(int(data["slot"]), data["key"], data["val"])
        return self.get_info()

    def upload_model_assets(self, params: str):
        # self.vc.upload_model_assets(params)
        self.modelSlotManager.store_model_assets(params)
        return self.get_info()
