import numpy as np
import torchfcpe
import torch

from const import PitchExtractorType
from voice_changer.common.deviceManager.DeviceManager import DeviceManager
from voice_changer.RVC.pitchExtractor.PitchExtractor import PitchExtractor
from voice_changer.common.TorchUtils import circular_write
from voice_changer.common.FCPE import spawn_infer_model_from_pt
# from voice_changer.common.MelExtractor import MelSpectrogram

class FcpePitchExtractor(PitchExtractor):

    def __init__(self, file: str):
        super().__init__()
        self.type: PitchExtractorType = "fcpe"
        self.f0_min = 50
        self.f0_max = 1100
        self.f0_mel_min = 1127 * np.log(1 + self.f0_min / 700)
        self.f0_mel_max = 1127 * np.log(1 + self.f0_max / 700)
        device_manager = DeviceManager.get_instance()
        self.is_half = device_manager.use_fp16()

        model, wav2mel = spawn_infer_model_from_pt(file, self.is_half, device_manager.device, bundled_model=True)
        self.mel_extractor = wav2mel
        self.fcpe = model

    def extract(self, audio: torch.Tensor, pitchf: torch.Tensor, f0_up_key: int, sr: int, window: int) -> tuple[torch.Tensor, torch.Tensor]:
        mel: torch.Tensor = self.mel_extractor(audio.unsqueeze(0).float(), sr)
        if self.is_half:
            mel = mel.half()

        f0: torch.Tensor = self.fcpe(
            mel,
            decoder_mode="local_argmax",
            threshold=0.006,
        )
        f0 = f0.squeeze()

        f0 *= 2 ** (f0_up_key / 12)
        circular_write(f0, pitchf)
        f0_mel = 1127.0 * torch.log(1.0 + pitchf / 700.0)
        f0_mel[f0_mel > 0] = (f0_mel[f0_mel > 0] - self.f0_mel_min) * 254 / (self.f0_mel_max - self.f0_mel_min) + 1
        f0_mel[f0_mel <= 1] = 1
        f0_mel[f0_mel > 255] = 255
        f0_coarse = torch.round(f0_mel, out=f0_mel).to(dtype=torch.int64)
        return f0_coarse.unsqueeze(0), pitchf.unsqueeze(0)