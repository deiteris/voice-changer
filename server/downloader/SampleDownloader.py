import json
import os
import asyncio
import shutil
import tempfile
from pathlib import Path
from typing import Any, Tuple

from const import RVCSampleMode, getSampleJsonAndModelIds
from data.ModelSample import ModelSamples, generateModelSample
from data.ModelSlot import ModelSlot, RVCModelSlot, loadSlotInfo
import logging
from voice_changer.ModelSlotManager import ModelSlotManager
from voice_changer.RVC.RVCModelSlotGenerator import RVCModelSlotGenerator
from voice_changer.common.SafetensorsUtils import convert_single
from downloader.Downloader import download

logger = logging.getLogger(__name__)


async def downloadInitialSamples(mode: RVCSampleMode, model_dir: str):
    if not mode:
        catalog_urls, _ = getSampleJsonAndModelIds("production")
        await _downloadSampleJsons(catalog_urls)
        return

    sampleJsonUrls, sampleModels = getSampleJsonAndModelIds(mode)
    if not sampleModels:
        return
    sampleJsons = await _downloadSampleJsons(sampleJsonUrls)
    samples = _generateSampleList(sampleJsons)
    root = Path(model_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    pending = [(index, request) for index, request in enumerate(sampleModels)
               if not _installed_sample_matches(root, index, request, samples)]
    if not pending:
        return
    slotIndex = [index for index, _ in pending]
    pendingModels = [request for _, request in pending]
    with tempfile.TemporaryDirectory(prefix=".sample-stage-", dir=root) as temp:
        stage = Path(temp)
        for index in slotIndex:
            existing = root / str(index)
            if existing.is_symlink():
                raise ValueError("Model slot cannot be a symlink")
            if existing.exists():
                shutil.copytree(existing, stage / str(index))
        await _downloadSamples(samples, pendingModels, str(stage), slotIndex)
        committed = []
        try:
            for index in slotIndex:
                existing = root / str(index)
                backup = stage / f"backup-{index}"
                had_slot = existing.exists()
                if had_slot:
                    os.replace(existing, backup)
                try:
                    os.replace(stage / str(index), existing)
                except Exception:
                    if had_slot:
                        os.replace(backup, existing)
                    raise
                committed.append((existing, backup, had_slot))
        except Exception:
            for existing, backup, had_slot in reversed(committed):
                shutil.rmtree(existing)
                if had_slot:
                    os.replace(backup, existing)
            raise


def _installed_sample_matches(root: Path, index: int, request: Tuple[str, Any], samples: list[ModelSamples]) -> bool:
    sample_id, options = request
    sample = next((item for item in samples if item.id == sample_id), None)
    slot_dir = root / str(index)
    if sample is None or sample.voiceChangerType != "RVC" or slot_dir.is_symlink():
        return False
    try:
        slot = loadSlotInfo(str(root), index)
        if not isinstance(slot, RVCModelSlot) or slot.sampleId != sample_id:
            return False
        model_name = os.path.basename(sample.modelUrl)
        if not model_name.endswith((".onnx", ".safetensors")):
            model_name = os.path.splitext(model_name)[0] + ".safetensors"
        expected = [(slot.modelFile, model_name)]
        index_name = os.path.basename(sample.indexUrl) if options["useIndex"] and getattr(sample, "indexUrl", "") else ""
        expected.append((slot.indexFile, index_name))
        icon_name = os.path.basename(sample.icon) if getattr(sample, "icon", "") else ""
        expected.append((slot.iconFile, icon_name))
        for actual, name in expected:
            if actual != name:
                return False
            if name:
                path = slot_dir / name
                if path.is_symlink() or not path.is_file() or path.stat().st_size == 0:
                    return False
        return True
    except (OSError, ValueError, TypeError, KeyError):
        return False


async def downloadSample(mode: RVCSampleMode, modelId: str, model_dir: str, slotIndex: int, params: Any):
    effective_mode: RVCSampleMode = mode if mode else "production"
    sampleJsonUrls, _sampleModels = getSampleJsonAndModelIds(effective_mode)
    sampleJsons = _generateSampleJsons(sampleJsonUrls)
    if any(not os.path.exists(f) for f in sampleJsons):
        sampleJsons = await _downloadSampleJsons(sampleJsonUrls)
    samples = _generateSampleList(sampleJsons)
    await _downloadSamples(samples, [(modelId, params)], model_dir, [slotIndex])


def getSampleInfos(mode: RVCSampleMode):
    effective_mode: RVCSampleMode = mode if mode else "production"
    sampleJsonUrls, _sampleModels = getSampleJsonAndModelIds(effective_mode)
    sampleJsons = [f for f in _generateSampleJsons(sampleJsonUrls) if os.path.exists(f)]
    samples = _generateSampleList(sampleJsons)
    return samples


async def _downloadSampleJsons(sampleJsonUrls: list[str]):
    sampleJsons: list[str] = []
    tasks: list[asyncio.Task] = []
    for url in sampleJsonUrls:
        filename = os.path.basename(url)
        tasks.append(asyncio.ensure_future(download({"url": url, "saveTo": filename})))
        sampleJsons.append(filename)
    await asyncio.gather(*tasks)
    return sampleJsons


def _generateSampleJsons(sampleJsonUrls: list[str]):
    sampleJsons = []
    for url in sampleJsonUrls:
        filename = os.path.basename(url)
        sampleJsons.append(filename)
    return sampleJsons


def _generateSampleList(sampleJsons: list[str]):
    samples: list[ModelSamples] = []
    for file in sampleJsons:
        with open(file, "r", encoding="utf-8") as f:
            jsonDict = json.load(f)
        for vcType in jsonDict:
            for sampleParams in jsonDict[vcType]:
                sample = generateModelSample(sampleParams)
                samples.append(sample)
    return samples


async def _downloadSamples(samples: list[ModelSamples], sampleModelIds: list[Tuple[str, Any]], model_dir: str, slotIndex: list[int]):
    downloadParams = []
    modelSlotManager = ModelSlotManager(model_dir)

    for i, initSampleId in enumerate(sampleModelIds):
        targetSampleId = initSampleId[0]
        targetSampleParams = initSampleId[1]
        targetSlotIndex = slotIndex[i]

        # 初期サンプルをサーチ
        match = False
        for sample in samples:
            if sample.id == targetSampleId:
                match = True
                break
        if match is False:
            logger.warning(f"Initial sample not found: {targetSampleId}")
            raise ValueError(f"Sample not found: {targetSampleId}")

        # 検出されたら、、、
        slotDir = os.path.join(model_dir, str(targetSlotIndex))
        slotInfo: ModelSlot = ModelSlot()
        if sample.voiceChangerType == "RVC":
            slotInfo: RVCModelSlot = RVCModelSlot()

            os.makedirs(slotDir, exist_ok=True)
            modelFilePath = os.path.join(
                slotDir,
                os.path.basename(sample.modelUrl),
            )
            downloadParams.append(
                {
                    "url": sample.modelUrl,
                    "saveTo": modelFilePath,
                    "cache": False,
                }
            )
            slotInfo.modelFile = os.path.basename(sample.modelUrl)

            if targetSampleParams["useIndex"] is True and hasattr(sample, "indexUrl") and sample.indexUrl != "":
                indexPath = os.path.join(
                    slotDir,
                    os.path.basename(sample.indexUrl),
                )
                downloadParams.append(
                    {
                        "url": sample.indexUrl,
                        "saveTo": indexPath,
                        "cache": False,
                    }
                )
                slotInfo.indexFile = os.path.basename(sample.indexUrl)

            if hasattr(sample, "icon") and sample.icon != "":
                iconPath = os.path.join(
                    slotDir,
                    os.path.basename(sample.icon),
                )
                downloadParams.append(
                    {
                        "url": sample.icon,
                        "saveTo": iconPath,
                        "cache": False,
                    }
                )
                slotInfo.iconFile = os.path.basename(sample.icon)

            slotInfo.sampleId = sample.id
            slotInfo.credit = sample.credit
            slotInfo.description = sample.description
            slotInfo.name = sample.name
            slotInfo.termsOfUseUrl = sample.termsOfUseUrl
            slotInfo.defaultTune = 0
            slotInfo.defaultIndexRatio = 0
            slotInfo.defaultProtect = 0.5
            slotInfo.isONNX = slotInfo.modelFile.endswith(".onnx")
            modelSlotManager.save_model_slot(targetSlotIndex, slotInfo)
        else:
            raise ValueError(f"{sample.voiceChangerType} is not supported.")

    # ダウンロード
    logger.info("Downloading model files...")
    tasks: list[asyncio.Task] = []
    for file in downloadParams:
        tasks.append(asyncio.ensure_future(download(file)))
    results = await asyncio.gather(*tasks, return_exceptions=True)
    for result in results:
        if isinstance(result, BaseException):
            raise result

    # メタデータ作成
    logger.info("Generating metadata...")
    for targetSlotIndex in slotIndex:
        slotInfo = modelSlotManager.get_slot_info(targetSlotIndex)
        modelPath = os.path.join(model_dir, str(slotInfo.slotIndex), os.path.basename(slotInfo.modelFile))
        if slotInfo.voiceChangerType == "RVC":
            if slotInfo.isONNX:
                slotInfo = RVCModelSlotGenerator._setInfoByONNX(modelPath, slotInfo)
            else:
                slotInfo = RVCModelSlotGenerator._setInfoByPytorch(modelPath, slotInfo)
                if not modelPath.endswith(".safetensors"):
                    convert_single(modelPath, True)
                    filename, _ = os.path.splitext(os.path.basename(modelPath))
                    slotInfo.modelFile = f"{filename}.safetensors"

            modelSlotManager.save_model_slot(targetSlotIndex, slotInfo)
