#!/usr/bin/env node
// The three places a release number is written must agree.
//
//   node tools/version.test.mjs
//
// package.json is the source of truth. The README quotes the current release
// in prose and the CHANGELOG's top heading names it, and both were written by
// hand -- so 0.5.0 shipped with the README still saying 0.4.0 and nothing
// noticed, because a stale sentence breaks no build and renders perfectly.
//
// THE FAILURE MODE THIS GUARDS IS THE CHECK GOING QUIET, not the numbers
// disagreeing. If someone rewords the README and drops "(currently vX.Y.Z)",
// a regex that simply finds no match would pass forever and this file would
// become decoration -- the same trap as the enamel detector that scored 100%
// because SURFACE_MM is painted unconditionally (CLAUDE.md, enamel section c).
// So a missing marker is a FAILURE, not a skip.

import { readFile } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = dirname(dirname(fileURLToPath(import.meta.url)));
const read = (f) => readFile(join(ROOT, f), 'utf8');

const fail = [];
const { version } = JSON.parse(await read('package.json'));
if (!/^\d+\.\d+\.\d+$/.test(version ?? '')) {
  fail.push(`package.json version is ${JSON.stringify(version)}, not x.y.z`);
}

// README: the "(currently vX.Y.Z)" the live link is captioned with.
const readme = await read('README.md');
const inReadme = readme.match(/\(currently v(\d+\.\d+\.\d+)\)/);
if (!inReadme) {
  fail.push('README.md has no "(currently vX.Y.Z)" marker -- either it was ' +
            'reworded, in which case update this check, or the caption was ' +
            'dropped and the release number is no longer stated anywhere a ' +
            'reader looks first');
} else if (inReadme[1] !== version) {
  fail.push(`README.md says v${inReadme[1]}, package.json says ${version}`);
}

// CHANGELOG: the topmost release heading.
const changelog = await read('CHANGELOG.md');
const inLog = changelog.match(/^## \[(\d+\.\d+\.\d+)\]/m);
if (!inLog) {
  fail.push('CHANGELOG.md has no "## [x.y.z]" release heading');
} else if (inLog[1] !== version) {
  fail.push(`CHANGELOG.md's newest release is ${inLog[1]}, ` +
            `package.json says ${version}`);
}

if (fail.length) {
  console.error('version drift:');
  for (const f of fail) console.error(`  - ${f}`);
  console.error('\nBump all three together, or the atlas tells its readers it ' +
                'is a release behind.');
  process.exit(1);
}
console.log(`version ${version} agrees across package.json, README and CHANGELOG`);
