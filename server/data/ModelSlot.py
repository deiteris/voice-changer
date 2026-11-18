from typing import TypeAlias, Union
from const import MAX_SLOT_NUM, EnumInferenceTypes, EmbedderType, VoiceChangerType

from dataclasses import dataclass, asdict, field

import os
import json
import logging
import tempfile
logger = logging.getLogger(__name__)

@dataclass
class ModelSlot:
    slotIndex: int = -1
    voiceChangerType: VoiceChangerType | None = None
    name: str = ""
    description: str = ""
    credit: str = ""
    termsOfUseUrl: str = ""
    iconFile: str = ""
    speakers: dict = field(default_factory=lambda: {})


@dataclass
class RVCModelSlot(ModelSlot):
    voiceChangerType: VoiceChangerType = "RVC"
    modelFile: str = ""
    modelFileOnnx: str = ""
    indexFile: str = ""
    defaultTune: int = 0
    defaultFormantShift: float = 0
    defaultIndexRatio: float = 0
    defaultProtect: float = 0.5
    isONNX: bool = False
    modelType: str = EnumInferenceTypes.pyTorchRVC.value
    modelTypeOnnx: str = EnumInferenceTypes.onnxRVC.value
    samplingRate: int = -1
    f0: bool = True
    embChannels: int = 256
    embOutputLayer: int = 9
    useFinalProj: bool = True
    deprecated: bool = False
    embedder: EmbedderType = "hubert_base"

    sampleId: str = ""
    speakers: dict = field(default_factory=lambda: {0: "target"})

    version: str = "v2"


ModelSlots: TypeAlias = Union[
    ModelSlot,
    RVCModelSlot,
]


def loadSlotInfo(model_dir: str, slotIndex: int) -> ModelSlots:
    slotDir = os.path.join(model_dir, str(slotIndex))
    jsonFile = os.path.join(slotDir, "params.json")
    if not os.path.exists(jsonFile):
        return ModelSlot()
    with open(jsonFile, encoding="utf-8") as f:
        jsonDict = json.load(f)
    if not isinstance(jsonDict, dict):
        raise ValueError("Model slot metadata must be an object")
    slotInfoKey = list(ModelSlot.__annotations__.keys())
    slotInfo = ModelSlot(**{k: v for k, v in jsonDict.items() if k in slotInfoKey})
    if slotInfo.voiceChangerType == "RVC":
        slotInfoKey.extend(list(RVCModelSlot.__annotations__.keys()))
        return RVCModelSlot(**{k: v for k, v in jsonDict.items() if k in slotInfoKey})
    else:
        return ModelSlot()


def loadAllSlotInfo(model_dir: str):
    slotInfos: list[ModelSlots] = []
    for slotIndex in range(MAX_SLOT_NUM):
        try:
            slotInfo = loadSlotInfo(model_dir, slotIndex)
        except (OSError, ValueError, TypeError, UnicodeError):
            logger.exception("Could not load model slot %s", slotIndex)
            slotInfo = ModelSlot()
        slotInfo.slotIndex = slotIndex  # スロットインデックスは動的に注入
        slotInfos.append(slotInfo)
    return slotInfos


def saveSlotInfo(model_dir: str, slotIndex: int, slotInfo: ModelSlots):
    slotDir = os.path.join(model_dir, str(slotIndex))
    logger.info(f"SlotInfo::: {slotInfo}")
    slotInfoDict = asdict(slotInfo)
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=slotDir, delete=False) as f:
            temp_path = f.name
            json.dump(slotInfoDict, f, indent=4)
        os.replace(temp_path, os.path.join(slotDir, "params.json"))
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)
