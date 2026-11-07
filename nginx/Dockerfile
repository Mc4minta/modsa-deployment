# Stage 1: Build the static frontend SPA
FROM node:22.14.0-bookworm-slim AS builder

WORKDIR /build/frontend

# Build argument for backend API URL (defaults to /api for relative same-origin proxying)
ARG VITE_API_URL=/api
ENV VITE_API_URL=${VITE_API_URL}

# Copy package manifests first for efficient layer caching
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

# Copy frontend source code and compile production distribution
COPY frontend/ ./
RUN npm run build

# Stage 2: Minimal runtime image serving static assets and reverse proxying backend
FROM nginx:1.27.4-alpine AS runner

# Install curl for reliable container health checking
RUN apk add --no-cache curl

# Remove default nginx configurations and html files
RUN rm -rf /etc/nginx/conf.d/* /usr/share/nginx/html/*

# Copy custom Nginx configuration
COPY nginx/nginx.conf /etc/nginx/nginx.conf

# Copy compiled static assets from builder stage
COPY --from=builder /build/frontend/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=15s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:80/nginx-health || exit 1

CMD ["nginx", "-g", "daemon off;"]
