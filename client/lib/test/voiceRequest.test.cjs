const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const ts = require("typescript");

test("failed REST audio requests notify the listener without an unhandled rejection", async () => {
    global.AudioWorkletNode = class { constructor() { this.port = {}; } };
    const source = fs.readFileSync(path.join(__dirname, "../src/client/VoiceChangerWorkletNode.ts"), "utf8");
    const js = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 } }).outputText;
    const exportsForTest = {};
    const mockRequire = (id) => {
        if (id === "../const") return { DefaultClientSettng: { workletNodeSetting: { inputChunkNum: 1, protocol: "rest", serverUrl: "" } } };
        if (id === "./ServerRestClient") return { ServerRestClient: class { async postVoice() { throw new Error("offline"); } } };
        if (id === "socket.io-client" || id === "./sio/msgpackr") return {};
        return require(id);
    };
    new Function("require", "exports", js)(mockRequire, exportsForTest);
    const errors = [];
    const node = new exportsForTest.VoiceChangerWorkletNode({}, { notifyException: (...args) => errors.push(args) });
    await node.sendBuffer(new ArrayBuffer(256));
    assert.equal(errors.length, 1);
    assert.match(errors[0][1], /offline/);
});


test("disconnected Socket.IO audio is discarded and partial chunks are reset", async () => {
    global.AudioWorkletNode = class { constructor() { this.port = {}; } };
    const source = fs.readFileSync(path.join(__dirname, "../src/client/VoiceChangerWorkletNode.ts"), "utf8");
    const js = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 } }).outputText;
    const exportsForTest = {};
    const mockRequire = (id) => {
        if (id === "../const") return { DefaultClientSettng: { workletNodeSetting: { inputChunkNum: 2, protocol: "sio", serverUrl: "" } } };
        if (id === "./ServerRestClient" || id === "socket.io-client" || id === "./sio/msgpackr") return {};
        return require(id);
    };
    new Function("require", "exports", js)(mockRequire, exportsForTest);
    const sent = [];
    const node = new exportsForTest.VoiceChangerWorkletNode({}, { notifySendBufferingTime() {} });
    const socket = { connected: true, emit: (_event, data) => sent.push(new Int16Array(data[1]).slice()) };
    node.socket = socket;
    const input = (value) => node.handleMessage({ data: { responseType: "inputData", inputData: new Float32Array(128).fill(value) } });
    input(0.1);
    socket.connected = false;
    input(0.2);
    await node.sendBuffer(new ArrayBuffer(512));
    assert.equal(sent.length, 0);
    socket.connected = true;
    input(0.3);
    assert.equal(sent.length, 0);
    input(0.4);
    assert.equal(sent.length, 1);
    assert.equal(sent[0][0], Math.trunc(0.3 * 0x7fff));
    assert.equal(sent[0][128], Math.trunc(0.4 * 0x7fff));
});
