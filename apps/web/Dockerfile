FROM node:22.19-alpine AS build
WORKDIR /workspace
RUN corepack enable && corepack prepare pnpm@10.13.1 --activate
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/web/package.json apps/web/package.json
COPY packages/types/package.json packages/types/package.json
RUN pnpm install --frozen-lockfile --filter @saferoute/web...
COPY apps/web apps/web
COPY packages/types packages/types
ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
RUN pnpm --filter @saferoute/web build

FROM caddy:2.10.2-alpine
USER caddy
COPY infrastructure/caddy/Caddyfile /etc/caddy/Caddyfile
COPY --from=build /workspace/apps/web/out /srv
