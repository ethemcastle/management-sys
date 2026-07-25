# Dev-oriented image: runs `ng serve` with polling for container file-watching.
FROM node:22-alpine

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .

EXPOSE 4200

# Overridden by docker-compose to bind 0.0.0.0; sensible default here too.
CMD ["npm", "start", "--", "--host", "0.0.0.0", "--poll", "2000"]
