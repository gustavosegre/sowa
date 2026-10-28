FROM node:24-alpine
RUN corepack enable
WORKDIR /app
COPY package.json pnpm-lock.yaml* ./
RUN pnpm install --frozen-lockfile || pnpm install
COPY . .
EXPOSE 5173
CMD ["pnpm", "exec", "vite", "--host", "0.0.0.0", "--port", "5173"]
