import json
import os
import sys
import shutil
import threading
import numpy as np
import torch
import soundfile as sf
from io import BytesIO, FileIO
from librosa import to_mono
from downloader.SampleDownloader import downloadSample, getSampleInfos
from mods.log_control import VoiceChangaerLogger
from voice_changer.Local.ServerDevice import ServerDevice, ServerDeviceCallbacks
from voice_changer.ModelSlotManager import ModelSlotManager
from voice_changer.RVC.RVCModelMerger import RVCModelMerger
from const import STORED_SETTING_FILE, STORED_SETTINGS, UPLOAD_DIR
from voice_changer.VoiceChangerV2 import VoiceChangerV2
from voice_changer.utils.LoadModelParams import LoadModelParamFile, LoadModelParams
from voice_changer.utils.ModelMerger import MergeElement, ModelMergerRequest
from voice_changer.utils.VoiceChangerModel import AudioInOut
from settings import ServerSettings
from dataclasses import dataclass, asdict, field
from voice_changer.common.deviceManager.DeviceManager import DeviceManager

# import threading
from typing import Callable
from typing import Any
import re

logger = VoiceChangaerLogger.get_instance().getLogger()


@dataclass()
class GPUInfo:
    id: int
    name: str
    memory: int


@dataclass()
class VoiceChangerManagerSettings:
    modelSlotIndex: int = -1
    passThrough: bool = False  # 0: off, 1: on
    # ↓mutableな物だけ列挙
    boolData: list[str] = field(default_factory=lambda: ["passThrough"])
    intData: list[str] = field(
        default_factory=lambda: [
            "modelSlotIndex",
            "gpu"
        ]
    )


class VoiceChangerManager(ServerDeviceCallbacks):
    _instance = None

    ############################
    # ServerDeviceCallbacks
    ############################
    def on_request(self, unpackedData: AudioInOut):
        return self.changeVoice(unpackedData)

    def emitTo(self, performance: list[float]):
        self.emitToFunc(performance)

    def get_processing_sampling_rate(self):
        return self.voiceChanger.get_processing_sampling_rate()

    def setInputSamplingRate(self, sr: int):
        self.voiceChanger.setInputSampleRate(sr)

    def setOutputSamplingRate(self, sr: int):
        self.voiceChanger.setOutputSampleRate(sr)

    ############################
    # VoiceChangerManager
    ############################
    def __init__(self, params: ServerSettings):
        logger.info("[Voice Changer] VoiceChangerManager initializing...")
        self.params = params
        self.voiceChanger: VoiceChangerV2 = None
        self.voiceChangerModel = None
        self.settings: VoiceChangerManagerSettings = VoiceChangerManagerSettings()

        self.modelSlotManager = ModelSlotManager.get_instance(self.params.model_dir)
        # スタティックな情報を収集
        self.gpus: list[GPUInfo] = self._get_gpuInfos()

        self.serverDevice = ServerDevice(self)

        thread = threading.Thread(target=self.serverDevice.start, args=())
        thread.start()

        # 設定保存用情報
        self.current_model_index = -1
        self.stored_setting: dict[str, str | int | float] = {}
        if os.path.exists(STORED_SETTING_FILE):
            self.stored_setting = json.load(open(STORED_SETTING_FILE, "r", encoding="utf-8"))
        if 'version' not in self.stored_setting:
            if 'crossFadeOverlapSize' in self.stored_setting:
                self.update_settings('crossFadeOverlapSize', "0.10")
            if 'extraConvertSize' in self.stored_setting:
                self.update_settings('extraConvertSize', "0.5")
            self.update_settings("version", 1)
        if "modelSlotIndex" in self.stored_setting:
            self.update_settings("modelSlotIndex", self.stored_setting["modelSlotIndex"])
        # キャッシュ設定の反映
        for k, v in self.stored_setting.items():
            if k != "modelSlotIndex":
                self.update_settings(k, v)
        if "gpu" not in self.stored_setting:
            self.update_settings("gpu", -1)
        logger.info("[Voice Changer] VoiceChangerManager initializing... done.")

    def store_setting(self, key: str, val: str | int | float):
        if key in STORED_SETTINGS:
            self.stored_setting[key] = val
            json.dump(self.stored_setting, open(STORED_SETTING_FILE, "w"))

    def _get_gpuInfos(self):
        return DeviceManager.list_devices()

    @classmethod
    def get_instance(cls, params: ServerSettings):
        if cls._instance is None:
            cls._instance = cls(params)
        return cls._instance

    async def load_model(self, params: LoadModelParams):
        if params.isSampleMode:
            # サンプルダウンロード
            logger.info(f"[Voice Changer] sample download...., {params}")
            await downloadSample(self.params.sample_mode, params.sampleId, self.params.model_dir, params.slot, params.params)
            self.modelSlotManager.getAllSlotInfo(reload=True)
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
            logger.info(f"move to {srcPath} -> {dstPath}")
            shutil.move(srcPath, dstPath)
            file.name = os.path.basename(dstPath)

        # メタデータ作成(各VCで定義)
        if params.voiceChangerType == "RVC":
            from voice_changer.RVC.RVCModelSlotGenerator import RVCModelSlotGenerator  # 起動時にインポートするとパラメータが取れない。

            slotInfo = RVCModelSlotGenerator.load_model(params)
            self.modelSlotManager.save_model_slot(params.slot, slotInfo)

        logger.info(f"params, {params}")

    def get_info(self):
        data = asdict(self.settings)
        data["gpus"] = self.gpus
        data["modelSlots"] = self.modelSlotManager.getAllSlotInfo(reload=True)
        data["sampleModels"] = getSampleInfos(self.params.sample_mode)
        data["python"] = sys.version
        data["voiceChangerParams"] = self.params

        data["status"] = "OK"

        info = self.serverDevice.get_info()
        data.update(info)

        if self.voiceChanger is not None:
            info = self.voiceChanger.get_info()
            data.update(info)

        return data

    def get_performance(self):
        if self.voiceChanger is not None:
            info = self.voiceChanger.get_performance()
            return info
        else:
            return {"status": "ERROR", "msg": "no model loaded"}

    def generateVoiceChanger(self, val: int):
        if self.current_model_index == val:
            return

        self.current_model_index = val
        slotInfo = self.modelSlotManager.get_slot_info(val)
        if slotInfo is None:
            logger.info(f"[Voice Changer] model slot is not found {val}")
            return

        if self.voiceChangerModel is not None and slotInfo.voiceChangerType == self.voiceChangerModel.voiceChangerType:
            self.voiceChangerModel.set_slot_info(slotInfo)
            self.voiceChanger.setModel(self.voiceChangerModel)
            self.voiceChangerModel.initialize()
            return

        if slotInfo.voiceChangerType == "RVC":
            logger.info("................RVC")
            from voice_changer.RVC.RVCr2 import RVCr2

            self.voiceChangerModel = RVCr2(self.params, slotInfo)
            self.voiceChanger = VoiceChangerV2(self.params)
            self.voiceChanger.setModel(self.voiceChangerModel)
        else:
            logger.info(f"[Voice Changer] unknown voice changer model: {slotInfo.voiceChangerType}")

    def update_settings(self, key: str, val: str | int | float | bool):
        self.store_setting(key, val)

        if key in self.settings.boolData:
            newVal = val == 'true'
            setattr(self.settings, key, newVal)
        elif key in self.settings.intData:
            newVal = int(val)
            if key == "modelSlotIndex":
                logger.info(f"[Voice Changer] model slot is changed {self.settings.modelSlotIndex} -> {newVal}")
                self.generateVoiceChanger(newVal)
            setattr(self.settings, key, newVal)

        self.serverDevice.update_settings(key, val)
        if self.voiceChanger is not None:
            self.voiceChanger.update_settings(key, val)

        return self.get_info()

    def convert(self, file: FileIO) -> bytes:
        if self.voiceChanger is None:
            logger.info("Voice Change is not loaded. Did you load a correct model?")
            return None

        data, in_sr = sf.read(file, dtype=np.float32)
        with torch.no_grad():
            output, out_sr = self.voiceChanger.convert(to_mono(data.T), in_sr)

        with BytesIO() as wav_io:
            sf.write(wav_io, output, out_sr, format='WAV')
            wav_io.seek(0)
            return wav_io.read()

    def changeVoice(self, receivedData: AudioInOut):
        if self.settings.passThrough:  # パススルー
            return receivedData, [0, 0, 0]

        if self.voiceChanger is None:
            logger.info("Voice Change is not loaded. Did you load a correct model?")
            return np.zeros(1, dtype=np.float32), [0, 0, 0]

        with torch.no_grad():
            return self.voiceChanger.on_request(receivedData)

    def export2onnx(self):
        return self.voiceChanger.export2onnx()

    async def merge_models(self, request: str):
        # self.voiceChanger.merge_models(request)
        req = json.loads(request)
        req = ModelMergerRequest(**req)
        req.files = [MergeElement(**f) for f in req.files]
        # Slots range is 0-499
        slot = len(self.modelSlotManager.getAllSlotInfo()) - 1
        if req.voiceChangerType == "RVC":
            merged = RVCModelMerger.merge_models(self.params, req, slot)
            loadParam = LoadModelParams(voiceChangerType="RVC", slot=slot, isSampleMode=False, sampleId="", files=[LoadModelParamFile(name=os.path.basename(merged), kind="rvcModel", dir="")], params={})
            await self.load_model(loadParam)
        return self.get_info()

    def setEmitTo(self, emitTo: Callable[[Any], None]):
        self.emitToFunc = emitTo

    def update_model_default(self):
        # self.voiceChanger.update_model_default()
        current_settings = self.voiceChangerModel.get_model_current()
        for current_setting in current_settings:
            current_setting["slot"] = self.settings.modelSlotIndex
            self.modelSlotManager.update_model_info(json.dumps(current_setting))
        return self.get_info()

    def update_model_info(self, newData: str):
        # self.voiceChanger.update_model_info(newData)
        self.modelSlotManager.update_model_info(newData)
        return self.get_info()

    def upload_model_assets(self, params: str):
        # self.voiceChanger.upload_model_assets(params)
        self.modelSlotManager.store_model_assets(params)
        return self.get_info()
