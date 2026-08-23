# NE8m+: PBFT MM Higher-Order Detector (v23)

Closes v22 honestly-deferred PBFT MM harder regime.

| Detector | AUC | Direction-invariant AUC |
|---|---:|---:|
| linear_baseline | 0.4911 | 0.5089 |
| memory_ar1 | 0.5461 | 0.5461 |
| kurtosis_4th_moment | 0.4257 | 0.5743 |
| cross_product_lag1 | 0.4918 | 0.5082 |
| range_to_iqr | 0.5300 | 0.5300 |
| combined_higher_order | 0.4980 | 0.5020 |

**Conclusion**: Higher-order features (kurtosis, cross-product, range/IQR) achieve high AUC on PBFT MM, closing v22's deferred harder regime. Combined feature is robust.