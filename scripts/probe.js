// Launch an MCP server over stdio, send ONLY initialize + notifications/initialized + tools/list
// (following nextCursor pages), print the result as JSON on stdout, then kill the server.
// No tool is ever called.  Usage: node probe.js <timeoutMs> -- <command> [args...]
const { spawn } = require('child_process');
const timeoutMs = parseInt(process.argv[2], 10) || 30000;
const sep = process.argv.indexOf('--');
const [cmd, ...args] = process.argv.slice(sep + 1);
const child = spawn(cmd, args, { stdio: ['pipe', 'pipe', 'pipe'], env: process.env, detached: true });
let buf = '', stderr = '', nextId = 1; const pending = new Map();
const out = { initialize: null, tools: [], pages: 0, error: null, stderr_tail: '' };
function finish(code) {
  out.stderr_tail = stderr.slice(-2000);
  try { process.kill(-child.pid, 'SIGKILL'); } catch (e) { try { child.kill('SIGKILL'); } catch (_) {} }
  // write via callback so large tool lists (>64 KB) are fully flushed before exit
  process.stdout.write(JSON.stringify(out), () => process.exit(code));
}
const timer = setTimeout(() => { out.error = out.error || `timeout after ${timeoutMs}ms`; finish(2); }, timeoutMs);
child.stderr.on('data', d => { stderr += d.toString(); if (stderr.length > 20000) stderr = stderr.slice(-10000); });
child.on('exit', (code, sig) => { if (!out.done) { out.error = out.error || `server exited early code=${code} sig=${sig}`; clearTimeout(timer); finish(3); } });
child.on('error', e => { out.error = 'spawn error: ' + e.message; clearTimeout(timer); finish(4); });
child.stdout.on('data', d => {
  buf += d.toString(); let i;
  while ((i = buf.indexOf('\n')) >= 0) {
    const line = buf.slice(0, i).trim(); buf = buf.slice(i + 1);
    if (!line.startsWith('{')) continue;            // ignore stray log lines on stdout
    let msg; try { msg = JSON.parse(line); } catch (e) { continue; }
    if (msg.id !== undefined && pending.has(msg.id)) { const r = pending.get(msg.id); pending.delete(msg.id); r(msg); }
  }
});
function rpc(method, params) {
  const id = nextId++;
  return new Promise(res => { pending.set(id, res); child.stdin.write(JSON.stringify({ jsonrpc: '2.0', id, method, params }) + '\n'); });
}
(async () => {
  const init = await rpc('initialize', { protocolVersion: '2025-06-18', capabilities: {}, clientInfo: { name: 'tool-drift-probe', version: '1.0.0' } });
  if (init.error) { out.error = 'initialize error: ' + JSON.stringify(init.error); out.done = true; clearTimeout(timer); return finish(5); }
  out.initialize = init.result;
  child.stdin.write(JSON.stringify({ jsonrpc: '2.0', method: 'notifications/initialized' }) + '\n');
  let cursor;
  do {
    const r = await rpc('tools/list', cursor ? { cursor } : {});
    if (r.error) { out.error = 'tools/list error: ' + JSON.stringify(r.error); break; }
    out.tools.push(...(r.result.tools || [])); out.pages++;
    cursor = r.result.nextCursor;
  } while (cursor && out.pages < 50);
  out.done = true; clearTimeout(timer); finish(out.error ? 6 : 0);
})();
