import torch
from const import EnumInferenceTypes
from voice_changer.RVC.deviceManager.DeviceManager import DeviceManager
from voice_changer.RVC.inferencer.Inferencer import Inferencer
from .rvc_models.infer_pack.models import SynthesizerTrnMs768NSFsid


class RVCInferencerv2(Inferencer):
    def loadModel(self, file: str, gpu: int):
        dev = DeviceManager.get_instance().getDevice(gpu)
        self.setProps(EnumInferenceTypes.pyTorchRVCv2, file, False, gpu)

        cpt = torch.load(file, map_location=dev)
        model = SynthesizerTrnMs768NSFsid(*cpt["config"], is_half=False).to(dev)

        model.eval()
        model.load_state_dict(cpt["weight"], strict=False)

        self.model = model
        return self

    def infer(
        self,
        feats: torch.Tensor,
        pitch_length: torch.Tensor,
        pitch: torch.Tensor,
        pitchf: torch.Tensor,
        sid: torch.Tensor,
        convert_length: int | None,
    ) -> torch.Tensor:
        if pitch is None or pitchf is None:
            raise RuntimeError("[Voice Changer] Pitch or Pitchf is not found.")

        res = self.model.infer(feats, pitch_length, pitch, pitchf, sid, convert_length=convert_length)
        res = res[0][0, 0]
        return torch.clip(res, -1.0, 1.0, out=res)
