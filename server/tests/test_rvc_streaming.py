import unittest
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import torch

from voice_changer.common.TorchUtils import circular_write
from voice_changer.RVC.RVCr2 import RVCr2
from voice_changer.RVC.pipeline.Pipeline import Pipeline
from voice_changer.VoiceChangerV2 import VoiceChangerV2


class StreamingEdgeCases(unittest.TestCase):
    def test_invalid_pitch_becomes_unvoiced(self):
        pipeline = object.__new__(Pipeline)
        pipeline.dtype = torch.float32
        pipeline.pitchExtractor = SimpleNamespace(extract=Mock(return_value=torch.tensor(
            [float('nan'), float('inf'), -float('inf'), -10.0, 0.0, 100.0]
        )))
        pitch, pitchf = pipeline.extract_pitch(torch.zeros(16), None, None, 0, 0)
        self.assertEqual(pitchf[0, :5].tolist(), [0.0] * 5)
        self.assertEqual(pitchf[0, 5].item(), 100.0)
        self.assertTrue(torch.all((pitch >= 1) & (pitch <= 255)))

    def test_circular_write_short_empty_and_oversized(self):
        target = torch.tensor([1, 2, 3, 4])
        circular_write(torch.tensor([], dtype=target.dtype), target)
        self.assertEqual(target.tolist(), [1, 2, 3, 4])
        circular_write(torch.tensor([5, 6]), target)
        self.assertEqual(target.tolist(), [3, 4, 5, 6])
        circular_write(torch.tensor([7, 8, 9, 10, 11]), target)
        self.assertEqual(target.tolist(), [8, 9, 10, 11])
        self.assertEqual(circular_write(torch.tensor([1]), torch.tensor([])).numel(), 0)

    def test_short_extra_context_never_uses_negative_pitch_slice(self):
        rvc = object.__new__(RVCr2)
        rvc.input_sample_rate = 48000
        rvc.settings = SimpleNamespace(silenceFront=1)
        rvc.device_manager = SimpleNamespace(device=torch.device('cpu'))
        rvc.dtype = torch.float32
        rvc.pipeline = None
        rvc.realloc(4096, 480, 2400, 480)
        self.assertEqual(rvc.silence_front, 0)
        rvc.realloc(4096, 4800, 2400, 480)
        self.assertEqual(rvc.silence_front, 800)

    def test_zero_crossfade_returns_audio_without_convolution(self):
        vc = object.__new__(VoiceChangerV2)
        vc.vcmodel = SimpleNamespace(inference=Mock(return_value=(torch.arange(8, dtype=torch.float32), 0.25)))
        vc.crossfade_frame = 0
        result, volume = vc.process_audio(np.zeros(4, dtype=np.float32))
        np.testing.assert_array_equal(result, [0, 1, 2, 3])
        self.assertEqual(volume, 0.25)

    def test_block_frame_matches_server_audio_rate(self):
        vc = object.__new__(VoiceChangerV2)
        vc.settings = SimpleNamespace(serverReadChunkSize=32, inputSampleRate=96000, enableServerAudio=1)
        self.assertEqual(vc._get_block_frame(), 8192)
        vc.settings.inputSampleRate = 44100
        self.assertEqual(vc._get_block_frame(), 3763)
        vc.settings.serverReadChunkSize = 27
        vc.settings.inputSampleRate = 24000
        self.assertEqual(vc._get_block_frame(), int((27 * 128 / 48000) * 24000))
        vc.settings.serverReadChunkSize = 32
        vc.settings.enableServerAudio = 0
        self.assertEqual(vc._get_block_frame(), 4096)


if __name__ == '__main__':
    unittest.main()
