import torchcrepe
import torch
from const import PitchExtractorType, F0_MIN, F0_MAX
from voice_changer.common.deviceManager.DeviceManager import DeviceManager
from voice_changer.pitch_extractor.PitchExtractor import PitchExtractor
from voice_changer.pitch_extractor.torchcrepe.load import load_model

class CrepePitchExtractor(PitchExtractor):

    def __init__(self, type: PitchExtractorType, file: str):
        super().__init__()
        self.type: PitchExtractorType = type
        _, size = type.split('_')
        self.model_size = size
        self.device = DeviceManager.get_instance().device
        load_model(self.device, file, size)

    def extract(
        self,
        audio: torch.Tensor,
        sr: int,
        window: int,
    ) -> torch.Tensor:
        f0, pd = torchcrepe.predict(
            audio.unsqueeze(0).float(),
            sr,
            hop_length=window,
            fmin=F0_MIN,
            fmax=F0_MAX,
            model=self.model_size,
            decoder=torchcrepe.decode.weighted_argmax,
            device=self.device,
            return_periodicity=True,
        )

        f0: torch.Tensor = torchcrepe.filter.median(f0, 3)  # 本家だとmeanですが、harvestに合わせmedianフィルタ
        pd: torch.Tensor = torchcrepe.filter.median(pd, 3)

        f0[pd < 0.1] = 0
        return f0.squeeze()
