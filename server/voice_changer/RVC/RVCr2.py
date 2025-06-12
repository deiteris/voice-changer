"""
VoiceChangerV2向け
"""
import torch
from data.ModelSlot import RVCModelSlot, saveSlotInfo
from const import EnumInferenceTypes
import logging
import os
from voice_changer.embedder.EmbedderManager import EmbedderManager
from voice_changer.utils.VoiceChangerModel import (
    AudioInOutFloat,
    VoiceChangerModel,
)
from voice_changer.RVC.consts import HUBERT_SAMPLE_RATE, WINDOW_SIZE
from voice_changer.RVC.onnx_exporter.export2onnx import export2onnx
from voice_changer.pitch_extractor.PitchExtractorManager import PitchExtractorManager
from voice_changer.RVC.pipeline.PipelineGenerator import createPipeline
from voice_changer.common.TorchUtils import circular_write
from voice_changer.common.deviceManager.DeviceManager import DeviceManager
from voice_changer.RVC.pipeline.Pipeline import Pipeline
from torchaudio import transforms as tat
from voice_changer.VoiceChangerSettings import VoiceChangerSettings
from settings import get_settings
from Exceptions import (
    PipelineNotInitializedException,
)

logger = logging.getLogger(__name__)


class RVCr2(VoiceChangerModel):
    def __init__(self, slotInfo: RVCModelSlot, settings: VoiceChangerSettings):
        self.voiceChangerType = "RVC"

        self.device_manager = DeviceManager.get_instance()
        EmbedderManager.initialize()
        PitchExtractorManager.initialize()
        self.settings = settings
        self.params = get_settings()

        self.pipeline: Pipeline | None = None

        self.convert_buffer: torch.Tensor | None = None
        self.pitch_buffer: torch.Tensor | None = None
        self.pitchf_buffer: torch.Tensor | None = None
        self.return_length = 0
        self.skip_head = 0
        self.silence_front = 0
        self.slotInfo = slotInfo

        self.resampler_in: tat.Resample | None = None
        self.resampler_out: tat.Resample | None = None

        self.input_sample_rate = self.settings.inputSampleRate
        self.output_sample_rate = self.settings.outputSampleRate

        # Convert dB to RMS
        self.inputSensitivity = 10 ** (self.settings.silentThreshold / 20)

        self.is_half = self.device_manager.use_fp16()
        self.dtype = torch.float16 if self.is_half else torch.float32

    def initialize(self, force_reload: bool = False):
        logger.info("Initializing...")

        if self.settings.useONNX and not self.slotInfo.modelFileOnnx:
            self.export2onnx()

        # pipelineの生成
        try:
            self.pipeline = createPipeline(
                self.slotInfo, self.settings.f0Detector, self.settings.useONNX, force_reload
            )
        except Exception as e:  # NOQA
            logger.error("Failed to create pipeline.")
            logger.exception(e)
            return

        # 処理は16Kで実施(Pitch, embed, (infer))
        self.resampler_in = tat.Resample(
            orig_freq=self.input_sample_rate,
            new_freq=HUBERT_SAMPLE_RATE,
            dtype=torch.float32
        ).to(self.device_manager.device)

        self.resampler_out = tat.Resample(
            orig_freq=self.slotInfo.samplingRate,
            new_freq=self.output_sample_rate,
            dtype=torch.float32
        ).to(self.device_manager.device)

        logger.info("Initialized.")

    def set_sampling_rate(self, input_sample_rate: int, output_sample_rate: int):
        if self.input_sample_rate != input_sample_rate:
            self.input_sample_rate = input_sample_rate
            self.resampler_in = tat.Resample(
                orig_freq=self.input_sample_rate,
                new_freq=HUBERT_SAMPLE_RATE,
                dtype=torch.float32
            ).to(self.device_manager.device)
        if self.output_sample_rate != output_sample_rate:
            self.output_sample_rate = output_sample_rate
            self.resampler_out = tat.Resample(
                orig_freq=self.slotInfo.samplingRate,
                new_freq=self.output_sample_rate,
                dtype=torch.float32
            ).to(self.device_manager.device)

    def change_pitch_extractor(self):
        pitchExtractor = PitchExtractorManager.getPitchExtractor(
            self.settings.f0Detector, self.settings.gpu
        )
        self.pipeline.setPitchExtractor(pitchExtractor)

    def update_settings(self, key: str, val, old_val):
        if key in {"gpu", "forceFp32", "disableJit"}:
            self.is_half = self.device_manager.use_fp16()
            self.dtype = torch.float16 if self.is_half else torch.float32
            self.initialize(True)
        elif key == 'useONNX':
            self.initialize()
        elif key == "f0Detector" and self.pipeline is not None:
            self.change_pitch_extractor()
        elif key == 'silentThreshold':
            # Convert dB to RMS
            self.inputSensitivity = 10 ** (self.settings.silentThreshold / 20)

    def set_slot_info(self, slotInfo: RVCModelSlot):
        self.slotInfo = slotInfo

    def get_info(self):
        data = {}
        if self.pipeline is not None:
            pipelineInfo = self.pipeline.getPipelineInfo()
            data["pipelineInfo"] = pipelineInfo
        else:
            data["pipelineInfo"] = "None"
        return data

    def get_processing_sampling_rate(self):
        return self.slotInfo.samplingRate

    def realloc(self, block_frame: int, extra_frame: int, crossfade_frame: int, sola_search_frame: int):
        # Calculate frame sizes based on DEVICE sample rate (f.e., 48000Hz) and convert to 16000Hz
        block_frame_16k = int(block_frame / self.input_sample_rate * HUBERT_SAMPLE_RATE)
        crossfade_frame_16k = int(crossfade_frame / self.input_sample_rate * HUBERT_SAMPLE_RATE)
        sola_search_frame_16k = int(sola_search_frame / self.input_sample_rate * HUBERT_SAMPLE_RATE)
        extra_frame_16k = int(extra_frame / self.input_sample_rate * HUBERT_SAMPLE_RATE)

        convert_size_16k = block_frame_16k + sola_search_frame_16k + extra_frame_16k + crossfade_frame_16k
        if (modulo := convert_size_16k % WINDOW_SIZE) != 0:  # モデルの出力のホップサイズで切り捨てが発生するので補う。
            convert_size_16k = convert_size_16k + (WINDOW_SIZE - modulo)
        self.convert_feature_size_16k = convert_size_16k // WINDOW_SIZE

        self.skip_head = extra_frame_16k // WINDOW_SIZE
        self.return_length = self.convert_feature_size_16k - self.skip_head
        self.silence_front = extra_frame_16k - (WINDOW_SIZE * 5) if self.settings.silenceFront else 0

        # Audio buffer to measure volume between chunks
        audio_buffer_size = block_frame_16k + crossfade_frame_16k
        self.audio_buffer = torch.zeros(audio_buffer_size, dtype=self.dtype, device=self.device_manager.device)

        # Audio buffer for conversion without silence
        self.convert_buffer = torch.zeros(convert_size_16k, dtype=self.dtype, device=self.device_manager.device)
        # Additional +1 is to compensate for pitch extraction algorithm
        # that can output additional feature.
        self.pitch_buffer = torch.zeros(self.convert_feature_size_16k + 1, dtype=torch.int64, device=self.device_manager.device)
        self.pitchf_buffer = torch.zeros(self.convert_feature_size_16k + 1, dtype=self.dtype, device=self.device_manager.device)
        logger.info(f'Allocated audio buffer size: {audio_buffer_size}')
        logger.info(f'Allocated convert buffer size: {convert_size_16k}')
        logger.info(f'Allocated pitchf buffer size: {self.convert_feature_size_16k + 1}')

    def convert(self, audio_in: AudioInOutFloat, sample_rate: int) -> torch.Tensor:
        if self.pipeline is None:
            raise PipelineNotInitializedException()

        # Input audio is always float32
        audio_in_t = torch.as_tensor(audio_in, dtype=torch.float32, device=self.device_manager.device)
        if self.is_half:
            audio_in_t = audio_in_t.half()

        convert_feature_size_16k = audio_in_t.shape[0] // WINDOW_SIZE

        resampler_temp = tat.Resample(
            orig_freq=sample_rate,
            new_freq=HUBERT_SAMPLE_RATE,
            dtype=self.dtype
        ).to(self.device_manager.device)
        audio_in_16k = resampler_temp(audio_in_t)

        vol_t = torch.sqrt(
            torch.square(audio_in_16k).mean()
        )

        audio_model = self.pipeline.exec(
            self.settings.dstId,
            audio_in_16k,
            None,
            None,
            self.settings.tran,
            self.settings.formantShift,
            self.settings.indexRatio,
            convert_feature_size_16k,
            0,
            self.slotInfo.embOutputLayer,
            self.slotInfo.useFinalProj,
            0,
            convert_feature_size_16k,
            self.settings.protect,
        )

        # TODO: Need to handle resampling for individual files
        # FIXME: Why the heck does it require another sqrt to amplify the volume?
        audio_out: torch.Tensor = self.resampler_out(audio_model * torch.sqrt(vol_t))

        return audio_out

    def inference(self, audio_in: AudioInOutFloat):
        if self.pipeline is None:
            raise PipelineNotInitializedException()

        # Input audio is always float32
        audio_in_t = torch.as_tensor(audio_in, dtype=torch.float32, device=self.device_manager.device)
        audio_in_16k = self.resampler_in(audio_in_t)
        if self.is_half:
            audio_in_16k = audio_in_16k.half()

        circular_write(audio_in_16k, self.audio_buffer)

        vol_t = torch.sqrt(
            torch.square(self.audio_buffer).mean()
        )
        vol = max(vol_t.item(), 0)

        if vol < self.inputSensitivity:
            # Busy wait to keep power manager happy and clocks stable. Running pipeline on-demand seems to lag when the delay between
            # voice changer activation is too high.
            # https://forums.developer.nvidia.com/t/why-kernel-calculate-speed-got-slower-after-waiting-for-a-while/221059/9
            self.pipeline.exec(
                self.settings.dstId,
                self.convert_buffer,
                self.pitch_buffer,
                self.pitchf_buffer,
                self.settings.tran,
                self.settings.formantShift,
                self.settings.indexRatio,
                self.convert_feature_size_16k,
                self.silence_front,
                self.slotInfo.embOutputLayer,
                self.slotInfo.useFinalProj,
                self.skip_head,
                self.return_length,
                self.settings.protect,
            )
            return None, vol

        circular_write(audio_in_16k, self.convert_buffer)

        audio_model = self.pipeline.exec(
            self.settings.dstId,
            self.convert_buffer,
            self.pitch_buffer,
            self.pitchf_buffer,
            self.settings.tran,
            self.settings.formantShift,
            self.settings.indexRatio,
            self.convert_feature_size_16k,
            self.silence_front,
            self.slotInfo.embOutputLayer,
            self.slotInfo.useFinalProj,
            self.skip_head,
            self.return_length,
            self.settings.protect,
        )

        # FIXME: Why the heck does it require another sqrt to amplify the volume?
        audio_out: torch.Tensor = self.resampler_out(audio_model * torch.sqrt(vol_t))

        return audio_out, vol

    def __del__(self):
        del self.pipeline

    def export2onnx(self):
        modelSlot = self.slotInfo

        if modelSlot.isONNX:
            logger.error(f"{modelSlot.modelFile} is already in ONNX format.")
            return

        output_path = export2onnx(modelSlot)

        self.slotInfo.modelFileOnnx = os.path.basename(output_path)
        self.slotInfo.modelTypeOnnx = EnumInferenceTypes.onnxRVC.value if self.slotInfo.f0 else EnumInferenceTypes.onnxRVCNono.value
        saveSlotInfo(self.params.model_dir, self.slotInfo.slotIndex, self.slotInfo)

    def get_model_current(self) -> dict:
        return [
            {
                "key": "defaultTune",
                "val": self.settings.tran,
            },
            {
                "key": "defaultIndexRatio",
                "val": self.settings.indexRatio,
            },
            {
                "key": "defaultProtect",
                "val": self.settings.protect,
            },
            {
                "key": "defaultFormantShift",
                "val": self.settings.formantShift,
            },
        ]
