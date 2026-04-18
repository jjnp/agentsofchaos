FROM node:20-alpine

RUN apk add --no-cache bash git ripgrep openssh-client \
 && git config --global user.name "agentsofchaos" \
 && git config --global user.email "agentsofchaos@local.invalid"

WORKDIR /app
COPY apps/pi-worker/package.json ./package.json
RUN npm install
COPY apps/pi-worker/server.js ./server.js

WORKDIR /workspace
RUN mkdir -p /workspace /state/pi-agent /state/meta \
 && git init -b main /workspace \
 && printf '# Agent workspace\n\nThis is a clean worker sandbox.\n' > /workspace/README.md \
 && git -C /workspace add README.md \
 && git -C /workspace commit -m "Initial workspace" >/dev/null

WORKDIR /app
ENV PORT=3000
ENV PI_WORKSPACE=/workspace
ENV PI_CODING_AGENT_DIR=/state/pi-agent
EXPOSE 3000
CMD ["npm", "start"]
