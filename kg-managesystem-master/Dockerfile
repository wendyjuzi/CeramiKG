FROM node:20-alpine AS build
WORKDIR /app

# Install dependencies
COPY package*.json ./
RUN npm ci

# Build
COPY . .
RUN npm run build


FROM nginx:1.25-alpine AS runtime

# Nginx config for SPA + reverse proxy
COPY nginx/default.conf /etc/nginx/conf.d/default.conf

# Static assets
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

# Use default nginx entrypoint/cmd
