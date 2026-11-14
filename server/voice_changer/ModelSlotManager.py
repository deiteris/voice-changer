from const import UPLOAD_DIR
from data.ModelSlot import ModelSlots, loadAllSlotInfo, saveSlotInfo
import json
import os
import shutil

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
        paramsDict = json.loads(params)
        uploadPath = os.path.join(UPLOAD_DIR, paramsDict["file"])
        storeDir = os.path.join(self.model_dir, str(paramsDict["slot"]))
        storePath = os.path.join(
            storeDir,
            paramsDict["file"],
        )
        try:
            shutil.move(uploadPath, storePath)
            slotInfo = self._load_model_slot(paramsDict["slot"])
            setattr(slotInfo, paramsDict["name"], storePath)
            self._save_model_slot(paramsDict["slot"], slotInfo)
        except Exception as e:
            logger.exception(e)
