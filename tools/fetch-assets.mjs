#!/usr/bin/env node
// Fetch the BodyParts3D source meshes this project uses.
//
// The STLs are vendored into the repo, so you should not normally need to run
// this. It exists to document provenance and make the vendored copies auditable:
// re-run it and `git diff` should be empty.
//
//   node tools/fetch-assets.mjs           # skip files already present
//   node tools/fetch-assets.mjs --force   # re-download everything

import { createHash } from 'node:crypto';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { STRUCTURES, SOURCE_BASE } from './manifest.mjs';

const ROOT = dirname(dirname(fileURLToPath(import.meta.url)));
const STL_DIR = join(ROOT, 'assets', 'source', 'stl');
const LOCK = join(ROOT, 'assets', 'source', 'provenance.json');

const force = process.argv.includes('--force');

const sha256 = (buf) => createHash('sha256').update(buf).digest('hex');

async function main() {
  await mkdir(STL_DIR, { recursive: true });

  const provenance = {
    source: 'BodyParts3D, (c) The Database Center for Life Science',
    license: 'CC Attribution-Share Alike 2.1 Japan',
    release: '3.0 (2011-09-15)',
    mirror: SOURCE_BASE,
    retrieved: new Date().toISOString().slice(0, 10),
    files: {},
  };

  let fetched = 0;
  let skipped = 0;

  for (const { fma, name } of STRUCTURES) {
    const dest = join(STL_DIR, `${fma}.stl`);
    let buf;

    if (existsSync(dest) && !force) {
      buf = await readFile(dest);
      skipped++;
    } else {
      const res = await fetch(`${SOURCE_BASE}/${fma}.stl`);
      if (!res.ok) throw new Error(`${fma} (${name}): HTTP ${res.status}`);
      buf = Buffer.from(await res.arrayBuffer());
      // Binary STL: 80-byte header + uint32 triangle count + 50 bytes/triangle.
      // A short file here means we saved an HTML error page, not a mesh.
      if (buf.length < 134) throw new Error(`${fma} (${name}): got ${buf.length} bytes, not an STL`);
      await writeFile(dest, buf);
      fetched++;
    }

    provenance.files[fma] = {
      name,
      bytes: buf.length,
      triangles: buf.readUInt32LE(80),
      sha256: sha256(buf),
    };
  }

  await writeFile(LOCK, JSON.stringify(provenance, null, 2) + '\n');

  const total = Object.values(provenance.files).reduce((n, f) => n + f.triangles, 0);
  console.log(`${STRUCTURES.length} structures (${fetched} fetched, ${skipped} already present)`);
  console.log(`${total.toLocaleString()} triangles total`);
  console.log(`provenance written to assets/source/provenance.json`);
}

main().catch((err) => {
  console.error(`fetch failed: ${err.message}`);
  process.exit(1);
});
