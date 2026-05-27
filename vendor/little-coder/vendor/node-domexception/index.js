// Drop-in replacement for the deprecated `node-domexception@1.0.0` shim.
// Bundled with little-coder; wired in via `package.json#overrides` so the
// transitive `fetch-blob -> node-domexception` chain (pulled in via
// @earendil-works/pi-ai -> @google/genai -> google-auth-library -> gaxios ->
// node-fetch -> fetch-blob) doesn't emit a deprecation warning during
// `npm install -g little-coder`. Native `globalThis.DOMException` has been
// available since Node 18, and little-coder requires Node >= 22.19, so this
// is always defined at import time.
module.exports = globalThis.DOMException;
