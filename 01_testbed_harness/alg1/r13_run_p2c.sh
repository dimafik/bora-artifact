#!/usr/bin/env bash
# Phase 2-prime extension: arms A and C only, seeds 4-8, to bring the
# re-acquisition count from 15 to 40 elections per arm.  Arm D is dropped --
# it differs from C only in the Active-Leader Rule, which governs mid-term
# protection, not post-term re-acquisition, and it measured identically to C.
exec bash /mnt/d/fabric-d2/alg1/r13_p2c.sh 7 8 5
