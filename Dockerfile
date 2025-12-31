# Stage 1: Build the React/Vite application
FROM node:20-alpine AS builder

WORKDIR /app

# Accept build argument for API URL (defaults to localhost for development)
ARG VITE_API_URL=https://eoas-529682581088.europe-west1.run.app
ENV VITE_API_URL=$VITE_API_URL

# Copy package files
COPY package.json package-lock.json ./

# Install dependencies
RUN npm ci

# Copy source files
COPY . .

# Build the application
RUN npm run build

# Stage 2: Serve the built application with nginx
FROM nginx:alpine

# Set default PORT (Cloud Run will override this with env var)
ENV PORT=8080

# Copy nginx config template (nginx automatically processes templates in /etc/nginx/templates/)
COPY nginx.conf.template /etc/nginx/templates/default.conf.template

# Copy built files from builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

# Expose port (Cloud Run will set PORT env var)
EXPOSE 8080

