from typing import Any, Union

from torch.functional import F
import torch
import numpy as np
import logging
from const import VoiceChangerType
from data.ModelSlot import ModelSlots

from voice_changer.IORecorder import IORecorder
from voice_changer.VoiceChangerSettings import VoiceChangerSettings
from voice_changer.utils.Timer import Timer2
from voice_changer.utils.VoiceChangerModel import AudioInOutFloat, VoiceChangerModel
from Exceptions import (
    VoiceChangerIsNotSelectedException,
)
from voice_changer.common.deviceManager.DeviceManager import DeviceManager

logger = logging.getLogger(__name__)

class VoiceChangerV2:
    def __init__(self, settings: VoiceChangerSettings):
        # 初期化
        self.settings = settings

        self.block_frame = self.settings.serverReadChunkSize * 128
        self.crossfade_frame = int(self.settings.crossFadeOverlapSize * self.settings.inputSampleRate)
        self.extra_frame = int(self.settings.extraConvertSize * self.settings.inputSampleRate)
        self.sola_search_frame = self.settings.inputSampleRate // 100

        self.vcmodel: VoiceChangerModel | None = None
        self.device_manager = DeviceManager.get_instance()
        self.sola_buffer: torch.Tensor | None = None
        self.io_recorder = IORecorder()
        if self.settings.recordIO:
            self.io_recorder.open(
                self.settings.inputSampleRate,
                self.settings.outputSampleRate,
            )
        self._generate_strength()

    def initialize(self, vcmodel: VoiceChangerModel):
        self.vcmodel = vcmodel
        self.vcmodel.realloc(self.block_frame, self.extra_frame, self.crossfade_frame, self.sola_search_frame)
        self.vcmodel.initialize()

    def set_slot_info(self, slot_info: ModelSlots):
        if self.vcmodel is not None:
            self.vcmodel.set_slot_info(slot_info)
            self.vcmodel.initialize()

    def get_type(self) -> VoiceChangerType:
        if self.vcmodel is None:
            return "None"
        return self.vcmodel.voiceChangerType

    def set_input_sample_rate(self):
        if self.settings.recordIO:
            self.io_recorder.open(self.settings.inputSampleRate, self.settings.outputSampleRate)

        self.extra_frame = int(self.settings.extraConvertSize * self.settings.inputSampleRate)
        self.crossfade_frame = int(self.settings.crossFadeOverlapSize * self.settings.inputSampleRate)
        self.sola_search_frame = self.settings.inputSampleRate // 100
        self._generate_strength()

        if self.vcmodel is not None:
            self.vcmodel.set_sampling_rate(self.settings.inputSampleRate, self.settings.outputSampleRate)
            self.vcmodel.realloc(self.block_frame, self.extra_frame, self.crossfade_frame, self.sola_search_frame)

    def set_output_sample_rate(self):
        if self.settings.recordIO:
            self.io_recorder.open(self.settings.inputSampleRate, self.settings.outputSampleRate)

        if self.vcmodel is not None:
            self.vcmodel.set_sampling_rate(self.settings.inputSampleRate, self.settings.outputSampleRate)

    def get_info(self):
        if self.vcmodel is not None:
            return self.vcmodel.get_info()
        return {}

    def update_settings(self, key: str, val: Any, old_val: Any):
        if key == "serverReadChunkSize":
            self.block_frame = self.settings.serverReadChunkSize * 128
        elif key == 'gpu':
            # When changing GPU, need to re-allocate fade-in/fade-out buffers on different device
            self._generate_strength()
        elif key == "inputSampleRate":
            self.set_input_sample_rate()
        elif key == "outputSampleRate":
            self.set_output_sample_rate()
        elif key == 'extraConvertSize':
            self.extra_frame = int(val * self.settings.inputSampleRate)
        elif key == 'crossFadeOverlapSize':
            self.crossfade_frame = int(val * self.settings.inputSampleRate)
            self._generate_strength()
        elif key == 'recordIO':
            if val:
                self.io_recorder.open(self.settings.inputSampleRate, self.settings.outputSampleRate)
            else:
                self.io_recorder.close()

        if self.vcmodel is not None:
            self.vcmodel.update_settings(key, val, old_val)
            if key in {'gpu', 'serverReadChunkSize', 'extraConvertSize', 'crossFadeOverlapSize', 'silenceFront', 'forceFp32'}:
                self.vcmodel.realloc(self.block_frame, self.extra_frame, self.crossfade_frame, self.sola_search_frame)


    def _generate_strength(self):
        self.fade_in_window: torch.Tensor = (
            torch.sin(
                0.5
                * np.pi
                * torch.linspace(
                    0.0,
                    1.0,
                    steps=self.crossfade_frame,
                    device=self.device_manager.device,
                    dtype=torch.float32,
                )
            )
            ** 2
        )
        self.fade_out_window: torch.Tensor = 1 - self.fade_in_window

        # ひとつ前の結果とサイズが変わるため、記録は消去する。
        self.sola_buffer = torch.zeros(self.crossfade_frame, device=self.device_manager.device, dtype=torch.float32)
        self.sola_ones = torch.ones(1, 1, self.crossfade_frame, device=self.device_manager.device, dtype=torch.float32)
        logger.info(f'Allocated SOLA buffer size: {self.crossfade_frame}')

    def get_processing_sampling_rate(self) -> int:
        if self.vcmodel is None:
            return 0
        return self.vcmodel.get_processing_sampling_rate()

    def reset_stream(self):
        if self.sola_buffer is not None:
            self.sola_buffer.zero_()
        if self.vcmodel is not None:
            self.vcmodel.reset_stream()

    def process_audio(self, audio_in: AudioInOutFloat) -> tuple[AudioInOutFloat, float]:
        block_size = audio_in.shape[0]

        audio, vol = self.vcmodel.inference(audio_in)

        if audio is None:
            # In case there's an actual silence - send full block with zeros
            return np.zeros(block_size, dtype=np.float32), vol

        # SOLA algorithm from https://github.com/yxlllc/DDSP-SVC, https://github.com/liujing04/Retrieval-based-Voice-Conversion-WebUI
        conv_input = audio[
            None, None, : self.crossfade_frame + self.sola_search_frame
        ]
        cor_nom = F.conv1d(conv_input, self.sola_buffer[None, None, :])
        cor_den = torch.sqrt(
            F.conv1d(
                conv_input ** 2,
                self.sola_ones,
            )
            + 1e-8
        )
        sola_offset = torch.argmax(cor_nom[0, 0] / cor_den[0, 0])

        audio = audio[sola_offset:]
        audio[: self.crossfade_frame] *= self.fade_in_window
        audio[: self.crossfade_frame] += (
            self.sola_buffer * self.fade_out_window
        )

        self.sola_buffer[:] = audio[block_size : block_size + self.crossfade_frame]

        return audio[: block_size].detach().cpu().numpy(), vol

    @torch.no_grad()
    def on_request(self, audio_in: AudioInOutFloat) -> tuple[AudioInOutFloat, list[Union[int, float]]]:
        if self.vcmodel is None:
            raise VoiceChangerIsNotSelectedException("Voice Changer is not selected.")

        with Timer2("main-process", True) as t:
            result, vol = self.process_audio(audio_in)

        mainprocess_time = t.secs

        # 後処理
        if self.settings.recordIO and self.io_recorder.fi is not None and self.io_recorder.fo is not None:
            self.io_recorder.write_input((audio_in * 32767).astype(np.int16).tobytes())
            self.io_recorder.write_output((result * 32767).astype(np.int16).tobytes())

        return result, vol, [0, mainprocess_time, 0]

    @torch.no_grad()
    def export2onnx(self):
        if self.vcmodel is None:
            return None
        return self.vcmodel.export2onnx()

    def get_current_model_settings(self) -> list[dict]:
        if self.vcmodel is None:
            return []
        return self.vcmodel.get_model_current()
