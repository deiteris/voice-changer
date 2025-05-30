from const import EmbedderType
from voice_changer.embedder.Embedder import Embedder
from voice_changer.embedder.OnnxEmbedder import OnnxEmbedder
from settings import ServerSettings, get_settings
import logging
logger = logging.getLogger(__name__)

class EmbedderManager:
    embedder: Embedder | None = None
    params: ServerSettings

    @classmethod
    def initialize(cls):
        cls.params = get_settings()

    @classmethod
    def get_embedder(cls, embedder_type: EmbedderType, force_reload: bool = False) -> Embedder:
        if cls.embedder is not None \
            and cls.embedder == embedder_type \
            and not force_reload:
            logger.info('Reusing embedder.')
            return cls.embedder
        cls.embedder = cls.load_embedder(embedder_type)
        return cls.embedder

    @classmethod
    def load_embedder(cls, embedder_type: EmbedderType) -> Embedder:
        logger.info(f'Loading embedder {embedder_type}')

        if embedder_type == "spin_base":
            file = cls.params.spin_onnx
            return OnnxEmbedder().load_model(file)
        elif embedder_type not in ["hubert_base", "contentvec"]:
            raise RuntimeError(f'Unsupported embedder type: {embedder_type}')
        file = cls.params.content_vec_500_onnx
        return OnnxEmbedder().load_model(file)

