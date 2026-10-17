// Export the FastAPI schema to rlgym-server/openapi.json (only rewritten when the API changed).
// Uses rlgym-server/.venv when it exists, otherwise the `python` on PATH (CI).
import { spawnSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const server = fileURLToPath(new URL('../../rlgym-server/', import.meta.url));
const venvPython = process.platform === 'win32'
  ? `${server}.venv/Scripts/python.exe`
  : `${server}.venv/bin/python`;
const python = existsSync(venvPython) ? venvPython : 'python';

const { status } = spawnSync(python, ['scripts/export_openapi.py'], { cwd: server, stdio: 'inherit' });
process.exit(status ?? 1);
