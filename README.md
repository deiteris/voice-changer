# Voice Changer

## Table of Contents

- [Overview](#overview)
- [Supported operated systems](#supported-operated-systems)
- [System requirements](#system-requirements)
  - [For CPU-only voice conversion](#for-cpu-only-voice-conversion)
  - [For GPU voice conversion](#for-gpu-voice-conversion)
- [Known issues](#known-issues)
  - [General](#general)
  - [DirectML (dml) version](#directml-dml-version)
  - [Nvidia version](#nvidia-version)
  - [All versions](#all-versions)
- [How to use](#how-to-use)
  - [Running locally on Windows](#running-locally-on-windows)
    - [Before you start](#before-you-start)
    - [Check your hardware](#check-your-hardware)
    - [For AMD/Intel/CPU users](#for-amdintelcpu-users)
    - [For Nvidia users](#for-nvidia-users)
    - [Running the voice changer](#running-the-voice-changer)
  - [Running locally on macOS](#running-locally-on-macos)
    - [For Apple Silicon (Apple M1, etc.) users](#for-apple-silicon-apple-m1-etc-users)
    - [For Intel users](#for-intel-users)
    - [Removing Apple quarantine attribute](#removing-apple-quarantine-attribute)
    - [Running the voice changer](#running-the-voice-changer-1)
  - [Running on Colab/Kaggle](#running-on-colabkaggle)
- [Troubleshooting](#troubleshooting)
  - [Exceptions.PretrainDownloadException: 'Failed to download weight.'](#exceptionspretraindownloadexception-failed-to-download-weight)
  - [Audio devices are not displayed](#audio-devices-are-not-displayed)
  - [No sound after start](#no-sound-after-start)
  - [Hearing non-converted voice](#hearing-non-converted-voice)
  - [Hearing audio crackles](#hearing-audio-crackles)
  - [Audio is stuttery](#audio-is-stuttery)
- [Contribution](#contribution)
- [Working with the source](#working-with-the-source)
  - [Prerequisites](#prerequisites)
  - [Setting up the environment](#setting-up-the-environment)
  - [Model checkpoint safety](#model-checkpoint-safety)
  - [Running the server](#running-the-server)
  - [Building a package](#building-a-package)

## Overview

This is a fork of [w-okada voice changer](https://github.com/w-okada/voice-changer) that performs real-time voice conversion
using various voice conversion algorithms.

> [!IMPORTANT]
> This version works only with Retrieval-based Voice Conversion (RVC).

The fork aims to improve the overall performance for any backend, and at the same time introducing new features and improving
user experience.

The following videos demonstrate how the voice changer works and performs with AMD graphics cards (including integrated GPU!):

[Amd iGPU.webm](https://github.com/deiteris/voice-changer/assets/6103913/67354d4e-51aa-425c-bd23-d33ad2baf824)

[Amd Dgpu Rx6600m.webm](https://github.com/deiteris/voice-changer/assets/6103913/b932296c-36e4-4150-9306-e80b5c7e4afb)

And this one demonstrates how the voice changer works and performs with Nvidia GeForce GTX 1650 laptop:

[Nvidia Dgpu Gtx 1650.webm](https://github.com/deiteris/voice-changer/assets/6103913/3985e6f3-c22d-4899-ad93-057c599b8b53)

## Supported operated systems

* Windows 10 or later.
* Linux.
* macOS 12 Monterey or later. With Apple Silicon or Intel CPU.

## System requirements

> [!IMPORTANT]
> Minimum requirement means that you will be able to run **ONLY** the voice changer. Voice conversion and gaming at the same time will not provide satisfying experience with minimum requirements in most cases.

RAM: at least 6GB.

Disk space: at least 6GB of free disk space. For fast model loading, SSD is recommended.

### For CPU-only voice conversion

Minimum requirement: Intel Core i5-4690K or AMD FX-6300.

Recommended requirement: Intel Core i5-10400F or AMD Ryzen 5 1600X.

### For GPU voice conversion

GPU support and performance depend on the selected backend, drivers, operating system, and model. The CUDA build uses CUDA 13.4 and requires a compatible NVIDIA driver. Verify compatibility for your hardware and driver before choosing a release. The Linux CUDA backend also requires a compatible FAISS GPU installation.

## Known issues

### General

* Mozilla Firefox ESR may not display audio devices.

### DirectML (dml) version

* When changing **Chunk**, **Extra** or **Crossfade size** settings, you must switch device to CPU then back to your GPU.
  Otherwise, performance issues can be observed.

* Only `rmvpe_onnx`, `fcpe_onnx`, `crepe_tiny_onnx` and `crepe_full_onnx` are available in the list of **F0 Det.**.

* When using a laptop with integrated GPU and dedicated GPU, severely degraded performance (up to 50% reduction) can be observed when running the voice changer on built-in display.

* Slightly degraded performance (up to 25% reduction) can be observed with multi-GPU setups.

* AMD Radeon RX 7000 series may be unable to achieve low latency (below 256ms).

### Nvidia version

* When starting voice conversion for the first time, it may take up to 5-7 seconds to start outputting the converted voice.

### All versions

* Only "perf" metric is reported in server audio mode with `rest` protocol.

## How to use

### Running locally on Windows

#### Before you start

1. [If not installed] Download and install [7-Zip](https://www.7-zip.org/) or [WinRAR](https://www.win-rar.com/download.html).

1. [If not installed] Download and install [VAC Lite by Muzychenko](https://software.muzychenko.net/freeware/vac470lite.zip).

1. Navigate to the [releases section](https://github.com/JohnRealNoob/voice-changer/releases).

#### Check your hardware

1. Open **Task Manager** > **Performance**.

1. Click **CPU**, check and note the processor model on the right. An example: AMD Ryzen 7 5800H with Radeon Graphics.

1. Check and note graphics card models under **GPU**. An example:

   * GPU 0: AMD Radeon RX 6600M.

   * GPU 1: AMD Radeon(TM) Graphics.

#### For AMD/Intel/CPU users

1. Download the `voice-changer-windows-amd64-dml.zip` ZIP file.

1. Right-click the ZIP file. In the opened action menu select **7-Zip** > **Extract to "voice-changer-windows-amd64-dml\\"**.

#### For Nvidia users

1. Install an NVIDIA driver compatible with CUDA 13.4. [NVIDIA explains how to check your driver version](https://www.nvidia.com/en-gb/drivers/drivers-faq).

1. Download the CUDA ZIP asset from the release. If it is split into numbered parts, download every part into the same folder.

1. Extract the ZIP with 7-Zip. For a split archive, right-click the `.zip.001` part; 7-Zip reads the remaining parts automatically.

The following examples demonstrate the unpacking process:

* 7-Zip.
  ![unzip_cuda](https://github.com/deiteris/voice-changer/assets/6103913/f33ebb39-b527-462e-bd0c-6007d26aba35)
* WinRAR.
  ![unzip_cuda_winrar](https://github.com/deiteris/voice-changer/assets/6103913/1f8d63db-01b6-427f-9ee9-c674a61d0ecf)

#### Running the voice changer

1. Open the extracted folder (`voice-changer-windows-amd64-dml` or `voice-changer-windows-amd64-cuda`) > `MMVCServerSIO`.

1. Run `MMVCServerSIO.exe`.

When running the voice changer for the first time, it will start downloading necessary files. Do not close the window until the download finishes.

Select **Quit** in the header to stop Voice Changer and Server Audio. Closing the last browser tab opened by the Windows launcher also quits after a short pause for reloads. You can also press **Ctrl+C** in the console. Use `--launch-browser false` to run the server independently of a browser.

Once the download is finished, the voice changer will open the user interface using your default web browser.

### Running locally on macOS

> [!IMPORTANT]
> macOS support is experimental.

#### For Apple Silicon (Apple M1, etc.) users

1. Download the `voice-changer-macos-arm64-cpu.tar.gz` file.

1. Double-click the file. The voice changer will unpack and the `MMVCServerSIO` folder will appear.

#### For Intel users

> [!NOTE]
> The voice changer would work best if your Intel-based machine has AMD graphics. If your machine has only Intel integrated graphics, only CPU will be utilized.

1. Download the `voice-changer-macos-amd64-cpu.tar.gz` file.

1. Double-click the file. The voice changer will unpack and the `MMVCServerSIO` folder will appear.

#### Removing Apple quarantine attribute

> [!WARNING]
> Currently, this step is mandatory. Otherwise, the voice changer will fail to start with an error related to **Python.framework** being damaged. This may be improved in the future.

1. Open Terminal.

1. Run the following command:

   ```
   xattr -dr com.apple.quarantine <Path to extracted MMVCServerSIO folder>
   ```

   For example, if you extracted the voice changer to your desktop, the command may look as follows:

   ```
   xattr -dr com.apple.quarantine ~/Desktop/MMVCServerSIO
   ```

#### Running the voice changer

1. Open the extracted `MMVCServerSIO` folder.

1. Double-click `MMVCServerSIO` to run the voice changer.

### Running on Colab/Kaggle

Use the [Colab](Colab_RealtimeVoiceChanger.ipynb) or [Kaggle](Kaggle_RealtimeVoiceChanger.ipynb) notebook. Each downloads a compatible published Linux CUDA release from the configured GitHub repository, which defaults to this fork. If no compatible release has been published, choose a repository with one in the notebook.

The notebooks prompt for an ngrok account token and a separate username and password to protect visitor access. Keep all three private and enter the visitor credentials in the browser. HRZN is disabled because its visitor access controls have not been verified. Never enable unsafe checkpoint loading when using a public tunnel.

## Troubleshooting

> [!TIP]
> When any issue with the voice changer occurs, check the command line window (the one that opens during the start) for errors.

### Exceptions.PretrainDownloadException: 'Failed to download weight.'

Either the remote files have changed or your files were corrupted. The error will show which files are affected above the error:

```
[WeightDownloader] 'pretrain/content_vec_500.onnx failed to pass hash verification check. Got 1931e237626b80d65ae44cbacd4a5197, expected ab288ca5b540a4a15909a40edf875d1e'
[WeightDownloader] 'pretrain/rmvpe.onnx failed to pass hash verification check. Got 65030149d579a65f15aa7e85769c32f1, expected b6979bf69503f8ec48c135000028a7b0'
```

Find and delete the mentioned files from the voice changer folder and restart the voice changer. Deleted files will be re-downloaded.

### Audio devices are not displayed

1. Make sure that you have given the permission to access the microphone.

1. If you are using Mozilla Firefox ESR, there may be an issue with audio devices. Use other web browser (preferably Chrome or Chromium-based).

### No sound after start

1. Make sure you have selected correct input and output audio devices.

1. Make sure your input device is not muted. Check the microphone volume in the system settings or hardware switch on your headset (usually a button, if present).

### Hearing non-converted voice

In the voice changer, make sure **passthru** is not on (indicated by blinking red color). Click it to switch it off (indicated by solid green color).

![unpassthru](https://github.com/user-attachments/assets/014fd740-d8cb-48f6-8b5c-d53258a34b95)

### Hearing audio crackles

1. Make sure you are using **VAC by Muzychenko** (indicated by the **Line 1** audio device name).

1. In Windows **Sound Control Panel**, make sure that the sample rate of your microphone matches the sample rate of the virtual cable.

   The following example shows the configuration of the virtual cable and the microphone:

   ![image](https://github.com/user-attachments/assets/bd19dcbe-87a8-4e0a-9d3d-baf8015c546c)

   ![image](https://github.com/user-attachments/assets/0e7ae533-3ba5-4308-895e-54254c2a67e0)

1. If nothing helped, in **Task Manager** > **Details**, find "audiodg.exe" process and do the folowing:

   1. Right-click "audiodg.exe" > **Set priority** > **High**.
  
   1. Right-click "audiodg.exe" > **Set affinity**. Uncheck every option, then only select CPU 2.

### Audio is stuttery

1. If you changed chunk when voice conversion was on, click **Stop** then **Start** again.

1. Make sure the **perf** time is smaller than **Chunk**. Increase **Chunk** or reduce **Extra** and **Crossfade size**.

## Contribution

At the moment, the fork does not accept any code contributions. However, feel free to report any issues
you encounter during usage.

## Working with the source

### Prerequisites

1. Install Python 3.12 for CPU, CUDA, or DirectML. For Linux ROCm, use Python 3.10 because the configured ONNX Runtime wheel targets CPython 3.10. Install [Node.js 22](https://nodejs.org/) to build the browser client.

1. [If not installed] Download and install git.

1. Open a command line.

1. Verify your Python version by running the following command:

   ```
   python --version
   Python 3.12.x  # or 3.10.x for ROCm
   ```

1. Clone the repository.

1. Build the browser client from the repository root:

   ```
   cd client/lib
   npm ci
   npm run build:prod
   cd ../demo
   npm ci
   npm run build:mod_copy
   npm run build:prod
   cd ../../server
   ```

   Rebuild it after client changes before running or packaging the server.

### Setting up the environment

1. [If not set up] Set up virtual environment with the following command:

   ```
   python -m venv venv
   ```

1. Activate virtual environment using one of the following commands:

   * For Windows:

     ```
     .\venv\Scripts\activate.ps1
     ```

   * For Linux/macOS:

     ```
     source ./venv/bin/activate
     ```

1. Install the requirements using one of the following commands:

   * For AMD/Intel/CPU (Windows only):

     ```
     pip install -r requirements-common.txt -r requirements-dml.txt
     ```

   * For Nvidia (any OS):

     ```
     pip install -r requirements-common.txt -r requirements-cuda.txt
     ```

   * For AMD ROCm (Linux only):

     ```
     pip install -r requirements-common.txt -r requirements-rocm.txt
     ```

   * For CPU (Linux/macOS only):

     ```
     pip install -r requirements-common.txt -r requirements-cpu.txt
     ```

### Model checkpoint safety

`ALLOW_UNSAFE_RVC_CHECKPOINTS` is off by default. Prefer safetensors or ONNX RVC models. Compatible `.pth` checkpoints can be loaded with restricted weights-only loading on PyTorch 2.10 or newer; older PyTorch versions cannot use that path. If a trusted local file requires unrestricted loading, set `ALLOW_UNSAFE_RVC_CHECKPOINTS=true` in the server environment or `.env` before starting. Unrestricted loading can execute code from the checkpoint: only opt in for trusted local files, and never use this setting with a public tunnel.

### Running the server

Run the server by executing `main.py`.

```
python ./main.py
```

This will run the server with default settings. Note that it will not open the web browser by default, copy the address from command line.

The server listens on loopback. For remote use, put it behind an authenticated reverse proxy or use the notebook’s authenticated tunnel. Remove any non-loopback `HOST` setting from your environment or `.env`, point the proxy upstream at `127.0.0.1:18888` (or your configured port), and set the public browser origin in `ALLOWED_ORIGINS`.

Rebuild the browser client when updating the server. The current browser client reserves a stream at startup. Legacy REST clients can still send audio, but each chunk is converted independently because those requests have no stream ID.

### Building a package

1. [If not installed] Install `pyinstaller` with the following command:

   ```
   pip install --upgrade pip wheel setuptools pyinstaller
   ```

1. Set `BACKEND` to match the installed requirements: `cpu`, `cuda`, `dml`, or `rocm`. For example, in PowerShell:

   ```powershell
   $env:BACKEND = "dml"
   pyinstaller --clean -y --dist ./dist --workpath ./build MMVCServerSIO.spec
   ```

   On Linux or macOS, for example:

   ```sh
   BACKEND=cpu pyinstaller --clean -y --dist ./dist --workpath ./build MMVCServerSIO.spec
   ```

   Choose the matching backend for your installation. The executable is placed in the `dist` folder.
