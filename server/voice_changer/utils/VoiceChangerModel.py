from typing import Any, Protocol, TypeAlias
import torch
import numpy as np
from const import VoiceChangerType
from data.ModelSlot import ModelSlots
from voice_changer.VoiceChangerSettings import VoiceChangerSettings

AudioInOutFloat: TypeAlias = np.ndarray[Any, np.dtype[np.float32]]

class VoiceChangerModel(Protocol):
    voiceChangerType: VoiceChangerType

    def __init__(self, slot_info: ModelSlots, settings: VoiceChangerSettings):
        ...

    def initialize(self, force_reload: bool = False):
        ...

    def set_slot_info(self, slot_info: ModelSlots):
        ...

    def get_processing_sampling_rate(self) -> int:
        ...

    def get_info(self) -> dict[str, Any]:
        ...

    def convert(self, data: torch.Tensor, sample_rate: int) -> torch.Tensor:
        ...

    def inference(self, data: tuple[Any, ...]) -> torch.Tensor:
        ...

    def update_settings(self, key: str, val: Any, old_val: Any):
        ...

    def set_sampling_rate(self, inputSampleRate: int, outputSampleRate: int):
        ...

    def realloc(self, block_frame: int, extra_frame: int, crossfade_frame: int, sola_search_frame: int):
        ...

    def export2onnx() -> Any:
        ...

    def get_model_current(self) -> list[dict]:
        ...
