#!/usr/bin/env node
// Prepares a release: bumps the app version and closes the changelog's Unreleased section.
//
//   node scripts/release.mjs <x.y.z>
//
// Run it on a release/* or hotfix/* branch, review the diff, then commit. Nothing is committed or
// tagged here: the Release workflow tags vX.Y.Z when the PR is merged into master.

import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');

const PACKAGES = ['electron', 'rlgym-app'];
const CHANGELOG = 'rlgym-app/CHANGELOG.md';

const version = process.argv[2];
if (!/^\d+\.\d+\.\d+$/.test(version ?? '')) {
  fail('usage: node scripts/release.mjs <x.y.z>');
}

// electron/package.json is the version the app reports and the updater compares against.
const current = readJson('electron/package.json').data.version;
if (compare(version, current) <= 0) {
  fail(`${version} is not greater than the current version ${current}`);
}

// Everything is computed (and validated) before anything is written, so a failure leaves no
// half-bumped files behind.
const writes = [[CHANGELOG, releaseChangelog()]];
for (const pkg of PACKAGES) {
  writes.push([`${pkg}/package.json`, withVersion(`${pkg}/package.json`, (json) => {
    json.version = version;
  })]);
  writes.push([`${pkg}/package-lock.json`, withVersion(`${pkg}/package-lock.json`, (json) => {
    json.version = version;
    json.packages[''].version = version;
  })]);
}
for (const [path, text] of writes) {
  writeFileSync(join(root, path), text);
}

console.log(`Version ${current} -> ${version}. Review the diff, then commit:`);
console.log(`  git commit -am "RLGYM-<n> Release ${version}"`);

function releaseChangelog() {
  const { text, eol } = readText(CHANGELOG);
  const lines = text.split(eol);

  const start = lines.indexOf('## Unreleased');
  if (start === -1) fail(`${CHANGELOG} has no "## Unreleased" heading`);
  if (lines.some((line) => line.startsWith(`## [${version}]`))) {
    fail(`${CHANGELOG} already has a section for ${version}`);
  }

  let end = lines.findIndex((line, i) => i > start && line.startsWith('## '));
  if (end === -1) end = lines.length;
  if (lines.slice(start + 1, end).every((line) => line.trim() === '')) {
    fail(`"## Unreleased" in ${CHANGELOG} is empty: nothing to release`);
  }

  const date = new Date().toISOString().slice(0, 10);
  lines.splice(start + 1, 0, '', `## [${version}] - ${date}`);
  return lines.join(eol);
}

function withVersion(path, change) {
  const { data, eol } = readJson(path);
  change(data);
  return (JSON.stringify(data, null, 2) + '\n').replaceAll('\n', eol);
}

function readJson(path) {
  const { text, eol } = readText(path);
  return { data: JSON.parse(text), eol };
}

// Keeps the file's line endings (CRLF on Windows checkouts with autocrlf).
function readText(path) {
  const text = readFileSync(join(root, path), 'utf8');
  return { text, eol: text.includes('\r\n') ? '\r\n' : '\n' };
}

function compare(a, b) {
  const [pa, pb] = [a, b].map((v) => v.split('.').map(Number));
  for (let i = 0; i < 3; i++) {
    if (pa[i] !== pb[i]) return pa[i] - pb[i];
  }
  return 0;
}

function fail(message) {
  console.error(`error: ${message}`);
  process.exit(1);
}
