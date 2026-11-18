const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');

const source = fs.readFileSync(path.join(__dirname, '../src/client/ServerRestClient.ts'), 'utf8');
const js = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 } }).outputText;
const exportsForTest = {};
new Function('require', 'exports', js)(require, exportsForTest);
const client = new exportsForTest.ServerRestClient('http://localhost');

test('REST calls propagate network, JSON, HTTP and empty-response failures', async () => {
    global.fetch = async () => { throw new Error('offline'); };
    await assert.rejects(client.getSettings(), /offline/);
    global.fetch = async () => new Response('invalid JSON');
    await assert.rejects(client.getSettings(), SyntaxError);
    global.fetch = async () => Response.json({ message: 'model failed' }, { status: 500 });
    await assert.rejects(client.loadModel(4, false), /model failed/);
    global.fetch = async () => Response.json(null);
    await assert.rejects(client.getSettings(), /empty response/);
});

test('REST success returns server data and sends the selected slot', async () => {
    global.fetch = async (_url, options) => {
        assert.equal(options.body.get('slot'), '4');
        assert.equal(JSON.parse(options.body.get('params')).slot, 4);
        return Response.json({ status: 'OK' });
    };
    assert.deepEqual(await client.loadModel(4, false, JSON.stringify({ slot: 4 })), { status: 'OK' });
});

test('file uploads reject server failures and accept successful responses', async () => {
    class MockXHR {
        upload = { addEventListener() {} };
        handlers = {};
        addEventListener(event, callback) { this.handlers[event] = callback; }
        open() {}
        send() { this.handlers.load(); }
    }
    global.XMLHttpRequest = MockXHR;
    const file = new File(['x'], 'model.pth');
    MockXHR.prototype.status = 500;
    MockXHR.prototype.responseText = '{"message":"disk full"}';
    await assert.rejects(client.uploadFile2('', file, () => {}), /disk full/);
    MockXHR.prototype.status = 200;
    MockXHR.prototype.responseText = 'null';
    await assert.rejects(client.uploadFile2('', file, () => {}), /upload failed/);
    MockXHR.prototype.responseText = '{"status":"OK"}';
    assert.equal((await client.uploadFile2('', file, () => {})).status, 200);
});
