'use strict';

const { test, after, before } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { createApp } = require('../app');

let server;
let origin;
let fixture;
before(async () => {
  fixture = fs.mkdtempSync(path.join(os.tmpdir(), 'devops-lab5-'));
  fs.writeFileSync(path.join(fixture, 'index.html'), '<!doctype html><title>Docker Blog</title><div id="root"></div>');
  fs.writeFileSync(path.join(fixture, 'main.js'), 'console.log("static asset");');
  server = createApp({ buildDirectory: fixture }).listen(0, '127.0.0.1');
  await new Promise(resolve => server.once('listening', resolve));
  origin = `http://127.0.0.1:${server.address().port}`;
});
after(async () => {
  await new Promise(resolve => server.close(resolve));
  fs.rmSync(fixture, { recursive: true, force: true });
});

test('health endpoint returns the required contract', async () => {
  const response = await fetch(`${origin}/api/health`);
  assert.equal(response.status, 200);
  assert.deepEqual(await response.json(), { status: 'ok', message: 'Server is running' });
});
test('posts endpoint supplies the React blog content', async () => {
  const response = await fetch(`${origin}/api/posts`);
  const data = await response.json();
  assert.equal(response.status, 200);
  assert.equal(data.length, 3);
  assert.equal(new Set(data.map(post => post.id)).size, data.length);
  for (const post of data) assert.ok(post.title && post.excerpt && post.content.length);
});
test('unknown API route returns JSON 404 instead of SPA HTML', async () => {
  const response = await fetch(`${origin}/api/missing`);
  assert.equal(response.status, 404);
  assert.match(response.headers.get('content-type'), /application\/json/);
});
test('SPA route receives the production entry point', async () => {
  const response = await fetch(`${origin}/posts/1`);
  assert.equal(response.status, 200);
  assert.match(await response.text(), /Docker Blog/);
});
test('static JavaScript is served as JavaScript', async () => {
  const response = await fetch(`${origin}/main.js`);
  assert.equal(response.status, 200);
  assert.match(response.headers.get('content-type'), /javascript/);
});
test('missing static asset returns 404 instead of HTML', async () => {
  const response = await fetch(`${origin}/missing.js`);
  assert.equal(response.status, 404);
});
