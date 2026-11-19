import json
import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
import os
import sys
import shutil
import tempfile
from pathlib import Path
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
from time import monotonic
from traceback import format_exc
from typing import Callable, Any

from voice_changer.RVC.RVCr2 import RVCr2
from voice_changer.RVC.RVCModelSlotGenerator import RVCModelSlotGenerator  # 起動時にインポートするとパラメータが取れない。

logger = logging.getLogger(__name__)


BROWSER_STREAM_IDLE_SECONDS = 10


class VoiceChangerManager(ServerAudioCallbacks):
    _instance = None

    ############################
    # ServerDeviceCallbacks
    ############################
    def on_audio(self, unpackedData: AudioInOutFloat):
        return self.change_voice(unpackedData, local_source=self.server_audio.stream_id)

    def emit_to(self, volume: float, performance: list[float], err):
        self.emitToFunc(volume, performance, err)

    ############################
    # VoiceChangerManager
    ############################
    def __init__(self):
        logger.info("Initializing...")
        self.params = get_settings()
        self._browser_stream: str | None = None
        self._last_browser_audio = 0.0
        self._audio_source = None
        self._model_load_lock = asyncio.Lock()
        self._settings_lock = threading.Lock()
        self._inference_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="voice-inference")

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

    def shutdown(self):
        try:
            with self._settings_lock:
                self.server_audio.stop()
        finally:
            self._inference_executor.shutdown(wait=True, cancel_futures=True)
            self.vc.io_recorder.close()

    def store_setting(self):
        temp_path = None
        try:
            directory = os.path.dirname(os.path.abspath(STORED_SETTING_FILE))
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=directory, delete=False) as f:
                temp_path = f.name
                json.dump(self.settings.to_dict_stateless(), f)
            os.replace(temp_path, STORED_SETTING_FILE)
        finally:
            if temp_path and os.path.exists(temp_path):
                os.remove(temp_path)

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def load_model(self, params: LoadModelParams):
        async with self._model_load_lock:
            return await self._load_model(params)

    async def _load_model(self, params: LoadModelParams):
        if type(params.slot) is not int or not 0 <= params.slot < len(self.modelSlotManager.getAllSlotInfo()):
            raise ValueError("Invalid model slot")
        if params.voiceChangerType != "RVC":
            raise ValueError("Unsupported voice changer type")

        model_root = Path(self.params.model_dir).resolve()
        model_root.mkdir(parents=True, exist_ok=True)
        slot_dir = model_root / str(params.slot)
        # A pre-existing slot symlink must not redirect replacement outside the model root.
        if slot_dir.is_symlink():
            raise ValueError("Model slot cannot be a symlink")
        with tempfile.TemporaryDirectory(prefix=".model-stage-", dir=model_root) as temp:
            stage_root = Path(temp)
            stage_slot = stage_root / str(params.slot)
            uploaded_sources = []
            if params.isSampleMode:
                await downloadSample(self.params.sample_mode, params.sampleId, str(stage_root), params.slot, params.params)
            else:
                stage_slot.mkdir()
                upload_root = Path(UPLOAD_DIR).resolve()
                names = set()
                if any(f.kind not in ("rvcModel", "rvcIndex") for f in params.files) or sum(f.kind == "rvcIndex" for f in params.files) > 1:
                    raise ValueError("Invalid model files")
                for file in params.files:
                    if not isinstance(file.name, str) or not file.name or Path(file.name).name != file.name or "\\" in file.name or file.name in (".", ".."):
                        raise ValueError("Invalid model filename")
                    source = (upload_root / file.dir / file.name).resolve()
                    if not source.is_relative_to(upload_root) or not source.is_file():
                        raise ValueError("Invalid uploaded model path")
                    if file.name.lower() == "params.json":
                        raise ValueError("Reserved model filename")
                    if file.name in names:
                        raise ValueError("Duplicate model filename")
                    names.add(file.name)
                    uploaded_sources.append(source)
                    shutil.copy2(source, stage_slot / file.name)
                if sum(f.kind == "rvcModel" for f in params.files) != 1:
                    raise ValueError("Exactly one RVC model is required")
                slot_info = RVCModelSlotGenerator.load_model(params, str(stage_root))
                from data.ModelSlot import saveSlotInfo
                saveSlotInfo(str(stage_root), params.slot, slot_info)

            def commit_model():
                with self.device_manager.lock:
                    backup = stage_root / "previous"
                    had_slot = slot_dir.exists()
                    if had_slot:
                        os.replace(slot_dir, backup)
                    try:
                        os.replace(stage_slot, slot_dir)
                        self.modelSlotManager.getAllSlotInfo(reload=True)
                        if params.slot == self.settings.modelSlotIndex:
                            slot_info = self.modelSlotManager.get_slot_info(params.slot)
                            defaults = {"tran": slot_info.defaultTune, "formantShift": slot_info.defaultFormantShift,
                                        "indexRatio": slot_info.defaultIndexRatio, "protect": slot_info.defaultProtect}
                            old_defaults = {key: self.settings.get_property(key) for key in defaults}
                            try:
                                self.settings.set_properties(defaults)
                                candidate = RVCr2(slot_info, self.settings)
                                candidate.realloc(self.vc.block_frame, self.vc.extra_frame, self.vc.crossfade_frame, self.vc.sola_search_frame)
                                candidate.initialize()
                                if candidate.pipeline is None:
                                    raise RuntimeError("Failed to initialize model pipeline")
                                self.vc.vcmodel = candidate
                            except Exception:
                                self.settings.set_properties(old_defaults)
                                raise
                    except Exception:
                        if slot_dir.exists():
                            shutil.rmtree(slot_dir)
                        if had_slot:
                            os.replace(backup, slot_dir)
                        self.modelSlotManager.getAllSlotInfo(reload=True)
                        raise
            commit_task = asyncio.create_task(asyncio.to_thread(commit_model))
            try:
                await asyncio.shield(commit_task)
            except asyncio.CancelledError:
                # Keep the staging directory alive until the worker is done.
                await commit_task
                raise
            for source in uploaded_sources:
                try:
                    source.unlink()
                except OSError:
                    logger.warning("Could not remove accepted uploaded file: %s", source)
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
        # Serialize updates through stream restarts without holding the inference lock
        # while PortAudio waits for a callback to finish.
        with self._settings_lock:
            with self.device_manager.lock:
                audio_updates = []
                self._update_settings_locked(key, val, audio_updates)
            for update in audio_updates:
                self.server_audio.update_settings(*update)
        return self.get_info()

    def _select_model(self, index: int):
        old_index = self.settings.modelSlotIndex
        active_model = self.vc.vcmodel
        if index == old_index and (index == -1 or (active_model is not None and active_model.pipeline is not None)):
            return

        candidate = None
        defaults = {}
        if index != -1:
            slot = self.modelSlotManager.get_slot_info(index)
            if slot is None or slot.voiceChangerType != 'RVC':
                raise ValueError("Invalid model slot")
            defaults = {'tran': slot.defaultTune, 'formantShift': slot.defaultFormantShift,
                        'indexRatio': slot.defaultIndexRatio, 'protect': slot.defaultProtect}
            candidate = RVCr2(slot, self.settings)
            candidate.realloc(self.vc.block_frame, self.vc.extra_frame, self.vc.crossfade_frame, self.vc.sola_search_frame)
            candidate.initialize()
            if candidate.pipeline is None:
                raise RuntimeError("Failed to initialize model pipeline")

        old_defaults = {key: self.settings.get_property(key) for key in defaults}
        try:
            self.settings.set_properties(defaults)
            self.settings.set_property('modelSlotIndex', index)
            self.store_setting()
        except Exception:
            self.settings.set_properties(old_defaults)
            self.settings.set_property('modelSlotIndex', old_index)
            raise
        self.vc.vcmodel = candidate
        if self.vc.sola_buffer is not None:
            self.vc.sola_buffer.zero_()

    def _update_settings_locked(self, key: str, val: Any, audio_updates: list):
        logger.info(f"update configuration {key}: {val}")
        if key == 'modelSlotIndex':
            self._select_model(int(val))
            return
        if key in {'inputSampleRate', 'outputSampleRate', 'serverAudioSampleRate',
                   'serverInputAudioSampleRate', 'serverOutputAudioSampleRate', 'serverMonitorAudioSampleRate'}:
            if int(val) <= 0:
                raise ValueError("Sample rate must be positive")
        elif key == 'gpu' and int(val) not in {device['id'] for device in self.devices}:
            raise ValueError("Unknown GPU device")
        error, old_value = self.settings.set_property(key, val)
        if error:
            raise ValueError(f"Unknown or immutable setting: {key}")
        # TODO: This is required to get type-casted setting. But maybe this should be done prior to setting.
        val = self.settings.get_property(key)
        if old_value == val:
            return
        # TODO: Storing settings on each change is suboptimal. Maybe timed autosave?
        try:
            self.store_setting()
        except Exception:
            # Boolean settings accept the string values used by the client.
            restore_value = str(old_value).lower() if isinstance(old_value, bool) else old_value
            self.settings.set_property(key, restore_value)
            raise

        if key == 'gpu':
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
                self._update_settings_locked('inputSampleRate', self.settings.serverAudioSampleRate, audio_updates)
                self._update_settings_locked('outputSampleRate', self.settings.serverAudioSampleRate, audio_updates)
            else:
                self._update_settings_locked('inputSampleRate', 48000, audio_updates)
                self._update_settings_locked('outputSampleRate', 48000, audio_updates)
        elif key == 'serverAudioSampleRate':
            self._update_settings_locked('inputSampleRate', self.settings.serverAudioSampleRate, audio_updates)
            self._update_settings_locked('outputSampleRate', self.settings.serverAudioSampleRate, audio_updates)

        self.vc.update_settings(key, val, old_value)
        audio_updates.append((key, val, old_value))

    def set_browser_stream(self, stream_id: str, active: bool) -> bool:
        with self.device_manager.lock:
            if not active:
                if self._browser_stream == stream_id:
                    self._browser_stream = None
                    self._audio_source = None
                return True

            now = monotonic()
            busy = self._browser_stream is not None and now - self._last_browser_audio < BROWSER_STREAM_IDLE_SECONDS
            if self.settings.enableServerAudio or self.server_audio.running or (busy and self._browser_stream != stream_id):
                return False
            self._browser_stream = stream_id
            self._last_browser_audio = now
            self._audio_source = None
            return True

    def change_voice(
        self,
        receivedData: AudioInOutFloat,
        stream_id: str | None = None,
        legacy_socket: str | None = None,
        *,
        local_source: object | None = None,
    ):
        try:
            with self.device_manager.lock:
                if local_source is not None:
                    source = local_source
                else:
                    now = monotonic()
                    if self.settings.enableServerAudio or self.server_audio.running:
                        return np.zeros(1, dtype=np.float32), 0, [0, 0, 0], (
                            'STREAM_INACTIVE', 'Server audio owns voice conversion.')
                    if stream_id is not None:
                        if stream_id != self._browser_stream:
                            return np.zeros(1, dtype=np.float32), 0, [0, 0, 0], (
                                'STREAM_INACTIVE', 'This stream no longer owns voice conversion. Stop and start again.')
                        self._last_browser_audio = now
                        source = stream_id
                    else:
                        if self._browser_stream is not None and now - self._last_browser_audio < BROWSER_STREAM_IDLE_SECONDS:
                            return np.zeros(1, dtype=np.float32), 0, [0, 0, 0], (
                                'STREAM_INACTIVE', 'Another browser is using voice conversion.')
                        self._browser_stream = None
                        # Legacy REST packets have no stream identity. Give each packet fresh history.
                        source = ('socket', legacy_socket) if legacy_socket is not None else object()

                if self._audio_source != source:
                    self.vc.reset_stream()
                    self._audio_source = source
                if self.settings.passThrough:
                    vol = float(np.sqrt(np.square(receivedData).mean(dtype=np.float32)))
                    return receivedData, vol, [0, 0, 0], None
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

    async def change_voice_async(self, receivedData: AudioInOutFloat, stream_id: str | None = None, legacy_socket: str | None = None):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(self._inference_executor, self.change_voice, receivedData, stream_id, legacy_socket)

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
