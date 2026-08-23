# 5-Hour AWS Live Experiment — Final Build Status

**Build date**: 2026-06-01
**Pre-register hash**: `6102513b8a1407865e9b2b2c700c143b06b7a6b3e978f152b81a5d53e88d36e7`
**Files under hash**: 28
**Estimated cost (5h run, no rebuild)**: $23.65
**Estimated cost (5h run + AMI rebuild)**: $25.19
**Budget headroom vs $35 soft cap**: $9.81

## Component Status

| Component | Files | Status |
|---|---|---|
| Terraform IaC | `terraform/main.tf`, `outputs.tf`, `userdata.sh`, `inventory.tmpl` | ✓ Ready |
| Ansible playbooks | `ansible/playbooks/0{1,2,3}_*.yml` | ✓ Ready |
| Packer AMI build | `packer/fabric-ami.pkr.hcl` + 6 install scripts | ✓ Ready (build pending) |
| Analysis pipeline | `analysis/aws_5h_analysis.py` (525 LOC) | ✓ Validated via dry-run |
| Caliper workloads | `caliper/benchmark-arm-{a,b,burst}.yaml`, `workloads/transfer.js` | ✓ Ready |
| Orchestration | `scripts/run_orchestrator.sh`, `cost_simulate.py`, `dry_run_simulate.py` | ✓ Ready, dry-run passed |
| Pre-registration | `preregister.hash`, `preregister.proof.txt`, `timestamping/` | ✓ Hash locked, OTS commit pending user auth |
| Documentation | `README.md`, `TIMESTAMP_INSTRUCTIONS.md`, packer/README, timestamping/README | ✓ Complete |

## Dry-Run Results (1.44M synthetic tx)

Per-arm summary table:

| Arm | n HC | HC miss | Rate | 99% Wilson CI | P99 (ms) |
|---|---:|---:|---:|---|---:|
| A: Raft | 52,386 | 2,024 | 3.86% | [3.65, 4.09]% | 143.4 |
| B: Proposed | 52,985 | 430 | 0.81% | [0.72, 0.92]% | 102.6 |
| C: Ablation | 52,519 | 1,233 | 2.35% | [2.18, 2.52]% | 117.4 |

Pre-registered statistical comparisons:

| Test | Risk Diff | Risk Ratio | Fisher p | Holm p | Reject H₀? |
|---|---:|---:|---:|---:|:---:|
| primary (normal) | +3.05 pp | 0.210 | 6.24e-256 | 1.25e-255 | YES |
| secondary (burst) | +4.85 pp | 0.213 | 1.50e-204 | 1.50e-204 | YES |

## Cost Simulation Matrix

| Scenario | Compute | EBS | Network | S3 | Other | **TOTAL** | Cap status |
|---|---:|---:|---:|---:|---:|---:|---|
| 5h, no AMI rebuild | $22.02 | $0.60 | $0.89 | $0.13 | $0.01 | **$23.65** | $11.35 headroom |
| 5h, with AMI rebuild | $22.02 | $0.60 | $0.89 | $0.13 | $1.55 | **$25.19** | $9.81 headroom |
| 5.5h (30min overrun) | $24.22 | $0.66 | $0.89 | $0.13 | $0.02 | **$25.92** | $9.08 headroom |
| 6h (60min overrun) | $26.42 | $0.72 | $0.89 | $0.13 | $0.02 | **$28.18** | $6.82 headroom |

All scenarios within $35 soft cap. Hard cap ($60) not threatened.

## User Action Items (in order)

1. **Pre-bake the AMI** (one-time, ~25 min, ~$0.05):
   ```bash
   cd runbook/packer
   packer init . && packer build fabric-ami.pkr.hcl
   # Capture AMI id, write to ../terraform/secrets.tfvars
   ```

2. **Commit pre-register hash to OTS** (user authorization required):
   ```bash
   cd runbook/
   ots stamp preregister.hash
   ```

3. **Launch the 5-hour run** (at chosen T+0:00):
   ```bash
   bash runbook/scripts/run_orchestrator.sh <run_id>
   ```

4. **Upgrade OTS proof** (~3h after stamping):
   ```bash
   ots upgrade runbook/preregister.hash.ots
   ```

5. **Publish S3 bucket** (within 7 days of run, per design doc commitment):
   - Set bucket policy to public-read
   - Tag release with arXiv preprint URL

## Honest Limitations (carry into manuscript)

1. Single region (us-east-1); multi-region not tested.
2. SmartBFT and Arma not measured live; comparison via published-paper
   figures and an internal ablation arm only.
3. Predictor frozen at simulator-trained weights; online learning untested.
4. Cross-AZ latency estimates assume <2ms RTT; real numbers may vary
   ±20-30% during peak AWS hours.
5. Dry-run validated the analysis pipeline; real-data validation pending
   actual run.

## Sign-off

All 7 panel experts (Anya, Bjorn, Chen, Dara, Erik, Fatima, Greta) signed
off on the locked design. The runbook is reproducible by any third party
with AWS credentials and the manifest hash. No further design changes
permitted without invalidating the pre-registration.
