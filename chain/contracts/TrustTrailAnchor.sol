// SPDX-License-Identifier: MIT
pragma solidity ^0.8.28;

/// @title TrustTrail ledger anchor
/// @notice Stores the Merkle root of each batch of TrustTrail ledger entries.
/// Only hashes go on-chain: records stay off-chain, fingerprints are anchored here.
/// An anchor proves a batch is unchanged since it was anchored, not that its
/// contents were true when written.
contract TrustTrailAnchor {
    struct Batch {
        bytes32 root;         // Merkle root over the batch's entry hashes
        uint64 firstEntryId;  // ledger entry ids covered, inclusive
        uint64 lastEntryId;
        uint64 anchoredAt;    // block timestamp
    }

    address public immutable owner;
    Batch[] private batches;

    event Anchored(uint256 indexed batchId, bytes32 root, uint64 firstEntryId, uint64 lastEntryId, uint64 anchoredAt);

    error NotOwner();
    error EmptyRange();
    // Batches must cover the ledger from entry 1 with no gaps or overlaps, so a
    // verifier can tell which entries are anchored and spot a truncated ledger.
    error NotContiguous(uint64 expectedFirstEntryId);

    constructor() {
        owner = msg.sender;
    }

    function anchor(bytes32 root, uint64 firstEntryId, uint64 lastEntryId) external returns (uint256 batchId) {
        if (msg.sender != owner) revert NotOwner();
        if (lastEntryId < firstEntryId) revert EmptyRange();
        uint64 expected = batches.length == 0 ? 1 : batches[batches.length - 1].lastEntryId + 1;
        if (firstEntryId != expected) revert NotContiguous(expected);

        batchId = batches.length;
        uint64 at = uint64(block.timestamp);
        batches.push(Batch(root, firstEntryId, lastEntryId, at));
        emit Anchored(batchId, root, firstEntryId, lastEntryId, at);
    }

    function batchCount() external view returns (uint256) {
        return batches.length;
    }

    function getBatch(uint256 batchId) external view returns (Batch memory) {
        return batches[batchId];
    }

    /// @notice Highest ledger entry id anchored so far (0 if none).
    function lastAnchoredEntryId() external view returns (uint64) {
        return batches.length == 0 ? 0 : batches[batches.length - 1].lastEntryId;
    }
}
