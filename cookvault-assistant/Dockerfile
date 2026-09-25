FROM oven/bun:1-slim
WORKDIR /app

COPY package.json bun.lock bunfig.toml ./
RUN bun install --frozen-lockfile --production

COPY src ./src
COPY prompts ./prompts

ENV NODE_ENV=production
ENV PORT=8500
# The audit log and nothing else. Mounted as a volume by compose.
RUN mkdir -p /app/data
EXPOSE 8500
CMD ["bun", "run", "src/index.ts"]
