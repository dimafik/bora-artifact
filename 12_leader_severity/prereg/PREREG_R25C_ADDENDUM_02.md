# Addendum 02 to PREREG_R25C — nine invalid attempts, and the cause

Nine attempts produced no measurement. **No wrong number was produced**: the
harness's ledger-delta check refused every one of them, which is what it is for.
Under §6 of the pre-registration these are counted and named here rather than
dropped.

**Nothing about the registered measurement changed.** Delay, arms, endpoints,
analysis, sample-size stages and the falsification condition are untouched.

## 1. The nine attempts

| attempt | output | outcome |
|---|---|---|
| 1 (solo) | `r25c_20260824-173515` | invalid — `C_clean: ledger delta=0` |
| 2–10 (campaign) | `r25c_20260824-174242` … `r25c_20260824-182031` | invalid, identical failure |

All nine died in the first arm, about four minutes in, with

    C_clean: ledger delta=0 -- NOTHING COMMITTED, measurement invalid

and, in every Caliper log, 45,020 instances of

    EndorseError: 9 FAILED_PRECONDITION: no combination of peers can be
    derived which satisfy the endorsement policy

## 2. What it was not

Addendum 01 attributed the first failure to a cold chaincode container on
`peer0.org1` and added a warm-up query. That diagnosis was **incomplete**. The
warm-up did its job — both peers answered `GetAllAssets` before every attempt,
and both chaincode containers were up — and the runs still failed. Warming the
containers was necessary but not sufficient.

## 3. What it was

Service discovery. The decisive test was to bypass it: an invoke naming both
peers explicitly, with their TLS roots, committed immediately.

    peer chaincode invoke ... \
      --peerAddresses peer0.org1.example.com:7051 --tlsRootCertFiles ... \
      --peerAddresses peer0.org2.example.com:9051 --tlsRootCertFiles ...
    -> Chaincode invoke successful. result: status:200
    -> channel height 3647 -> 3648

So the chaincode, the endorsement policy, the orderers and the commit path were
all healthy. What could not happen was the *search* for an endorsing
combination, and Caliper's network configuration (`networks/fabric-5node.yaml`)
sets `discover: true` for both organisations.

The channel had **no anchor peers**. This cluster was brought up by the election
harness `nsweep_bringup.sh`, which by its own comment "joins the ORDERERS to the
channel and stops there, because leadership measurements never needed a peer";
the peers were joined afterwards by hand, and the anchor-peer step of channel
setup never ran. Without anchor peers each organisation's peer cannot learn of
the other's, so a policy requiring both can never be satisfied through
discovery.

## 4. The fix, and why it is a restoration rather than a change

`test-network/scripts/setAnchorPeer.sh` was run for both organisations:

- `Org1MSP` -> `peer0.org1.example.com:7051`
- `Org2MSP` -> `peer0.org2.example.com:9051`
- channel height 3648 -> 3650 (two configuration blocks)

Verified with the `discover` CLI afterwards: endorser discovery now returns a
layout `{G0: 1, G1: 1}`, one endorser from each organisation, which is exactly
the combination the policy needs.

**This restores parity with the environment the manuscript's existing number
came from.** The `r25b` cluster that produced 467.8 -> 127.5 tx/s was built by
`network.sh`, which sets anchor peers as part of channel creation. Anchor peers
affect gossip and discovery only; they are not part of consensus or of the
throughput path, so no measured quantity is defined differently before and after.

## 5. One incidental commit

The diagnostic invoke of §3 created a single asset, `diag_probe_1`, at channel
height 3648. The workload creates assets under randomised keys, so it collides
with nothing; it is recorded here for completeness.

## 6. Effect on the registered plan

None. Stages remain pilot 6 -> 12 -> conditional 18, counted in **valid** runs.
Ten invalid attempts now stand against that count and will appear in the final
table with the reasons given above.
