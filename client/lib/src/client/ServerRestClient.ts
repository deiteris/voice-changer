import { MergeModelRequest, OnnxExporterInfo, ServerInfo, ServerSettingKey } from "../const";
import { pack, unpack } from 'msgpackr';

type FileChunk = {
    hash: number;
    chunk: ArrayBuffer;
};

export class ServerRestClient {
    private serverUrl = "";

    constructor(serverUrl: string) {
        this.serverUrl = serverUrl;
    }

    private request = async (path: string, options?: RequestInit) => {
        const response = await fetch(this.serverUrl + path, options);
        if (!response.ok) {
            let detail = "";
            try {
                const body = await response.json();
                detail = typeof body.detail === "string" ? body.detail : (typeof body.message === "string" ? body.message : "");
            } catch { /* non-JSON error response */ }
            throw new Error(detail || `Request failed (${response.status})`);
        }
        return response;
    };

    private json = async <T>(path: string, options?: RequestInit): Promise<T> => {
        const body = await (await this.request(path, options)).json();
        if (body == null) throw new Error("Server returned an empty response");
        return body as T;
    };

    private postForm = <T>(path: string, values: Record<string, string>, signal?: AbortSignal) => {
        const body = new FormData();
        Object.entries(values).forEach(([key, value]) => body.append(key, value));
        return this.json<T>(path, { method: "POST", body, signal });
    };

    getSettings = () => this.json<ServerInfo>("/info");
    getPerformance = () => this.json<number[]>("/performance");
    updateSettings = (key: ServerSettingKey, val: string) => this.postForm<ServerInfo>("/update_settings", { key, val });

    uploadFile2 = async (dir: string, file: File, onprogress: (progress: number, end: boolean) => void) =>
        new Promise<{ status: number; body: string }>((resolve, reject) => {
            const xhr = new XMLHttpRequest();
            xhr.upload.addEventListener("progress", e => {
                if (e.lengthComputable) onprogress((e.loaded / e.total) * 100, false);
            });
            xhr.addEventListener("load", () => {
                if (xhr.status < 200 || xhr.status >= 300) {
                    let detail = "";
                    try { const body = JSON.parse(xhr.responseText); detail = body.detail || body.message || ""; } catch { /* non-JSON response */ }
                    reject(new Error(detail || `File upload failed (${xhr.status})`));
                    return;
                }
                try {
                    const result = JSON.parse(xhr.responseText);
                    if (!result || result.status !== "OK") throw new Error(result?.msg || "File upload failed");
                } catch (error) {
                    reject(error instanceof Error ? error : new Error("File upload failed"));
                    return;
                }
                resolve({ status: xhr.status, body: xhr.responseText });
            });
            xhr.addEventListener("error", () => reject(new Error("File upload failed")));
            xhr.addEventListener("abort", () => reject(new Error("File upload aborted")));
            xhr.open("POST", this.serverUrl + "/upload_file", true);
            const formData = new FormData();
            formData.append("file", file);
            formData.append("filename", dir + file.name);
            xhr.send(formData);
        });

    uploadFile = async (buf: ArrayBuffer, filename: string, onprogress: (progress: number, end: boolean) => void) => {
        onprogress(0, false);
        const size = 1024 * 1024;
        const fileChunks: FileChunk[] = [];
        let index = 0;
        for (let cur = 0; cur < buf.byteLength; cur += size) {
            fileChunks.push({ hash: index++, chunk: buf.slice(cur, cur + size) });
        }
        const chunkNum = fileChunks.length;
        while (fileChunks.length > 0) {
            const chunks = fileChunks.splice(0, 10);
            await Promise.all(chunks.map(async chunk => {
                const body = new FormData();
                body.append("file", new Blob([chunk.chunk]));
                body.append("filename", `${filename}_${chunk.hash}`);
                const result = await this.json<{ status: string; msg?: string }>("/upload_file", { method: "POST", body });
                if (result.status !== "OK") throw new Error(result.msg || "File upload failed");
            }));
            if (fileChunks.length > 0) onprogress(Math.floor(((chunkNum - fileChunks.length) / (chunkNum + 1)) * 100), false);
        }
        return chunkNum;
    };

    concatUploadedFile = async (filename: string, chunkNum: number) => {
        const body = new FormData();
        body.append("filename", filename);
        body.append("filenameChunkNum", String(chunkNum));
        await this.request("/concat_uploaded_file", { method: "POST", body });
    };

    loadModel = (slot: number, isHalf: boolean, params: string = "{}") =>
        this.postForm<{ status: "OK" }>("/load_model", { slot: String(slot), isHalf: String(isHalf ?? false), params });
    uploadAssets = (params: string) => this.postForm<ServerInfo>("/upload_model_assets", { params });
    getModelType = () => this.json<ServerInfo>("/model_type");
    export2onnx = () => this.json<OnnxExporterInfo>("/onnx");
    mergeModel = (req: MergeModelRequest) => this.postForm<ServerInfo>("/merge_model", { request: JSON.stringify(req) });
    updateModelDefault = () => this.json<ServerInfo>("/update_model_default", { method: "POST" });
    updateModelInfo = (slot: number, key: string, val: string) =>
        this.postForm<ServerInfo>("/update_model_info", { newData: JSON.stringify({ slot, key, val }) });

    // VoiceChangerWorkletNodeから呼び出される
    //// Restで音声変換
    setStream = (streamId: string, active: boolean) =>
        this.postForm<{ status: "OK" }>("/stream", { stream_id: streamId, active: String(active) }, AbortSignal.timeout(5000));

    postVoice = async (timestamp: number, buffer: ArrayBuffer, streamId?: string) => {
        const body = pack(streamId ? [timestamp, buffer, streamId] : [timestamp, buffer])
        const res = await this.request("/test", {
            method: "POST",
            headers: {
                Accept: "application/octet-stream",
                "Content-Type": "application/octet-stream",
            },
            body,
        });
        const data = new Uint8Array(await res.arrayBuffer());

        return unpack(data)
    };
}
