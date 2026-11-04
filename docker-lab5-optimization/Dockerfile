# syntax=docker/dockerfile:1
FROM node:24 AS react-build
WORKDIR /app/client
COPY client/package.json client/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY client/public ./public
COPY client/src ./src
RUN npm run build

FROM node:24-alpine AS production-deps
WORKDIR /app
COPY server/package.json server/package-lock.json ./
RUN npm ci --omit=dev --no-audit --no-fund \
    && apk add --no-cache binutils \
    && ls -l /usr/local/bin/node \
    && strip --strip-unneeded /usr/local/bin/node \
    && ls -l /usr/local/bin/node \
    && node --version

# node:24-alpine itself exceeded 200 decimal MB in the measured image store.
# Keep its official musl Node binary, but leave npm, Yarn and headers behind.
# Alpine 3.24 matches the distribution measured in this Node Alpine source.
FROM alpine:3.24 AS runtime
ENV NODE_ENV=production PORT=3000
RUN apk add --no-cache libstdc++ ca-certificates \
    && addgroup -g 1000 node \
    && adduser -D -u 1000 -G node node
WORKDIR /app
COPY --from=production-deps /usr/local/bin/node /usr/local/bin/node
COPY --from=production-deps /app/node_modules ./node_modules
COPY --chown=node:node server/server.js server/app.js server/posts.json ./
COPY --from=react-build --chown=node:node /app/client/build ./build
USER node
EXPOSE 3000
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
  CMD node -e "fetch('http://127.0.0.1:'+process.env.PORT+'/api/health',{signal:AbortSignal.timeout(2000)}).then(r=>{if(!r.ok)process.exit(1);return r.json()}).then(d=>{if(d.status!=='ok')process.exit(1)}).catch(()=>process.exit(1))"
CMD ["node", "server.js"]
