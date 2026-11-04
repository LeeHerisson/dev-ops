import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';
import { createHash } from 'node:crypto';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const evidence = path.join(root, 'evidence');
fs.mkdirSync(evidence, { recursive: true });
const commands = [];
const containers = new Set();
const stamp = Date.now();
const platform = process.env.LAB5_PLATFORM || 'linux/arm64';
const tags = { baseline: 'devops-lab5-baseline:local', optimized: 'devops-lab5-optimized:local' };
const save = (name, value) => fs.writeFileSync(path.join(evidence, name), typeof value === 'string' ? value : JSON.stringify(value, null, 2) + '\n');

function command(program, args, filename, { allowFailure = false } = {}) {
  console.log(`$ ${program} ${args.join(' ')}`);
  const began = performance.now();
  const result = spawnSync(program, args, { cwd: root, encoding: 'utf8', maxBuffer: 64 * 1024 * 1024 });
  const durationSeconds = Number(((performance.now() - began) / 1000).toFixed(3));
  const output = `$ ${program} ${args.join(' ')}\n\n${result.stdout || ''}${result.stderr || ''}`;
  save(filename, output);
  commands.push({ program, args, exitCode: result.status, durationSeconds, evidence: filename });
  save('commands.json', commands);
  if (!allowFailure && result.status !== 0) throw new Error(`${program} failed (${result.status}); see evidence/${filename}`);
  return result.stdout?.trim() || '';
}

async function responseSnapshot(url, filename) {
  const response = await fetch(url, { signal: AbortSignal.timeout(5000) });
  const body = await response.text();
  const snapshot = { url, status: response.status, headers: Object.fromEntries(response.headers), body };
  save(filename, snapshot);
  return snapshot;
}

async function checkImage(kind) {
  const name = `devops-lab5-${kind}-check-${stamp}`;
  command('docker', ['run', '-d', '--name', name, '--label', 'devops.lab=5', '-p', '127.0.0.1::3000', tags[kind]], `${kind}-run.txt`);
  containers.add(name);
  const binding = command('docker', ['port', name, '3000/tcp'], `${kind}-port.txt`).split('\n')[0];
  const origin = `http://${binding}`;
  let ready = false;
  for (let attempt = 0; attempt < 90; attempt += 1) {
    try {
      const response = await fetch(`${origin}/api/health`, { signal: AbortSignal.timeout(1000) });
      if (response.ok) { ready = true; break; }
    } catch {}
    await new Promise(resolve => setTimeout(resolve, 500));
  }
  assert.ok(ready, `${kind} API did not become ready`);
  const home = await responseSnapshot(`${origin}/`, `${kind}-http-home.json`);
  assert.equal(home.status, 200);
  assert.match(home.body, /Docker Blog/);
  const health = await responseSnapshot(`${origin}/api/health`, `${kind}-http-health.json`);
  assert.equal(health.status, 200);
  assert.equal(JSON.parse(health.body).status, 'ok');
  const posts = await responseSnapshot(`${origin}/api/posts`, `${kind}-http-posts.json`);
  assert.equal(posts.status, 200);
  assert.equal(JSON.parse(posts.body).length, 3);
  const spa = await responseSnapshot(`${origin}/posts/1`, `${kind}-http-spa.json`);
  assert.equal(spa.status, 200);
  assert.equal(spa.body, home.body);
  const assets = [...home.body.matchAll(/(?:src|href)="(\/static\/[^\"]+)"/g)].map(match => match[1]);
  assert.ok(assets.some(asset => asset.endsWith('.js')), 'CRA JavaScript bundle missing');
  assert.ok(assets.some(asset => asset.endsWith('.css')), 'CRA CSS bundle missing');
  const assetChecks = [];
  for (const asset of assets) {
    const response = await fetch(origin + asset, { signal: AbortSignal.timeout(5000) });
    const body = Buffer.from(await response.arrayBuffer());
    assert.equal(response.status, 200);
    assert.ok(body.length > 0);
    assert.match(response.headers.get('content-type'), asset.endsWith('.js') ? /javascript/ : /css/);
    assetChecks.push({ path: asset, status: response.status, bytes: body.length, contentType: response.headers.get('content-type'), sha256: createHash('sha256').update(body).digest('hex') });
  }
  save(`${kind}-http-assets.json`, assetChecks);
  const identity = command('docker', ['exec', name, 'id'], `${kind}-identity.txt`);
  const uid = Number(command('docker', ['exec', name, 'id', '-u'], `${kind}-uid.txt`));
  const runtimeArch = command('docker', ['exec', name, 'node', '-p', 'process.arch'], `${kind}-runtime-architecture.txt`);
  command('docker', ['exec', name, 'cat', '/etc/os-release'], `${kind}-os-release.txt`);
  if (kind === 'baseline') {
    command('docker', ['exec', name, 'sh', '-c', 'command -v make && command -v g++ && test -d /app/client/node_modules/react-scripts && echo "frontend toolchain retained in baseline"'], `${kind}-build-tools.txt`);
  }
  if (kind === 'optimized') {
    assert.notEqual(uid, 0, 'optimized server must run without root');
    command('docker', ['exec', name, 'sh', '-c', 'test ! -d /app/client && test ! -d /app/node_modules/react-scripts && echo "frontend toolchain absent from runtime"'], `${kind}-runtime-contents.txt`);
    let healthy = false;
    for (let attempt = 0; attempt < 40; attempt += 1) {
      const raw = command('docker', ['inspect', name, '--format', '{{json .State.Health}}'], `${kind}-healthcheck.json.txt`);
      if (JSON.parse(raw).Status === 'healthy') { healthy = true; break; }
      await new Promise(resolve => setTimeout(resolve, 500));
    }
    assert.ok(healthy, 'Docker healthcheck did not become healthy');
  }
  command('docker', ['logs', name], `${kind}-logs.txt`);
  command('docker', ['stop', '--timeout', '15', name], `${kind}-stop.txt`);
  const state = JSON.parse(command('docker', ['inspect', name, '--format', '{{json .State}}'], `${kind}-stopped-state.json.txt`));
  assert.equal(state.ExitCode, 0, 'graceful shutdown should exit successfully');
  command('docker', ['logs', name], `${kind}-shutdown-logs.txt`);
  command('docker', ['rm', name], `${kind}-remove.txt`);
  containers.delete(name);
  return { tag: tags[kind], identity, uid, runtimeArch, originDuringVerification: origin, http: 'passed', staticAssets: assetChecks, gracefulShutdownExitCode: state.ExitCode };
}

try {
  const version = JSON.parse(command('docker', ['version', '--format', '{{json .}}'], 'docker-version.json.txt'));
  save('environment.json', { verifiedAtUTC: new Date().toISOString(), nodeForVerification: process.version, targetPlatform: platform, dockerClient: version.Client, dockerServer: version.Server });
  for (const [kind, dockerfile] of [['baseline', 'Dockerfile.baseline'], ['optimized', 'Dockerfile']]) {
    console.log(`Building ${kind}; full output is saved in evidence/${kind}-build.txt`);
    command('docker', ['build', '--platform', platform, '--progress=plain', '-f', dockerfile, '-t', tags[kind], '.'], `${kind}-build.txt`);
  }
  command('docker', ['run', '--rm', '--name', `devops-lab5-tests-${stamp}`, '--label', 'devops.lab=5', tags.baseline, 'npm', 'test'], 'server-tests.txt');
  const inspection = {};
  for (const kind of Object.keys(tags)) {
    inspection[kind] = JSON.parse(command('docker', ['image', 'inspect', tags[kind]], `${kind}-image-inspect.json.txt`))[0];
    command('docker', ['history', '--no-trunc', tags[kind]], `${kind}-history.txt`);
  }
  const sizes = {
    metric: 'docker image inspect .Size, bytes; decimal MB = bytes / 1000000',
    baselineBytes: inspection.baseline.Size,
    optimizedBytes: inspection.optimized.Size,
    baselineMB: inspection.baseline.Size / 1000000,
    optimizedMB: inspection.optimized.Size / 1000000,
    reductionFactor: inspection.baseline.Size / inspection.optimized.Size,
    baselineArchitecture: `${inspection.baseline.Os}/${inspection.baseline.Architecture}`,
    optimizedArchitecture: `${inspection.optimized.Os}/${inspection.optimized.Architecture}`,
    baselineImageId: inspection.baseline.Id,
    optimizedImageId: inspection.optimized.Id
  };
  save('sizes.json', sizes);
  assert.ok(sizes.optimizedBytes < 200000000, 'optimized image must be under 200 decimal MB');
  assert.ok(sizes.reductionFactor >= 5, 'image reduction must be at least 5x');
  assert.equal(sizes.baselineArchitecture, sizes.optimizedArchitecture);
  const checks = {};
  for (const kind of Object.keys(tags)) checks[kind] = await checkImage(kind);
  save('functional-checks.json', checks);
  command('docker', ['build', '--platform', platform, '--progress=plain', '-t', tags.optimized, '.'], 'optimized-cached-build.txt');
  const cacheLog = fs.readFileSync(path.join(evidence, 'optimized-cached-build.txt'), 'utf8');
  assert.match(cacheLog, /CACHED/, 'second build should reuse cached steps');
  const appFile = path.join(root, 'client/src/App.js');
  const originalApp = fs.readFileSync(appFile, 'utf8');
  try {
    fs.writeFileSync(appFile, originalApp + '\n// Source-only cache verification.\n');
    command('docker', ['build', '--platform', platform, '--progress=plain', '-t', 'devops-lab5-cache-check:local', '.'], 'optimized-source-change-build.txt');
    const sourceLog = fs.readFileSync(path.join(evidence, 'optimized-source-change-build.txt'), 'utf8');
    const installStep = sourceLog.match(/#(\d+) \[react-build [^\]]+\] RUN npm ci --no-audit --no-fund/);
    assert.ok(installStep, 'frontend npm ci step not found in cache evidence');
    assert.ok(sourceLog.includes(`#${installStep[1]} CACHED`), 'source-only edit must reuse frontend dependency installation');
    save('source-change-cache-check.json', { status: 'passed', frontendInstallStep: Number(installStep[1]), dependencyInstallReused: true, mutation: 'one JavaScript comment appended temporarily', originalSourceRestored: true });
  } finally {
    fs.writeFileSync(appFile, originalApp);
  }
  command('docker', ['image', 'rm', 'devops-lab5-cache-check:local'], 'cache-check-tag-remove.txt');
  save('result.json', { status: 'passed', completedAtUTC: new Date().toISOString(), sizes, checks, cachedBuild: 'CACHED steps present', sourceOnlyChange: 'frontend npm ci reused; source restored', containersLeftByVerification: [] });
  fs.rmSync(path.join(evidence, 'verification-error.txt'), { force: true });
  console.log(JSON.stringify({ status: 'passed', sizes }, null, 2));
} catch (error) {
  save('verification-error.txt', error.stack + '\n');
  console.error(error);
  process.exitCode = 1;
} finally {
  for (const name of containers) {
    command('docker', ['rm', '-f', name], `${name}-cleanup.txt`, { allowFailure: true });
  }
  save('commands.json', commands);
}
