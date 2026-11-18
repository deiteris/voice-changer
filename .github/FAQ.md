# Frequently Asked Questions

Please read this FAQ and the [troubleshooting guide](../README.md#troubleshooting) before reporting a problem.

### General fixes

- Restart the application and check its console for errors.
- Extract a fresh copy of the release to a short path.
- Check that you selected the correct input, output, and processing device.
- For hosted GPU use, see this fork's [Colab](../Colab_RealtimeVoiceChanger.ipynb) and [Kaggle](../Kaggle_RealtimeVoiceChanger.ipynb) notebooks. They require a compatible published CUDA release and ngrok visitor credentials.

### GPU does not appear or does not work

Choose the release for your backend and install a compatible driver. The CUDA build requires an NVIDIA driver compatible with CUDA 13.4. DirectML and ROCm availability depends on your system; check the console for errors. See the [setup instructions](../README.md#working-with-the-source) for backend requirements.

### High CPU usage or latency

Try reducing **Extra** or disabling the index. Adjust **Chunk** to find a workable balance between latency and audio stability.

### I hear my voice without changes

Turn off **passthru** mode.

### A checkpoint fails to load

Prefer safetensors or ONNX models. Restricted `.pth` loading requires PyTorch 2.10 or newer and a compatible checkpoint. See [model checkpoint safety](../README.md#model-checkpoint-safety) before changing the unsafe-loading setting.
