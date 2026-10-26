# 106: Which counties are unusual compared with peers in the same state?

- Issue: [ML #106](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/106), part of [ML #22](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/22). Spec: [106-state-relative-anomaly/v1.1](106-analysis-spec.md).
- Data: `ONE_HEALTH_LYME_GAP_ATLAS_PROD.PRESENTATION.CURRENT_COUNTY_ATLAS_V`, `CURRENT_RELEASE_V`, and `CURRENT_SOURCE_METADATA_V`. Pinned release `governed-2026-10-15-january-climate-prod`.
- Cohort: one county row on that release. Rows read 3144. Complete feature rows 3144. Exclusions 0.

## Method and assumptions

Spec [106-state-relative-anomaly/v1.1](106-analysis-spec.md), frozen before the fit. Continuous features are log population, SVI percentile, uninsured percentile, and rural-urban code. Percentile columns divided by 100: none. A state with at least 40 counties uses its own median and MAD. A state with 15 to 39 counties keeps the state median and shrinks the scale toward the leave-state-out Census region. A state with fewer than 15 counties uses a Census-region by tick-status class when that cell has at least 40 counties, and otherwise the Census region. The robust-z flag is a largest absolute z above 3.5. Percentile tails and robust-covariance distance are fit only for peer groups of at least 40 counties. Surveillance status uses a minority rule, not MAD, because a 0/1 status has no robust scale unless the split is exactly even. Isolation forest and local outlier factor run only in states with at least 80 counties. Seeds 1062026 and 1062027. scikit-learn 1.9.1. Temporal detection was not fit: the pinned release is one row per county.

## Material findings and limits

Epic #22 section 4.1 recorded 3,144 counties, 651 with a published 2023 human floor, and 2,493 with no county-linked human record. This release matches those three counts and the 228-county established-tick / pathogen-present / no-human-floor gap. Section 4.1 did not record a state-relative anomaly count. The October 13 release id was `governed-2026-10-06-nlcd-demo-cohort`. This fit uses `governed-2026-10-15-january-climate-prod`. #109 already showed the headline counts did not move.

State-relative robust z flags 113 counties. National robust z flags 8. Jaccard 0.025. Median absolute rank shift on the union 1017.5. Spearman of the two max absolute z values 0.224. State-cluster interval for the state-relative flag rate: 0.025 to 0.048.

State-relative flags from states under 40 counties: 1. Flags from states under 15 counties: 0. Metro counties (rural-urban code 1 to 3) are 52 of the state-relative flags and 1186 of the fit cohort. The share gap is 0.083.

States eligible for a detector (at least 80 counties): 16. States whose isolation-forest seeds both flag someone and agree at Jaccard 0.90 or better: 4. The forest is not defensible under the frozen bar. Local outlier factor is defensible. A miss does not by itself change the baseline disposition. Robust distance failed in 0 of 32 state-native states.

Peer bands: fallback 8 states and 61 counties; shrunk 11 states and 283 counties; state_native 32 states and 2800 counties.

What a user would see, for the first listed flag, as an exploratory sentence and not as a shipped screen: Exploratory state-relative signal, separate from the HIGH, MEDIUM, and LOW tiers. Loving County, TX, is unusual compared with state TX (n=254) because uninsured percentile is below the state TX median (0.000 versus median 0.915, robust z -11.85, n=254). This is a surveillance-review flag. It is not a tier, an incidence, a risk, or a hot spot.

State-relative robust-z review list. 25 rows shown.

| County | State | FIPS | Peer | Peer n | Population | SVI | Uninsured | RUCC | Dominant | State z | National z | State flag | National flag | Reason |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | --- | --- | --- |
| Loving County | TX | 48301 | state_native | 254 | 96 | 0.436 | 0.000 | 9 | uninsured_percentile | 11.85 | 4.06 | yes | yes | uninsured percentile is below the state TX median (0.000 versus median 0.915, robust z -11.85, n=254). |
| Borden County | TX | 48033 | state_native | 254 | 686 | 0.027 | 0.006 | 9 | uninsured_percentile | 11.78 | 2.63 | yes | no | uninsured percentile is below the state TX median (0.006 versus median 0.915, robust z -11.78, n=254). |
| Kent County | TX | 48263 | state_native | 254 | 635 | 0.239 | 0.084 | 9 | uninsured_percentile | 10.77 | 2.69 | yes | no | uninsured percentile is below the state TX median (0.084 versus median 0.915, robust z -10.77, n=254). |
| Yates County | NY | 36123 | state_native | 62 | 24,713 | 0.572 | 0.927 | 6 | uninsured_percentile | 9.62 | 1.13 | yes | no | uninsured percentile is above the state NY median (0.927 versus median 0.088, robust z 9.62, n=62). |
| Delta County | TX | 48119 | state_native | 254 | 5,278 | 0.366 | 0.374 | 8 | uninsured_percentile | 7.01 | 1.15 | yes | no | uninsured percentile is below the state TX median (0.374 versus median 0.915, robust z -7.01, n=254). |
| Armstrong County | TX | 48011 | state_native | 254 | 1,912 | 0.086 | 0.403 | 2 | uninsured_percentile | 6.63 | 1.89 | yes | no | uninsured percentile is below the state TX median (0.403 versus median 0.915, robust z -6.63, n=254). |
| Davis County | IA | 19051 | state_native | 99 | 9,093 | 0.459 | 0.994 | 9 | uninsured_percentile | 5.86 | 1.31 | yes | no | uninsured percentile is above the state IA median (0.994 versus median 0.134, robust z 5.86, n=99). |
| Camden County | NC | 37029 | state_native | 100 | 10,547 | 0.252 | 0.047 | 1 | uninsured_percentile | 5.52 | 1.20 | yes | no | uninsured percentile is below the state NC median (0.047 versus median 0.685, robust z -5.52, n=100). |
| Cook County | IL | 17031 | state_native | 102 | 5,225,367 | 0.796 | 0.550 | 1 | log_population | 5.43 | 3.86 | yes | yes | log population is above the state IL median (population 5,225,367, log 15.47 versus median log 10.14, robust z 5.43, n=102). |
| Mahnomen County | MN | 27087 | state_native | 87 | 5,389 | 0.958 | 0.822 | 8 | uninsured_percentile | 5.40 | 1.23 | yes | no | uninsured percentile is above the state MN median (0.822 versus median 0.145, robust z 5.40, n=87). |
| Chattahoochee County | GA | 13053 | state_native | 159 | 9,402 | 0.655 | 0.156 | 2 | uninsured_percentile | 5.36 | 0.91 | yes | no | uninsured percentile is below the state GA median (0.156 versus median 0.828, robust z -5.36, n=159). |
| Polk County | IA | 19153 | state_native | 99 | 493,378 | 0.448 | 0.134 | 2 | log_population | 5.30 | 2.14 | yes | no | log population is above the state IA median (population 493,378, log 13.11 versus median log 9.63, robust z 5.30, n=99). |
| Douglas County | IL | 17041 | state_native | 102 | 19,714 | 0.458 | 0.917 | 8 | uninsured_percentile | 5.25 | 1.11 | yes | no | uninsured percentile is above the state IL median (0.917 versus median 0.189, robust z 5.25, n=102). |
| Rockwall County | TX | 48397 | state_native | 254 | 110,631 | 0.116 | 0.526 | 1 | uninsured_percentile | 5.05 | 1.12 | yes | no | uninsured percentile is below the state TX median (0.526 versus median 0.915, robust z -5.05, n=254). |
| Clearwater County | MN | 27029 | state_native | 87 | 8,541 | 0.778 | 0.775 | 8 | uninsured_percentile | 5.02 | 0.80 | yes | no | uninsured percentile is above the state MN median (0.775 versus median 0.145, robust z 5.02, n=87). |
| Queens County | NY | 36081 | state_native | 62 | 2,360,826 | 0.802 | 0.526 | 1 | uninsured_percentile | 5.01 | 3.28 | yes | no | uninsured percentile is above the state NY median (0.526 versus median 0.088, robust z 5.01, n=62). |
| Jefferson County | KY | 21111 | state_native | 120 | 779,232 | 0.622 | 0.189 | 1 | log_population | 4.95 | 2.47 | yes | no | log population is above the state KY median (population 779,232, log 13.57 versus median log 9.88, robust z 4.95, n=120). |
| Seneca County | NY | 36099 | state_native | 62 | 33,651 | 0.574 | 0.514 | 6 | uninsured_percentile | 4.88 | 0.20 | yes | no | uninsured percentile is above the state NY median (0.514 versus median 0.088, robust z 4.88, n=62). |
| Van Buren County | IA | 19177 | state_native | 99 | 7,207 | 0.361 | 0.848 | 9 | uninsured_percentile | 4.86 | 0.93 | yes | no | uninsured percentile is above the state IA median (0.848 versus median 0.134, robust z 4.86, n=99). |
| Sioux County | ND | 38085 | state_native | 53 | 3,896 | 0.918 | 0.993 | 9 | svi_percentile | 4.81 | 1.37 | yes | no | SVI percentile is above the state ND median (0.918 versus median 0.149, robust z 4.81, n=53). |
| Nobles County | MN | 27105 | state_native | 87 | 22,194 | 0.832 | 0.748 | 7 | uninsured_percentile | 4.80 | 0.90 | yes | no | uninsured percentile is above the state MN median (0.748 versus median 0.145, robust z 4.80, n=87). |
| Plumas County | CA | 06063 | state_native | 58 | 19,650 | 0.409 | 0.156 | 9 | rucc_2023 | 4.72 | 0.91 | yes | no | rural-urban code is above the state CA median (9 versus median 2.0, robust z 4.72, n=58). |
| Lafayette County | FL | 12067 | state_native | 67 | 8,107 | 0.841 | 0.871 | 9 | rucc_2023 | 4.72 | 0.98 | yes | no | rural-urban code is above the state FL median (9 versus median 2.0, robust z 4.72, n=67). |
| Johnson County | KS | 20091 | state_native | 105 | 610,742 | 0.060 | 0.215 | 1 | rucc_2023 | 4.72 | 2.30 | yes | no | rural-urban code is below the state KS median (1 versus median 8.0, robust z -4.72, n=105). |
| Leavenworth County | KS | 20103 | state_native | 105 | 82,050 | 0.247 | 0.340 | 1 | rucc_2023 | 4.72 | 1.12 | yes | no | rural-urban code is below the state KS median (1 versus median 8.0, robust z -4.72, n=105). |

Flagged by the state-relative rule and not by the national rule. 15 rows shown.

| County | State | FIPS | Peer | Peer n | Population | SVI | Uninsured | RUCC | Dominant | State z | National z | State flag | National flag | Reason |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | --- | --- | --- |
| Borden County | TX | 48033 | state_native | 254 | 686 | 0.027 | 0.006 | 9 | uninsured_percentile | 11.78 | 2.63 | yes | no | uninsured percentile is below the state TX median (0.006 versus median 0.915, robust z -11.78, n=254). |
| Kent County | TX | 48263 | state_native | 254 | 635 | 0.239 | 0.084 | 9 | uninsured_percentile | 10.77 | 2.69 | yes | no | uninsured percentile is below the state TX median (0.084 versus median 0.915, robust z -10.77, n=254). |
| Yates County | NY | 36123 | state_native | 62 | 24,713 | 0.572 | 0.927 | 6 | uninsured_percentile | 9.62 | 1.13 | yes | no | uninsured percentile is above the state NY median (0.927 versus median 0.088, robust z 9.62, n=62). |
| Delta County | TX | 48119 | state_native | 254 | 5,278 | 0.366 | 0.374 | 8 | uninsured_percentile | 7.01 | 1.15 | yes | no | uninsured percentile is below the state TX median (0.374 versus median 0.915, robust z -7.01, n=254). |
| Armstrong County | TX | 48011 | state_native | 254 | 1,912 | 0.086 | 0.403 | 2 | uninsured_percentile | 6.63 | 1.89 | yes | no | uninsured percentile is below the state TX median (0.403 versus median 0.915, robust z -6.63, n=254). |
| Davis County | IA | 19051 | state_native | 99 | 9,093 | 0.459 | 0.994 | 9 | uninsured_percentile | 5.86 | 1.31 | yes | no | uninsured percentile is above the state IA median (0.994 versus median 0.134, robust z 5.86, n=99). |
| Camden County | NC | 37029 | state_native | 100 | 10,547 | 0.252 | 0.047 | 1 | uninsured_percentile | 5.52 | 1.20 | yes | no | uninsured percentile is below the state NC median (0.047 versus median 0.685, robust z -5.52, n=100). |
| Mahnomen County | MN | 27087 | state_native | 87 | 5,389 | 0.958 | 0.822 | 8 | uninsured_percentile | 5.40 | 1.23 | yes | no | uninsured percentile is above the state MN median (0.822 versus median 0.145, robust z 5.40, n=87). |
| Chattahoochee County | GA | 13053 | state_native | 159 | 9,402 | 0.655 | 0.156 | 2 | uninsured_percentile | 5.36 | 0.91 | yes | no | uninsured percentile is below the state GA median (0.156 versus median 0.828, robust z -5.36, n=159). |
| Polk County | IA | 19153 | state_native | 99 | 493,378 | 0.448 | 0.134 | 2 | log_population | 5.30 | 2.14 | yes | no | log population is above the state IA median (population 493,378, log 13.11 versus median log 9.63, robust z 5.30, n=99). |
| Douglas County | IL | 17041 | state_native | 102 | 19,714 | 0.458 | 0.917 | 8 | uninsured_percentile | 5.25 | 1.11 | yes | no | uninsured percentile is above the state IL median (0.917 versus median 0.189, robust z 5.25, n=102). |
| Rockwall County | TX | 48397 | state_native | 254 | 110,631 | 0.116 | 0.526 | 1 | uninsured_percentile | 5.05 | 1.12 | yes | no | uninsured percentile is below the state TX median (0.526 versus median 0.915, robust z -5.05, n=254). |
| Clearwater County | MN | 27029 | state_native | 87 | 8,541 | 0.778 | 0.775 | 8 | uninsured_percentile | 5.02 | 0.80 | yes | no | uninsured percentile is above the state MN median (0.775 versus median 0.145, robust z 5.02, n=87). |
| Queens County | NY | 36081 | state_native | 62 | 2,360,826 | 0.802 | 0.526 | 1 | uninsured_percentile | 5.01 | 3.28 | yes | no | uninsured percentile is above the state NY median (0.526 versus median 0.088, robust z 5.01, n=62). |
| Jefferson County | KY | 21111 | state_native | 120 | 779,232 | 0.622 | 0.189 | 1 | log_population | 4.95 | 2.47 | yes | no | log population is above the state KY median (population 779,232, log 13.57 versus median log 9.88, robust z 4.95, n=120). |

Flagged by the national rule and not by the state-relative rule. 5 rows shown.

| County | State | FIPS | Peer | Peer n | Population | SVI | Uninsured | RUCC | Dominant | State z | National z | State flag | National flag | Reason |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | --- | --- | --- |
| Kalawao County | HI | 15005 | region_peer | 449 | 50 | 0.187 | 0.307 | 3 | log_population | 3.44 | 4.53 | no | yes |  |
| Los Angeles County | CA | 06037 | state_native | 58 | 9,936,690 | 0.863 | 0.550 | 1 | joint | 1.91 | 4.32 | no | yes |  |
| Kenedy County | TX | 48261 | state_native | 254 | 116 | 0.668 | 0.933 | 9 | log_population | 3.24 | 3.92 | no | yes |  |
| Maricopa County | AZ | 04013 | state_shrunk | 15 | 4,430,871 | 0.713 | 0.689 | 1 | joint | 2.17 | 3.74 | no | yes |  |
| San Diego County | CA | 06073 | state_native | 58 | 3,289,701 | 0.706 | 0.403 | 1 | joint | 1.38 | 3.52 | no | yes |  |

Surveillance-status minority rule flags 246 counties inside their peer group and 896 counties under the same rule fit nationally. That rule is not part of the robust-z disposition.

Surveillance-status review list. 25 rows shown.

| County | State | FIPS | Peer | Peer n | Population | SVI | Uninsured | RUCC | Dominant | State z | National z | State flag | National flag | Reason |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: | --- | --- | --- |
| Kent County | DE | 10001 | class_peer | 585 | 182,400 | 0.815 | 0.359 | 3 | joint | 1.40 | 1.42 | no | no |  |
| New Castle County | DE | 10003 | class_peer | 585 | 570,567 | 0.513 | 0.189 | 1 | joint | 2.35 | 2.25 | no | no |  |
| Sussex County | DE | 10005 | class_peer | 585 | 240,668 | 0.518 | 0.359 | 4 | joint | 1.63 | 1.62 | no | no |  |
| District of Columbia | DC | 11001 | class_peer | 585 | 670,587 | 0.626 | 0.029 | 1 | joint | 2.48 | 2.37 | no | no |  |
| Bradford County | FL | 12007 | state_native | 67 | 27,816 | 0.887 | 0.682 | 6 | rucc_2023 | 2.70 | 1.04 | no | no |  |
| Brevard County | FL | 12009 | state_native | 67 | 610,723 | 0.482 | 0.619 | 2 | joint | 1.52 | 2.30 | no | no |  |
| Broward County | FL | 12011 | state_native | 67 | 1,940,907 | 0.781 | 0.833 | 1 | joint | 1.51 | 3.14 | no | no |  |
| Charlotte County | FL | 12015 | state_native | 67 | 189,900 | 0.595 | 0.633 | 3 | joint | 0.89 | 1.45 | no | no |  |
| Collier County | FL | 12021 | state_native | 67 | 380,221 | 0.614 | 0.739 | 2 | joint | 0.79 | 1.95 | no | no |  |
| Gilchrist County | FL | 12041 | state_native | 67 | 18,070 | 0.734 | 0.813 | 2 | joint | 1.11 | 0.90 | no | no |  |
| Hardee County | FL | 12049 | state_native | 67 | 25,528 | 0.993 | 0.851 | 6 | rucc_2023 | 2.70 | 1.33 | no | no |  |
| Hillsborough County | FL | 12057 | state_native | 67 | 1,468,560 | 0.779 | 0.743 | 1 | joint | 1.35 | 2.93 | no | no |  |
| Holmes County | FL | 12059 | state_native | 67 | 19,529 | 0.808 | 0.898 | 8 | rucc_2023 | 4.05 | 1.06 | yes | no | rural-urban code is above the state FL median (8 versus median 2.0, robust z 4.05, n=67). |
| Lake County | FL | 12069 | state_native | 67 | 386,829 | 0.621 | 0.646 | 1 | joint | 0.75 | 1.97 | no | no |  |
| Lee County | FL | 12071 | state_native | 67 | 772,902 | 0.709 | 0.788 | 2 | joint | 0.99 | 2.47 | no | no |  |
| Manatee County | FL | 12081 | state_native | 67 | 405,069 | 0.633 | 0.754 | 2 | joint | 0.69 | 2.00 | no | no |  |
| Marion County | FL | 12083 | state_native | 67 | 378,225 | 0.820 | 0.769 | 2 | joint | 0.59 | 1.95 | no | no |  |
| Martin County | FL | 12085 | state_native | 67 | 159,399 | 0.464 | 0.593 | 2 | joint | 1.61 | 1.32 | no | no |  |
| Miami-Dade County | FL | 12086 | state_native | 67 | 2,688,237 | 0.881 | 0.865 | 1 | joint | 1.69 | 3.37 | no | no |  |
| Orange County | FL | 12095 | state_native | 67 | 1,427,403 | 0.795 | 0.779 | 1 | joint | 1.33 | 2.91 | no | no |  |
| Palm Beach County | FL | 12099 | state_native | 67 | 1,494,805 | 0.801 | 0.813 | 1 | joint | 1.36 | 2.95 | no | no |  |
| Pasco County | FL | 12101 | state_native | 67 | 569,211 | 0.704 | 0.704 | 1 | joint | 0.82 | 2.25 | no | no |  |
| Pinellas County | FL | 12103 | state_native | 67 | 959,918 | 0.710 | 0.674 | 1 | joint | 1.11 | 2.63 | no | no |  |
| St. Johns County | FL | 12109 | state_native | 67 | 278,722 | 0.127 | 0.395 | 1 | svi_percentile | 3.47 | 1.73 | no | no |  |
| St. Lucie County | FL | 12111 | state_native | 67 | 334,682 | 0.791 | 0.779 | 2 | joint | 0.52 | 1.86 | no | no |  |

Scores are surveillance-review flags. They are not incidence, risk, causation, or hot spots. `No records` and `Unknown` are not negatives. A missing human floor is not zero. A published human count is a lower bound. Counties in one state share reporting rules, so the interval resamples states. Population, vulnerability, insurance, rural-urban code, the 2023 human year, and cumulative tick and pathogen status are not one time base. Temporal detection is not feasible on this single snapshot and was not fit. Historical CDC objects were not read. Exclusions before the fit: 0. No tier, Tier 1 model, PROD batch, or API field changes.

## Decision

proceed. Proceed with a follow-on design for the interpretable state-relative baseline only. Do not change the tiers. Isolation forest and local outlier factor stay out of that follow-on unless the frozen detector bar was met. The detector bar was met for local outlier factor, so a later story could test that method again. A code-only slice, if a later review column is authorized, is log population and the rural-urban code. A protected slice is the social-vulnerability percentile and the uninsured percentile. Surveillance status is a third slice. It can explain a pattern. It is not an outreach rank.

Proposed follow-on outlines under #22. These are not opened as issues.

1. Code-only. Question: which counties are unusual for their state on size and rural-urban code, as a review flag beside the tiers? Model family: within-peer median and MAD robust z, with the frozen shrinkage and region or class fallback. Baseline: the national robust z on the same two features. Evaluation: Jaccard, median absolute rank shift, small-state share, and a state-cluster bootstrap. Persistence: ML Lab score table only. Not PROD and not the tier batch.
2. Protected. Question: does adding SVI and uninsured percentiles change the explanation of a code-only flag, without using them as an outreach rank? Model family: the same robust z, explanation only. Baseline: the code-only flag set. Evaluation: share of flags whose dominant feature is one of those two percentiles. Persistence: separate lab columns. Not an API field.
3. Local outlier factor, because the frozen bar was met. Question: which counties in states of at least 80 are density outliers relative to state peers, as a review flag beside the robust-z list? Model family: local outlier factor, 20 neighbors, contamination 0.05. Baseline: the state-relative robust z, compared by matched-count Jaccard. Evaluation: nested contamination stability at 0.90 and a state-cluster bootstrap of the flag rate. Persistence: ML Lab score columns only. Not PROD and not the tier batch. Isolation forest stays out: its seed bar was not met.

## Reproduction and retained evidence

The run row stores git commit `2096b7a8f5e4bd4bb24c93a1f1aa97d8ab39614c` because that was HEAD when the fit wrote `REGISTRY.RUNS`. Fit code commit `547193ae7774944c2fc9b9428ef451cf8773f754`. Release `governed-2026-10-15-january-climate-prod`. Seeds 1062026 and 1062027. Do not rerun the script against the same run id.

```text
uv sync --locked --extra dev --extra snowflake
uv run python scripts/check_ml_agent_context.py
MPLBACKEND=Agg uv run --with matplotlib --with seaborn python scripts/eda_106_state_anomaly.py
uv run python scripts/verify.py
```

Run id `106-state-relative-anomaly-20261026T0012Z`. Lab row counts: `REGISTRY.RUNS` 1, `EDA.METRICS_LONG` 11, `EDA.FINDINGS` 3, `REGISTRY.QUERIES` 4, `EXPERIMENTS.EXPERIMENTS` 6, `EXPERIMENTS.MODEL_METRICS` 5, `EDA.COUNTY_STATE_ANOMALY_106` 3144, `REGISTRY.ARTIFACTS` 2. Drive charts: [state-sample-size.png](https://drive.google.com/file/d/1sfRDfYvMk6knKLrnrquEcERtoybwHLAC/view?usp=drivesdk) (7238 bytes), [within-state-spread.png](https://drive.google.com/file/d/1bIVwWQ1GS8XWPBQ3wot-k2PrbP89432d/view?usp=drivesdk) (9128 bytes). Folder: [issue-106](https://drive.google.com/drive/folders/1uBUBbj3dlLYqZBrRkr2NVQsIKnF2SIbA). Each file was read back and matched the local byte size. Upload failures: none. Charts skipped for small-cell protection: flag-agreement.png, seed-stability.png. EDA record: `docs/eda/106-state-relative-anomaly.md`. Spec: `docs/eda/106-analysis-spec.md`. The shared lab writers do not grant SELECT. `OH_LYME_PROD_READ` cannot count `EDA.COUNTY_STATE_ANOMALY_106` until an owner grants it.

County scores, including names, stay in `EDA.COUNTY_STATE_ANOMALY_106`. Charts and Drive files are aggregate figures and do not name counties. A full county extract was not committed.
