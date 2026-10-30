FROM node:22-slim
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
# Compile at build time so the node and deploy containers start fast.
RUN npx hardhat build
CMD ["npx", "hardhat", "node", "--hostname", "0.0.0.0"]
