FROM node:22-alpine AS dependencies
ENV NEXT_TELEMETRY_DISABLED=1

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM node:22-alpine AS builder

WORKDIR /app
COPY --from=dependencies /app/node_modules ./node_modules
COPY . .
ARG GIT_SHA
ARG BUILD_TIMESTAMP
ARG APP_VERSION=0.2.0
ARG API_INTERNAL_URL=http://api:8000
ENV API_INTERNAL_URL=$API_INTERNAL_URL NEXT_TELEMETRY_DISABLED=1
RUN test "${#GIT_SHA}" -eq 40 && test -n "$BUILD_TIMESTAMP"
ENV COMPOUNDOS_GIT_SHA=$GIT_SHA COMPOUNDOS_BUILD_TIMESTAMP=$BUILD_TIMESTAMP COMPOUNDOS_APP_VERSION=$APP_VERSION
RUN npm run build
RUN npm prune --omit=dev --ignore-scripts


FROM node:22-alpine AS runner

ARG GIT_SHA
ARG BUILD_TIMESTAMP
ARG APP_VERSION=0.2.0
LABEL org.opencontainers.image.revision=$GIT_SHA org.opencontainers.image.created=$BUILD_TIMESTAMP org.opencontainers.image.version=$APP_VERSION
ENV NEXT_TELEMETRY_DISABLED=1 NODE_ENV=production COMPOUNDOS_GIT_SHA=$GIT_SHA COMPOUNDOS_BUILD_TIMESTAMP=$BUILD_TIMESTAMP COMPOUNDOS_APP_VERSION=$APP_VERSION
WORKDIR /app
COPY --from=builder /app/package.json ./package.json
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/.next ./.next

EXPOSE 3000

CMD ["npm", "run", "start", "--", "-H", "0.0.0.0"]
