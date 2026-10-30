import hardhatToolboxMochaEthersPlugin from "@nomicfoundation/hardhat-toolbox-mocha-ethers";
import { configVariable, defineConfig } from "hardhat/config";

export default defineConfig({
  plugins: [hardhatToolboxMochaEthersPlugin],
  solidity: {
    version: "0.8.28",
    settings: { optimizer: { enabled: true, runs: 200 } },
  },
  networks: {
    // The long-running local node from docker compose (`hardhat node`). Its
    // accounts are Hardhat's public test accounts: never use them elsewhere.
    chainNode: {
      type: "http",
      chainType: "l1",
      url: process.env.CHAIN_RPC_URL ?? "http://127.0.0.1:8545",
    },
    // Final run. Both values come from env vars or `npx hardhat keystore set ...`.
    sepolia: {
      type: "http",
      chainType: "l1",
      url: configVariable("SEPOLIA_RPC_URL"),
      accounts: [configVariable("SEPOLIA_PRIVATE_KEY")],
    },
  },
});
