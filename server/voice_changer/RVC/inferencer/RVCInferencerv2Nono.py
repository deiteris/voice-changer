import torch
import json
import logging
from safetensors import safe_open
from const import EnumInferenceTypes
from voice_changer.common.deviceManager.DeviceManager import DeviceManager
from voice_changer.RVC.inferencer.Inferencer import Inferencer
from .rvc_models.infer_pack.models import SynthesizerTrnMs768NSFsid_nono
from voice_changer.common.SafetensorsUtils import load_model

logger = logging.getLogger(__name__)

class RVCInferencerv2Nono(Inferencer):
    def load_model(self, file: str):
        device_manager = DeviceManager.get_instance()
        dev = device_manager.device
        is_half = device_manager.use_fp16()
        use_jit_compile = device_manager.use_jit_compile()
        self.set_props(EnumInferenceTypes.pyTorchRVCv2Nono, file)

        # Keep torch.load for backward compatibility, but discourage the use of this loading method
        if file.endswith('.safetensors'):
            with safe_open(file, 'pt', device=str(dev) if dev.type == 'cuda' else 'cpu') as cpt:
                config = json.loads(cpt.metadata()['config'])
                model = SynthesizerTrnMs768NSFsid_nono(*config, is_half=is_half).to(dev)
                load_model(model, cpt, strict=False)
        else:
            cpt = torch.load(file, map_location=dev if dev.type == 'cuda' else 'cpu', weights_only=True)
            model = SynthesizerTrnMs768NSFsid_nono(*cpt["config"], is_half=is_half).to(dev)
            model.load_state_dict(cpt["weight"], strict=False)
        model = model.eval()

        model.remove_weight_norm()

        if is_half:
            model = model.half()

        self.use_jit_eager = not use_jit_compile
        if use_jit_compile:
            logger.info('Compiling JIT model...')
            model = torch.jit.optimize_for_inference(torch.jit.script(model), other_methods=['infer'])

        self.model = model
        return self

    def infer(
        self,
        feats: torch.Tensor,
        pitch_length: torch.Tensor,
        pitch: torch.Tensor | None,
        pitchf: torch.Tensor | None,
        sid: torch.Tensor,
        skip_head: int,
        return_length: int,
        formant_length: int,
    ) -> torch.Tensor:
        with torch.jit.optimized_execution(self.use_jit):
            res = self.model.infer(
                feats,
                pitch_length,
                sid,
                skip_head=skip_head,
                return_length=return_length,
                formant_length=formant_length
            )
        res = res[0][0, 0]
        return torch.clip(res, -1.0, 1.0, out=res)
