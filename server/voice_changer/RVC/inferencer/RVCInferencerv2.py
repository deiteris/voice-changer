import torch
import json
import os
from safetensors import safe_open
from const import EnumInferenceTypes, JIT_DIR
from voice_changer.common.deviceManager.DeviceManager import DeviceManager
from voice_changer.RVC.inferencer.Inferencer import Inferencer
from .rvc_models.infer_pack.models import SynthesizerTrnMs768NSFsid
from voice_changer.common.SafetensorsUtils import load_model


class RVCInferencerv2(Inferencer):
    def loadModel(self, file: str, gpu: int):
        dev = DeviceManager.get_instance().getDevice(gpu)
        # isHalf = DeviceManager.get_instance().halfPrecisionAvailable(gpu)
        isHalf = False
        self.setProps(EnumInferenceTypes.pyTorchRVCv2, file, isHalf, gpu)

        filename = os.path.splitext(os.path.basename(file))[0]
        jit_filename = f'{filename}_{dev.type}_{dev.index}.torchscript' if dev.index is not None else f'{filename}_{dev.type}.torchscript'
        jit_file = os.path.join(JIT_DIR, jit_filename)
        if not os.path.exists(jit_file):
            # Keep torch.load for backward compatibility, but discourage the use of this loading method
            if '.safetensors' in file:
                with safe_open(file, 'pt', device=str(dev) if dev.type == 'cuda' else 'cpu') as cpt:
                    config = json.loads(cpt.metadata()['config'])
                    model = SynthesizerTrnMs768NSFsid(*config, is_half=False).to(dev)
                    load_model(model, cpt, strict=False)
            else:
                cpt = torch.load(file, map_location=dev if dev.type == 'cuda' else 'cpu')
                model = SynthesizerTrnMs768NSFsid(*cpt["config"], is_half=False).to(dev)
                model.load_state_dict(cpt["weight"], strict=False)

            model.remove_weight_norm()
            # FIXME: DirectML backend seems to have issues with JIT. Disable it for now.
            if dev.type == 'privateuseone':
                model = model.eval()
                self.use_jit = True
            else:
                model = torch.jit.freeze(torch.jit.script(model.eval()))
                torch.jit.save(model, jit_file)
                self.use_jit = False
        else:
            model = torch.jit.load(jit_file)
            self.use_jit = False

        self.model = model
        return self

    def infer(
        self,
        feats: torch.Tensor,
        pitch_length: torch.Tensor,
        pitch: torch.Tensor,
        pitchf: torch.Tensor,
        sid: torch.Tensor,
        skip_head: torch.Tensor | None,
        return_length: torch.Tensor | None,
    ) -> torch.Tensor:
        if pitch is None or pitchf is None:
            raise RuntimeError("[Voice Changer] Pitch or Pitchf is not found.")

        with torch.jit.optimized_execution(self.use_jit):
            res = self.model.infer(feats, pitch_length, pitch, pitchf, sid, skip_head=skip_head, return_length=return_length)
        res = res[0][0, 0].to(dtype=torch.float32)
        return torch.clip(res, -1.0, 1.0, out=res)
