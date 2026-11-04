'use strict';

const { createApp } = require('./app');
const port = Number(process.env.PORT || 3000);
if (!Number.isInteger(port) || port < 1 || port > 65535) throw new Error('PORT must be an integer in 1..65535');
const server = createApp().listen(port, '0.0.0.0', () => console.log(`Docker Blog listening on 0.0.0.0:${port}`));

function shutdown(signal) {
  console.log(`Received ${signal}; closing HTTP server`);
  server.close(error => process.exit(error ? 1 : 0));
  setTimeout(() => process.exit(1), 10000).unref();
}
process.once('SIGTERM', () => shutdown('SIGTERM'));
process.once('SIGINT', () => shutdown('SIGINT'));
