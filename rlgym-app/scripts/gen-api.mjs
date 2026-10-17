// Regenerate src/app/api from rlgym-server/openapi.json (settings in openapitools.json).
// Files are overwritten in place rather than wiping the folder first, so a running `ng serve`
// never sees the client missing; files the new spec no longer produces are removed afterwards.
import { spawnSync } from 'node:child_process';
import { existsSync, readFileSync, rmSync } from 'node:fs';
import { join } from 'node:path';

const out = 'src/app/api';
const manifest = join(out, '.openapi-generator/FILES');
const listFiles = () =>
  existsSync(manifest) ? readFileSync(manifest, 'utf8').split(/\r?\n/).filter(Boolean) : [];

const before = listFiles();
const { status } = spawnSync('openapi-generator-cli generate', { stdio: 'inherit', shell: true });
if (status !== 0) process.exit(status ?? 1);

const after = new Set(listFiles());
for (const file of before) {
  if (!after.has(file)) rmSync(join(out, file), { force: true });
}
