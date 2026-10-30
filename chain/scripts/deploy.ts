// Deploys TrustTrailAnchor and writes deployments/<network>.json, which the
// TrustTrail service reads to find the contract (address, chain id, ABI).
//   npx hardhat run scripts/deploy.ts --network chainNode   (docker compose does this)
//   npx hardhat run scripts/deploy.ts --network sepolia
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { network } from "hardhat";

const connection = await network.create();
const { ethers } = connection;
const name = connection.networkName === "chainNode" ? "localhost" : connection.networkName;
const file = `deployments/${name}.json`;

// Reuse the existing contract if it is still on this chain: redeploying would
// orphan every earlier anchor. A fresh local chain has no code there, so it
// gets a new contract. Set FORCE_DEPLOY=1 to deploy anyway.
if (existsSync(file) && !process.env.FORCE_DEPLOY) {
  const previous = JSON.parse(readFileSync(file, "utf8"));
  const { chainId: current } = await ethers.provider.getNetwork();
  if (Number(current) === previous.chainId && (await ethers.provider.getCode(previous.address)) !== "0x") {
    console.log(`TrustTrailAnchor already deployed on ${name} at ${previous.address}; reusing it`);
    process.exit(0);
  }
}

const [deployer] = await ethers.getSigners();
const anchor = await ethers.deployContract("TrustTrailAnchor");
const receipt = await anchor.deploymentTransaction()!.wait();
const { chainId } = await ethers.provider.getNetwork();

const out = {
  network: name,
  chainId: Number(chainId),
  address: await anchor.getAddress(),
  owner: deployer.address,
  deployBlock: receipt!.blockNumber,
  deployTx: receipt!.hash,
  deployGas: Number(receipt!.gasUsed),
  deployedAt: new Date().toISOString(),
  abi: JSON.parse(anchor.interface.formatJson()),
};
mkdirSync("deployments", { recursive: true });
writeFileSync(file, JSON.stringify(out, null, 2));
console.log(`TrustTrailAnchor deployed on ${name} (chain ${out.chainId}) at ${out.address}, gas ${out.deployGas}`);
