import json
import torch
from safetensors import safe_open
from const import EnumInferenceTypes
from voice_changer.common.SafetensorsUtils import load_model, load_rvc_checkpoint
from voice_changer.common.deviceManager.DeviceManager import DeviceManager

from voice_changer.RVC.inferencer.Inferencer import Inferencer
from voice_changer.RVC.inferencer.rvc_models.infer_pack.models_onnx import SynthesizerTrnMsNSFsidM


class WebUIInferencer(Inferencer):
    def load_model(self, file: str):
        self.set_props(EnumInferenceTypes.pyTorchWebUI, file)

        device_manager = DeviceManager.get_instance()
        dev = device_manager.device
        is_half = device_manager.use_fp16()

        if file.endswith('.safetensors'):
            with safe_open(file, 'pt', device=str(dev) if dev.type == 'cuda' else 'cpu') as cpt:
                params = json.loads(cpt.metadata()['params'])
                model = SynthesizerTrnMsNSFsidM(**params, is_half=is_half).to(dev)
                load_model(model, cpt, strict=False)
        else:
            cpt = load_rvc_checkpoint(file, map_location="cpu")
            model = SynthesizerTrnMsNSFsidM(**cpt["params"], is_half=is_half)
            model.load_state_dict(cpt["weight"], strict=False)
            model = model.to(dev)

        model.eval()
        if is_half:
            model = model.half()

        self.model = model
        return self

    @torch.no_grad()
    def infer(
        self,
        feats: torch.Tensor,
        pitch_length: torch.Tensor,
        pitch: torch.Tensor,
        pitchf: torch.Tensor,
        sid: torch.Tensor,
        skip_head: int,
        return_length: int,
        formant_length: int,
    ) -> torch.Tensor:
        assert pitch is not None or pitchf is not None, "Pitch or Pitchf is not found."

        return self.model(
            feats,
            pitch_length,
            pitch,
            pitchf,
            sid,
            skip_head,
            return_length,
            formant_length,
        )
