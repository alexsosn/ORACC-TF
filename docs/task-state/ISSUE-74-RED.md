# ISSUE-74 RED expectation

At commit `a3fc0ad6e94f5a0b7b9617456c167c0a35cf87a3`, the focused contract imports `oracc_tf.app_provenance`, which does not exist on the implementation branch yet. The intended RED is therefore a focused import/module failure while all pre-existing tests remain unaffected.

Production code must not be added until CI records that RED state.
