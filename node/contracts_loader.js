const { execFileSync } = require('child_process');
const path = require('path');

function renderSlice({ vendor='codex', slice='roles,tools', fmt='text', sidecar='contracts.min.json' } = {}) {
  const execRoot = process.env.LLMC_EXEC_ROOT || path.join(__dirname, '..');
  const scriptPath = path.join(execRoot, 'scripts', 'contracts_render.py');
  return execFileSync('python3', [scriptPath, '--vendor', vendor, '--slice', slice, '--format', fmt, '--sidecar', sidecar], { encoding: 'utf8' }).trim();
}
module.exports = { renderSlice };