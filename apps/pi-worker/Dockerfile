FROM node:20-alpine

RUN apk add --no-cache bash git ripgrep openssh-client \
 && git config --global user.name "agentsofchaos" \
 && git config --global user.email "agentsofchaos@local.invalid"

WORKDIR /app
COPY apps/pi-worker/package.json ./package.json
RUN npm install
COPY apps/pi-worker/server.js ./server.js

WORKDIR /workspace
COPY . /workspace
RUN mkdir -p /state/pi-agent /state/meta

WORKDIR /app
ENV PORT=3000
ENV PI_WORKSPACE=/workspace
ENV PI_CODING_AGENT_DIR=/state/pi-agent
EXPOSE 3000
CMD ["npm", "start"]
