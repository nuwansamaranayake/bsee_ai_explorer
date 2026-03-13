# Stage 1: Build
FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
COPY .npmrc ./
RUN npm ci
COPY . .
# In Docker, nginx proxies /api → backend, so VITE_API_URL must be empty
ENV VITE_API_URL=""
RUN npm run build

# Stage 2: Serve
FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
