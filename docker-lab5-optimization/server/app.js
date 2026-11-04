'use strict';

const express = require('express');
const path = require('node:path');
const posts = require('./posts.json');

function createApp({ buildDirectory = path.join(__dirname, 'build') } = {}) {
  const app = express();
  app.disable('x-powered-by');
  app.get('/api/health', (_req, res) => res.json({ status: 'ok', message: 'Server is running' }));
  app.get('/api/posts', (_req, res) => res.json(posts));
  app.use('/api', (_req, res) => res.status(404).json({ error: 'API route not found' }));
  app.use(express.static(buildDirectory, { index: false }));
  app.get('*', (req, res, next) => {
    if (path.extname(req.path)) return res.status(404).type('text').send('Asset not found');
    res.sendFile(path.join(buildDirectory, 'index.html'), error => {
      if (error) next(error);
    });
  });
  app.use((error, _req, res, _next) => {
    console.error(error.message);
    if (!res.headersSent) res.status(500).json({ error: 'Application error' });
  });
  return app;
}

module.exports = { createApp };
