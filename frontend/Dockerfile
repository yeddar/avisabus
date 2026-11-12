# AvisaBus web image (deployment_rpi design §2): the frontend build served by nginx, which also
# proxies /api/ and /ws/ to the backend. Build context: the repository root (deploy/compose.yaml).

# --- build: the PWA (dist/) -------------------------------------------------------------------------
FROM node:22-alpine AS build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# --- runtime -----------------------------------------------------------------------------------------
FROM nginx:1.27-alpine
COPY deploy/nginx/web.conf /etc/nginx/conf.d/default.conf
COPY deploy/nginx/security-headers.conf /etc/nginx/snippets/security-headers.conf
COPY --from=build /app/frontend/dist /usr/share/nginx/html
