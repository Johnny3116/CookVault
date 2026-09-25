FROM oven/bun:1 AS builder
WORKDIR /app

COPY package.json bun.lock bunfig.toml ./
# The 24h release-age guard in bunfig.toml only affects resolution; with a
# lockfile every version is already pinned, so --frozen-lockfile is the check
# that matters here: the lock and package.json must agree.
RUN bun install --frozen-lockfile

COPY . .
RUN bun run build

FROM oven/bun:1-slim
WORKDIR /app
ENV NODE_ENV=production
ENV PORT=3420

COPY --from=builder /app/.output ./.output

EXPOSE 3420
CMD ["bun", "run", ".output/server/index.mjs"]
