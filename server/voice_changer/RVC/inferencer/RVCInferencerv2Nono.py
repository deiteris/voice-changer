import torch
from const import EnumInferenceTypes

from voice_changer.RVC.deviceManager.DeviceManager import DeviceManager
from voice_changer.RVC.inferencer.Inferencer import Inferencer
from .rvc_models.infer_pack.models import SynthesizerTrnMs768NSFsid_nono


class RVCInferencerv2Nono(Inferencer):
    def loadModel(self, file: str, gpu: int):
        dev = DeviceManager.get_instance().getDevice(gpu)
        #isHalf = DeviceManager.get_instance().halfPrecisionAvailable(gpu)
        isHalf = False
        self.setProps(EnumInferenceTypes.pyTorchRVCv2Nono, file, isHalf, gpu)

        cpt = torch.load(file, map_location="cpu")
        model = SynthesizerTrnMs768NSFsid_nono(*cpt["config"], is_half=isHalf)

        model.eval()
        model.load_state_dict(cpt["weight"], strict=False)

        model = model.to(dev)
        if isHalf:
            model = model.half()

        self.model = model
        return self

    def infer(
        self,
        feats: torch.Tensor,
        pitch_length: torch.Tensor,
        pitch: torch.Tensor | None,
        pitchf: torch.Tensor | None,
        sid: torch.Tensor,
        convert_length: int | None,
    ) -> torch.Tensor:
        res = self.model.infer(feats, pitch_length, sid, convert_length=convert_length)
        res = res[0][0, 0].to(dtype=torch.float32)
        return torch.clip(res, -1.0, 1.0, out=res)
