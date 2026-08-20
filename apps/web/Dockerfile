FROM node:22.19-alpine AS build
WORKDIR /workspace
RUN corepack enable && corepack prepare pnpm@10.13.1 --activate
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/web/package.json apps/web/package.json
COPY packages/types/package.json packages/types/package.json
RUN pnpm install --frozen-lockfile --filter @roadsignal/web...
COPY apps/web apps/web
COPY packages/types packages/types
ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
RUN pnpm --filter @roadsignal/web build

FROM caddy:2.10.2-alpine
RUN addgroup -S -g 10001 roadsignal \
    && adduser -S -D -H -u 10001 -G roadsignal roadsignal \
    && chown -R roadsignal:roadsignal /data /config
COPY infrastructure/caddy/Caddyfile /etc/caddy/Caddyfile
COPY --chown=roadsignal:roadsignal --from=build /workspace/apps/web/out /srv
USER 10001:10001