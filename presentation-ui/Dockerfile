FROM node:22-bookworm-slim

WORKDIR /app

COPY package.json package-lock.json /app/
RUN npm ci

COPY . /app

RUN npm run build

EXPOSE 5173

CMD ["npm", "run", "preview", "--", "--host", "0.0.0.0", "--port", "5173", "--strictPort"]
