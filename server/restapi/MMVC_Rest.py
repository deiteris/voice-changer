import logging

from restapi.mods.trustedorigin import TrustedOriginMiddleware
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from voice_changer.VoiceChangerManager import VoiceChangerManager

from restapi.MMVC_Rest_Hello import MMVC_Rest_Hello
from restapi.MMVC_Rest_VoiceChanger import MMVC_Rest_VoiceChanger
from restapi.MMVC_Rest_Fileuploader import MMVC_Rest_Fileuploader
from settings import get_settings
from const import TMP_DIR

logger = logging.getLogger(__name__)


class MMVC_Rest:
    _instance = None

    @classmethod
    def get_instance(cls, voiceChangerManager: VoiceChangerManager):
        if cls._instance is None:
            logger.info("Initializing...")
            settings = get_settings()
            app_fastapi = FastAPI()
            app_fastapi.add_middleware(
                TrustedOriginMiddleware,
                allowed_origins=settings.allowed_origins,
                port=settings.port
            )

            app_fastapi.mount("/tmp", StaticFiles(directory=TMP_DIR), name="static")

            app_fastapi.mount(
                "/model_dir",
                StaticFiles(directory=settings.model_dir),
                name="static",
            )

            restHello = MMVC_Rest_Hello()
            app_fastapi.include_router(restHello.router)
            restVoiceChanger = MMVC_Rest_VoiceChanger(voiceChangerManager)
            app_fastapi.include_router(restVoiceChanger.router)
            fileUploader = MMVC_Rest_Fileuploader(voiceChangerManager)
            app_fastapi.include_router(fileUploader.router)

            cls._instance = app_fastapi
            logger.info("Initialized.")
            return cls._instance

        return cls._instance
