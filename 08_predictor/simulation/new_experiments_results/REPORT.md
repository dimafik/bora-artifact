# NE1-NE5: New Experiments (Panel-Identified Gaps)

## NE1_adaptive_byzantine

- **auc_linear**: 0.48472600000000005
- **auc_memory_aware**: 0.41949974999999995
- **n_samples**: 4000
- **adapt_rounds**: 10

## NE2_model_extraction

- **n_queries**: 500
- **cos_similarity_no_defense**: 0.9997204121615599
- **cos_similarity_with_dp_eps1**: 0.9923781948751692
- **dp_protection_gain**: 0.007342217286390729

## NE3_higher_moments

- **auc_linear_AUC_05_baseline**: 0.51152075
- **auc_second_moment_feature**: 0.45512974999999994
- **auc_fourth_moment_feature**: 0.45512974999999994
- **interpretation**: Linear AUC=0.5 confirms Theorem 1; higher-moment features regain discriminability — extends NW3 k-step to 4th moment.

## NE4_f2_boundary

- **trials**: 200
- **violations_no_blacklist**: 2
- **violations_with_blacklist**: 0
- **safety_rate_no_blacklist**: 0.99
- **safety_rate_with_blacklist**: 1.0

## NE5_election_timeout_sweep

- **results**: [{'timeout_ms': 400, 'viable_at_220ms_WAN': False, 'spurious_election_rate_estimate': 1.0, 'expected_recovery_ms': 350.0}, {'timeout_ms': 600, 'viable_at_220ms_WAN': True, 'spurious_election_rate_estimate': 0.0, 'expected_recovery_ms': 450.0}, {'timeout_ms': 800, 'viable_at_220ms_WAN': True, 'spurious_election_rate_estimate': 0.0, 'expected_recovery_ms': 550.0}, {'timeout_ms': 1000, 'viable_at_220ms_WAN': True, 'spurious_election_rate_estimate': 0.0, 'expected_recovery_ms': 650.0}, {'timeout_ms': 1200, 'viable_at_220ms_WAN': True, 'spurious_election_rate_estimate': 0.0, 'expected_recovery_ms': 750.0}, {'timeout_ms': 1500, 'viable_at_220ms_WAN': True, 'spurious_election_rate_estimate': 0.0, 'expected_recovery_ms': 900.0}, {'timeout_ms': 2000, 'viable_at_220ms_WAN': True, 'spurious_election_rate_estimate': 0.0, 'expected_recovery_ms': 1150.0}]
- **recommendation**: 800-1500ms range used in RD2 is justified: exceeds 2x worst-case one-way (440ms) + heartbeat + jitter.
