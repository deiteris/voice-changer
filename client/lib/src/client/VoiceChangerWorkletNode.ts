import { VoiceChangerWorkletProcessorRequest } from "../../worklet/src/voice-changer-worklet-processor";
import {
  DefaultClientSettng,
  //DownSamplingMode,
  VOICE_CHANGER_CLIENT_EXCEPTION,
  WorkletNodeSetting,
  WorkletSetting,
} from "../const";
import { io, Socket } from "socket.io-client";
import { DefaultEventsMap } from "@socket.io/component-emitter";
import { ServerRestClient } from "./ServerRestClient";
import * as msgpackrParser from "./sio/msgpackr";

export type VoiceChangerWorkletListener = {
  notifySendBufferingTime: (time: number) => void;
  notifyPerformanceStats: (ping: number, vol: number, perf: number[]) => void;
  notifyException: (
    code: VOICE_CHANGER_CLIENT_EXCEPTION,
    message: string
  ) => void;
};

export class VoiceChangerWorkletNode extends AudioWorkletNode {
  private listener: VoiceChangerWorkletListener;

  private setting: WorkletNodeSetting = DefaultClientSettng.workletNodeSetting;
  private streamSession?: { id: string; client: ServerRestClient };
  private streamOperation = Promise.resolve();
  private reservingStream = false;
  private requestChunks: Int16Array = new Int16Array(this.setting.inputChunkNum * 128);
  private chunkCounter: number = 0;
  private socket: Socket<DefaultEventsMap, DefaultEventsMap> | null = null;
  // performance monitor
  private bufferStart = 0;

  private isOutputRecording = false;
  private recordingOutputChunk: Float32Array[] = [];
  private outputNode: VoiceChangerWorkletNode | null = null;

  // Promises
  private startPromiseResolve:
    | ((value: void | PromiseLike<void>) => void)
    | null = null;
  private stopPromiseResolve:
    | ((value: void | PromiseLike<void>) => void)
    | null = null;

  constructor(context: AudioContext, listener: VoiceChangerWorkletListener) {
    super(context, "voice-changer-worklet-processor");
    this.port.onmessage = (event) => {
      if (event.data.responseType !== "inputData" || this.streamSession) {
        this.handleMessage(event);
      }
    };
    this.listener = listener;
    console.log(`[worklet_node][voice-changer-worklet-processor] created.`);
  }

  setOutputNode = (outputNode: VoiceChangerWorkletNode | null) => {
    this.outputNode = outputNode;
  };

  // 設定
  updateSetting = (setting: WorkletNodeSetting) => {
    if ((this.streamSession || this.reservingStream) && setting.serverUrl !== this.setting.serverUrl) {
      throw new Error("Stop voice conversion before changing servers.");
    }

    console.log(
      `[WorkletNode] Updating WorkletNode Setting,`,
      this.setting,
      setting
    );

    // Realloc buffer for both input and output nodes if chunk size has changed.
    if (setting.inputChunkNum !== this.setting.inputChunkNum) {
      this.requestChunks = new Int16Array(setting.inputChunkNum * 128);
      this.chunkCounter = 0;
    }

    // Do not connect output worklet to server on protocol change.
    // TODO: Refactor
    if (!this.outputNode) {
      let recreateSocketIoRequired = (
        this.setting.serverUrl !== setting.serverUrl ||
        this.setting.protocol !== setting.protocol
      );

      this.setting = setting;
      if (recreateSocketIoRequired) {
        this.createSocketIO();
      }
    } else {
      this.setting = setting;
    }
  };

  getSettings = (): WorkletNodeSetting => {
    return this.setting;
  };

  getSocketId = () => {
    return this.socket?.id;
  };

  // 処理
  createSocketIO = () => {
    if (this.socket) {
      this.socket.close();
    }
    if (this.setting.protocol === "sio") {
      this.socket = io(this.setting.serverUrl + "/test", { parser: msgpackrParser });
      this.socket.on("connect_error", (err) => {
        this.listener.notifyException(
          VOICE_CHANGER_CLIENT_EXCEPTION.ERR_SIO_CONNECT_FAILED,
          `[SIO] rconnection failed ${err}`
        );
      });
      this.socket.on("disconnect", () => {
        this.chunkCounter = 0;
      });
      this.socket.on("connect", () => {
        console.log(`[SIO] connect to ${this.setting.serverUrl}`);
        console.log(`[SIO] ${this.socket?.id}`);
      });
      this.socket.on("close", function (socket) {
        console.log(`[SIO] close ${socket.id}`);
      });

      this.socket.on("message", (response: any[]) => {
        console.log("message:", response);
      });

      this.socket.on("error", (response: any) => {
        const [error_code, error_message] = response;
        if (error_code === 'ERR_SAMPLE_RATE_NOT_SUPPORTED' || error_code === 'STREAM_INACTIVE') {
          this.listener.notifyException(error_code, error_message)
        } else {
          this.listener.notifyException(
            "ERR_GENERIC_VOICE_CHANGER_EXCEPTION",
            "An error occurred during voice conversion. Check command line window for more details."
          )
        }
      });

      // Dedicated message for server mode
      this.socket.on("server_stats", (response: any[]) => {
        const [vol, perf] = response;
        // There is no response delay in server mode.
        this.listener.notifyPerformanceStats(0, vol, perf);
      });

      this.socket.on("response", (response: any[]) => {
        const [sendTimestamp, audio, ping, vol, perf, streamId] = response
        if ((streamId ?? undefined) !== this.streamSession?.id) return;
        // NOTE: Large integers are packed as BigInt
        const totalPing = Date.now() - Number(sendTimestamp) + ping;

        if (audio.byteLength < 128 * 2) {
          this.listener.notifyException(
            VOICE_CHANGER_CLIENT_EXCEPTION.ERR_SIO_INVALID_RESPONSE,
            `[SIO] Received data is too short ${audio.byteLength}`
          );
        } else {
          if (this.outputNode != null) {
            this.outputNode.postReceivedVoice(audio);
          } else {
            this.postReceivedVoice(audio);
          }
          this.listener.notifyPerformanceStats(totalPing, vol, perf);
        }
      });
    }
  };

  postReceivedVoice = (u8data: Uint8Array) => {
    // Array view is Uint8, but received data is actually Int16.
    const dataLength = Math.floor(u8data.length / 2)
    const f32Data = new Float32Array(dataLength);
    // console.log(`[worklet] f32DataLength${f32Data.length} i16DataLength${i16Data.length}`)
    for (let i = 0; i < dataLength; i++) {
      const x = (u8data[i * 2 + 1] << 8) | u8data[i * 2];
      f32Data[i] = x >= 0x8000 ? -(0x10000 - x) / 0x8000 : x / 0x7fff;
    }

    if (this.isOutputRecording) {
      this.recordingOutputChunk.push(f32Data.slice());
    }

    const req: VoiceChangerWorkletProcessorRequest = {
      requestType: "voice",
      voice: f32Data,
    };
    this.port.postMessage(req, [f32Data.buffer]);
  };

  handleMessage(event: any) {
    // console.log(`[Node:handleMessage_] `, event.data.volume);
    if (event.data.responseType === "start_ok") {
      if (this.startPromiseResolve) {
        this.startPromiseResolve();
        this.startPromiseResolve = null;
      }
    } else if (event.data.responseType === "stop_ok") {
      if (this.stopPromiseResolve) {
        this.stopPromiseResolve();
        this.stopPromiseResolve = null;
      }
    } else if (event.data.responseType === "inputData") {
      // Socket.IO queues emits while disconnected; never replay stale microphone audio.
      if (this.setting.protocol === "sio" && !this.socket?.connected) {
        this.chunkCounter = 0;
        return;
      }
      const inputData = event.data.inputData as Float32Array;
      // console.log("receive input data", inputData);

      // Float to Int16 (internalの場合はfloatのまま行く。)
      const offset = inputData.length * this.chunkCounter;
      for (let i = 0; i < inputData.length; i++) {
        let s = Math.max(-1, Math.min(1, inputData[i]));
        this.requestChunks[offset + i] = s < 0 ? s * 0x8000 : s * 0x7fff;
      }

      //// リクエストバッファの中身が、リクエスト送信数と違う場合は処理終了。
      if (this.chunkCounter < this.setting.inputChunkNum - 1) {
        this.chunkCounter++;
        return;
      }

      this.sendBuffer(this.requestChunks.buffer);
      this.chunkCounter = 0;

      this.listener.notifySendBufferingTime(Date.now() - this.bufferStart);
      this.bufferStart = Date.now();
    } else {
      console.warn(
        `[worklet_node][voice-changer-worklet-processor] unknown response ${event.data.responseType}`,
        event.data
      );
    }
  }

  private sendBuffer = async (newBuffer: ArrayBuffer) => {
    const timestamp = Date.now();
    const stream = this.streamSession;
    if (this.setting.protocol === "sio") {
      if (!this.socket?.connected) {
        this.chunkCounter = 0;
        return;
      }
      // console.log("emit!")
      this.socket.emit("request_message", stream ? [timestamp, newBuffer, stream.id] : [timestamp, newBuffer]);
    } else if (this.setting.protocol === "rest") {
      const restClient = stream?.client ?? new ServerRestClient(this.setting.serverUrl);
      let data;
      try {
        data = await restClient.postVoice(timestamp, newBuffer, stream?.id);
      } catch (error) {
        this.listener.notifyException(
          "ERR_GENERIC_VOICE_CHANGER_EXCEPTION",
          `Voice conversion request failed: ${error instanceof Error ? error.message : String(error)}`
        );
        return;
      }
      if (stream !== this.streamSession) return;
      const totalPing = Date.now() - Number(data.sendTimestamp) + data.ping;
      if (data.error) {
        const { code, message } = data.details
        if (code === 'ERR_SAMPLE_RATE_NOT_SUPPORTED' || code === 'STREAM_INACTIVE') {
          this.listener.notifyException(code, message)
        } else {
          this.listener.notifyException(
            "ERR_GENERIC_VOICE_CHANGER_EXCEPTION",
            "An error occurred during voice conversion. Check command line window for more details."
          )
        }
        return;
      }
      const audio = data.audio

      if (audio.byteLength < 128 * 2) {
        this.listener.notifyException(
          VOICE_CHANGER_CLIENT_EXCEPTION.ERR_SIO_INVALID_RESPONSE,
          `[REST] Received data is too short ${audio.byteLength}`
        );
      } else {
        if (this.outputNode != null) {
          this.outputNode.postReceivedVoice(audio);
        } else {
          this.postReceivedVoice(audio);
        }
      }
      this.listener.notifyPerformanceStats(totalPing, data.vol, data.perf);
    } else {
      throw "unknown protocol";
    }
  };

  // Worklet操作
  configure = (_: WorkletSetting) => {
    const req: VoiceChangerWorkletProcessorRequest = {
      requestType: "config",
      voice: new Float32Array(1),
    };
    this.port.postMessage(req);
  };

  private queueStreamOperation = (operation: () => Promise<void>) => {
    const result = this.streamOperation.then(operation);
    this.streamOperation = result.catch(() => {});
    return result;
  };

  private sendWorkletCommand = (requestType: "start" | "stop") => new Promise<void>((resolve, reject) => {
    const timeout = setTimeout(() => reject(new Error(`Audio processor did not acknowledge ${requestType}.`)), 5000);
    const acknowledge = () => {
      clearTimeout(timeout);
      resolve();
    };
    if (requestType === "start") {
      this.startPromiseResolve = acknowledge;
    } else {
      this.stopPromiseResolve = acknowledge;
    }
    try {
      this.port.postMessage({ requestType, voice: new Float32Array(1) });
    } catch (error) {
      clearTimeout(timeout);
      reject(error);
    }
  });

  start = () => this.queueStreamOperation(async () => {
    if (this.streamSession) return;
    const stream = { id: crypto.randomUUID(), client: new ServerRestClient(this.setting.serverUrl) };
    this.reservingStream = true;
    try {
      await stream.client.setStream(stream.id, true);
    } finally {
      this.reservingStream = false;
    }
    this.streamSession = stream;
    this.requestChunks = new Int16Array(this.setting.inputChunkNum * 128);
    this.chunkCounter = 0;
    try {
      (this.outputNode ?? this).trancateBuffer();
      await this.sendWorkletCommand("start");
    } catch (error) {
      this.startPromiseResolve = null;
      this.streamSession = undefined;
      try {
        this.port.postMessage({ requestType: "stop", voice: new Float32Array(1) });
      } catch { /* The processor may already be closed. */ }
      await stream.client.setStream(stream.id, false).catch(() => {});
      throw error;
    }
  });

  stop = () => this.queueStreamOperation(async () => {
    const stream = this.streamSession;
    if (!stream) return;
    try {
      await this.sendWorkletCommand("stop");
    } finally {
      this.stopPromiseResolve = null;
      this.streamSession = undefined;
      try {
        (this.outputNode ?? this).trancateBuffer();
      } finally {
        await stream.client.setStream(stream.id, false);
      }
    }
  });
  trancateBuffer = () => {
    const req: VoiceChangerWorkletProcessorRequest = {
      requestType: "trancateBuffer",
      voice: new Float32Array(1),
    };
    this.port.postMessage(req);
  };

  startOutputRecording = () => {
    this.recordingOutputChunk = [];
    this.isOutputRecording = true;
  };
  stopOutputRecording = () => {
    this.isOutputRecording = false;

    const dataSize = this.recordingOutputChunk.reduce((prev, cur) => {
      return prev + cur.length;
    }, 0);
    const samples = new Float32Array(dataSize);
    let sampleIndex = 0;
    for (let i = 0; i < this.recordingOutputChunk.length; i++) {
      for (let j = 0; j < this.recordingOutputChunk[i].length; j++) {
        samples[sampleIndex] = this.recordingOutputChunk[i][j];
        sampleIndex++;
      }
    }
    return samples;
  };
}
