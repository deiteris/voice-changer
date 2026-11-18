from const import UPLOAD_DIR
from data.ModelSlot import ModelSlots, loadAllSlotInfo, saveSlotInfo
import json
import os
import shutil
from pathlib import Path

import logging

logger = logging.getLogger(__name__)


class ModelSlotManager:
    _instance = None

    def __init__(self, model_dir: str):
        self.model_dir = model_dir
        self.modelSlots = loadAllSlotInfo(self.model_dir)

    @classmethod
    def get_instance(cls, model_dir: str):
        if cls._instance is None:
            cls._instance = cls(model_dir)
        return cls._instance

    def _save_model_slot(self, slotIndex: int, slotInfo: ModelSlots):
        saveSlotInfo(self.model_dir, slotIndex, slotInfo)
        self.modelSlots = loadAllSlotInfo(self.model_dir)

    def _load_model_slot(self, slotIndex: int):
        return self.modelSlots[slotIndex]

    def getAllSlotInfo(self, reload: bool = False):
        if reload:
            self.modelSlots = loadAllSlotInfo(self.model_dir)
        return self.modelSlots

    def get_slot_info(self, slotIndex: int):
        if slotIndex < 0 or slotIndex >= len(self.modelSlots):
            return
        return self._load_model_slot(slotIndex)

    def save_model_slot(self, slotIndex: int, slotInfo: ModelSlots):
        self._save_model_slot(slotIndex, slotInfo)

    def update_model_info(self, slot_index: int, key: str, val):
        if slot_index < 0 or slot_index >= len(self.modelSlots):
            logger.warning(f"Invalid slot index for update_model_info: {slot_index}")
            return
        logger.info(f"UPDATE MODEL INFO: {key}={val}")
        slotInfo = self._load_model_slot(slot_index)
        if key == "speakers":
            setattr(slotInfo, key, json.loads(val))
        else:
            setattr(slotInfo, key, val)
        self._save_model_slot(slot_index, slotInfo)

    def store_model_assets(self, params: str):
        data = json.loads(params)
        slot = data["slot"]
        filename = data["file"]
        if type(slot) is not int or not 0 <= slot < len(self.modelSlots):
            raise ValueError("Invalid model slot")
        if data["name"] != "iconFile":
            raise ValueError("Unsupported model asset")
        if not isinstance(filename, str) or not filename or Path(filename).name != filename or "\\" in filename or filename in (".", ".."):
            raise ValueError("Invalid asset filename")
        upload_root = Path(UPLOAD_DIR).resolve()
        source = (upload_root / filename).resolve()
        model_root = Path(self.model_dir).resolve()
        slot_dir = model_root / str(slot)
        if slot_dir.is_symlink() or not slot_dir.is_dir():
            raise ValueError("Invalid model slot directory")
        slot_info = self._load_model_slot(slot)
        protected = {"params.json", getattr(slot_info, "modelFile", ""), getattr(slot_info, "modelFileOnnx", ""), getattr(slot_info, "indexFile", "")}
        if filename.lower() in {name.lower() for name in protected} or Path(filename).suffix.lower() not in (".png", ".jpg", ".jpeg", ".gif"):
            raise ValueError("Invalid asset filename")
        destination = slot_dir / filename
        if not source.is_relative_to(upload_root) or not source.is_file() or destination.is_symlink():
            raise ValueError("Invalid asset path")
        shutil.copy2(source, destination)
        slot_info.iconFile = filename
        self._save_model_slot(slot, slot_info)
        try:
            source.unlink()
        except OSError:
            logger.warning("Could not remove accepted uploaded asset: %s", source)
