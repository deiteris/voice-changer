import wave
import os
import logging
from const import TMP_DIR

logger = logging.getLogger(__name__)

STREAM_INPUT_FILE = os.path.join(TMP_DIR, "in.wav")
STREAM_OUTPUT_FILE = os.path.join(TMP_DIR, "out.wav")

class IORecorder:
    def __init__(self):
        self.fi = None
        self.fo = None
        self._clear()

    def _clear(self):
        self.close()
        self._clearFile(STREAM_INPUT_FILE)
        self._clearFile(STREAM_OUTPUT_FILE)

    def _clearFile(self, filename: str):
        if os.path.exists(filename):
            logger.info(f"Removing old recording file {filename}")
            os.remove(filename)

    def open(self, input_sampling_rate: int, output_sampling_rate: int):
        self._clear()

        self.fi = wave.open(STREAM_INPUT_FILE, "wb")
        self.fi.setnchannels(1)
        self.fi.setsampwidth(2)
        self.fi.setframerate(input_sampling_rate)

        self.fo = wave.open(STREAM_OUTPUT_FILE, "wb")
        self.fo.setnchannels(1)
        self.fo.setsampwidth(2)
        self.fo.setframerate(output_sampling_rate)
        logger.info(f"-------------------------- - - - {STREAM_INPUT_FILE}, {STREAM_OUTPUT_FILE}")

    def write_input(self, wav):
        if self.fi is None:
            raise Exception('IO recorder is closed.')
        self.fi.writeframes(wav)

    def write_output(self, wav):
        if self.fo is None:
            raise Exception('IO recorder is closed.')
        self.fo.writeframes(wav)

    def close(self):
        if self.fi is not None:
            self.fi.close()
            self.fi = None
        if self.fo is not None:
            self.fo.close()
            self.fo = None
