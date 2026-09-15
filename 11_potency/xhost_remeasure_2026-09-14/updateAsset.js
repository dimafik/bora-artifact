'use strict';

//
// Bounded-state workload.
//
// WHY THIS EXISTS.  createAsset.js mints a fresh key on every transaction
// (`bench_w0_r0_1_1789...`), so the world state grows without limit. Over one
// day of measurement on the cross-host rig that pushed the peer host's disk to
// 79% and took the clean baseline from 290 tx/s down to 145 -- a 50% drift that
// has nothing to do with what is being measured. A campaign that runs for hours
// cannot use a workload whose cost rises with the number of transactions it has
// already sent.
//
// WHAT THIS DOES INSTEAD.  Each worker owns a private pool of POOL keys, created
// once during initialisation, and the round cycles UpdateAsset over that pool.
// The world state is therefore constant at (workers x POOL) entries for the
// whole campaign; only the block store grows, and the block store is append-only
// and cheap to write.
//
// POOL SIZE AND MVCC.  Two updates to the same key inside one block collide and
// Fabric rejects the second with MVCC_READ_CONFLICT, which would show up as a
// failure rate that depends on load rather than on the system under test. The
// pool is per-worker so workers never collide with each other, and it is sized
// so a key is revisited far less often than a block is cut:
//   300 tx/s over 8 workers = 37.5 tx/s per worker
//   POOL 500  ->  a key is touched every ~13 s, against a ~2 s block time.
//
// Usage in a benchmark round:
//   workload:
//     module: workload/updateAsset.js
//     arguments: {poolSize: 500}
//

const { WorkloadModuleBase } = require('@hyperledger/caliper-core');

class UpdateAssetWorkload extends WorkloadModuleBase {
    constructor() {
        super();
        this.txIndex = 0;
        this.poolSize = 500;
    }

    async initializeWorkloadModule(workerIndex, totalWorkers, roundIndex, roundArguments, sutAdapter, sutContext) {
        await super.initializeWorkloadModule(workerIndex, totalWorkers, roundIndex, roundArguments, sutAdapter, sutContext);
        this.txIndex = 0;
        this.workerId = workerIndex;
        if (roundArguments && roundArguments.poolSize) {
            this.poolSize = parseInt(roundArguments.poolSize, 10);
        }

        // Create this worker's pool. Sent in batches: one awaited request at a
        // time would spend minutes here before the round even starts.
        const BATCH = 50;
        let batch = [];
        for (let i = 0; i < this.poolSize; i++) {
            batch.push({
                contractId: 'basic',
                contractFunction: 'CreateAsset',
                invokerIdentity: 'User1',
                contractArguments: [this._key(i), 'blue', '5', 'tom', '100'],
                readOnly: false
            });
            if (batch.length === BATCH || i === this.poolSize - 1) {
                // A key left over from an earlier round already exists; that is
                // fine and must not abort the preparation.
                try { await this.sutAdapter.sendRequests(batch); } catch (err) { /* already present */ }
                batch = [];
            }
        }
    }

    _key(i) {
        return `pool_w${this.workerId}_${i}`;
    }

    async submitTransaction() {
        const key = this._key(this.txIndex % this.poolSize);
        this.txIndex++;
        const request = {
            contractId: 'basic',
            contractFunction: 'UpdateAsset',
            invokerIdentity: 'User1',
            contractArguments: [key, 'red', '10', 'alice', String(100 + (this.txIndex % 50))],
            readOnly: false
        };
        await this.sutAdapter.sendRequests(request);
    }
}

function createWorkloadModule() {
    return new UpdateAssetWorkload();
}

module.exports.createWorkloadModule = createWorkloadModule;
