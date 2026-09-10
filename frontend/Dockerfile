FROM node:20-slim AS builder
WORKDIR /app

ARG NEXT_PUBLIC_API_URL=http://localhost:8420
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

COPY package.json package-lock.json* ./
RUN npm install

COPY . .
RUN npm run build

FROM node:20-slim
WORKDIR /app
ENV NODE_ENV=production
ENV PORT=3420

COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static

EXPOSE 3420
CMD ["node", "server.js"]
