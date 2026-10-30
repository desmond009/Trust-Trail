import { expect } from "chai";
import { network } from "hardhat";

const { ethers } = await network.create();
const ROOT_A = ethers.id("batch A");
const ROOT_B = ethers.id("batch B");

async function deploy() {
  const [owner, stranger] = await ethers.getSigners();
  const anchor = await ethers.deployContract("TrustTrailAnchor");
  return { anchor, owner, stranger };
}

describe("TrustTrailAnchor", function () {
  it("stores a batch and emits Anchored", async function () {
    const { anchor } = await deploy();
    await expect(anchor.anchor(ROOT_A, 1n, 10n)).to.emit(anchor, "Anchored");
    const batch = await anchor.getBatch(0n);
    expect(batch.root).to.equal(ROOT_A);
    expect(batch.firstEntryId).to.equal(1n);
    expect(batch.lastEntryId).to.equal(10n);
    expect(batch.anchoredAt).to.be.greaterThan(0n);
    expect(await anchor.batchCount()).to.equal(1n);
    expect(await anchor.lastAnchoredEntryId()).to.equal(10n);
  });

  it("requires batches to be contiguous from entry 1", async function () {
    const { anchor } = await deploy();
    await expect(anchor.anchor(ROOT_A, 2n, 5n))
      .to.be.revertedWithCustomError(anchor, "NotContiguous").withArgs(1n);
    await anchor.anchor(ROOT_A, 1n, 5n);
    await expect(anchor.anchor(ROOT_B, 5n, 9n))      // overlap
      .to.be.revertedWithCustomError(anchor, "NotContiguous").withArgs(6n);
    await expect(anchor.anchor(ROOT_B, 7n, 9n))      // gap
      .to.be.revertedWithCustomError(anchor, "NotContiguous").withArgs(6n);
    await anchor.anchor(ROOT_B, 6n, 9n);
    expect(await anchor.batchCount()).to.equal(2n);
  });

  it("rejects an empty range", async function () {
    const { anchor } = await deploy();
    await expect(anchor.anchor(ROOT_A, 3n, 2n)).to.be.revertedWithCustomError(anchor, "EmptyRange");
  });

  it("only the owner (TrustTrail's anchoring key) can anchor", async function () {
    const { anchor, stranger } = await deploy();
    await expect(anchor.connect(stranger).anchor(ROOT_A, 1n, 1n))
      .to.be.revertedWithCustomError(anchor, "NotOwner");
  });

  it("anchored batches cannot be changed: there is no function to do it", async function () {
    const { anchor } = await deploy();
    const writers = anchor.interface.fragments
      .filter((f) => f.type === "function" && !(f as any).constant && (f as any).stateMutability !== "view")
      .map((f) => (f as any).name);
    expect(writers).to.deep.equal(["anchor"]);
  });

  it("gas per anchor does not grow with batch size (only the root is stored)", async function () {
    const { anchor } = await deploy();
    const small = await (await anchor.anchor(ROOT_A, 1n, 1n)).wait();
    const large = await (await anchor.anchor(ROOT_B, 2n, 100001n)).wait();
    console.log(`      gas: first anchor ${small!.gasUsed}, later anchor of 100000 entries ${large!.gasUsed}`);
    expect(large!.gasUsed).to.be.lessThan(small!.gasUsed);   // first write also pays for the array slot
  });
});
