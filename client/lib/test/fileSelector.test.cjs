const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const ts = require("typescript");

const source = fs.readFileSync(path.join(__dirname, "../src/util.ts"), "utf8");
const js = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 } }).outputText;
const exportsForTest = {};
new Function("require", "exports", js)(require, exportsForTest);

test("fileSelector accepts matching MIME types and rejects nonmatches", async () => {
    class Input {
        click() { this.onchange({ target: this }); }
    }
    global.HTMLInputElement = Input;
    let selected = { name: "image.png", type: "image/png" };
    global.document = { createElement() { const input = new Input(); input.files = [selected]; return input; } };
    assert.equal(await exportsForTest.fileSelector("^image/"), selected);
    selected = { name: "model.pth", type: "application/octet-stream" };
    await assert.rejects(exportsForTest.fileSelector("^image/"), /not target file type/);
    assert.equal(await exportsForTest.fileSelector(""), selected);
});
