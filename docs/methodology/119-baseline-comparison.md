# ML #119 baseline comparison

Owning task: [ML #132](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/132). Dataset `surveillance-latent-class-counties` `v1.1`. The class-count range is the one frozen in [119-analysis-spec.md](../eda/119-analysis-spec.md): K = 2, 3, 4, 5, and 6.

The baseline is the observed cross-classification of the admitted categories. It is the complete description of those categories. It is not a second model, and it is not a score to beat.

Counts below are from the 2026-10-17 production refresh in [136-production-refresh.md](../eda/136-production-refresh.md). They match the earlier rolled catalog. No latent-class model was fit to produce them.

## Estimand A

Nineteen of the 96 possible human × blacklegged-tick × western-blacklegged-tick × pathogen cells are occupied. The other cells are empty on this release. An empty cell stays empty. It is not a zero that was filled in.

| Human status | Blacklegged tick | Western blacklegged tick | Pathogen | Counties | People |
| --- | --- | --- | --- | ---: | ---: |
| `no_county_linked_record` | No records | No records | No records | 1,189 | 54,861,634 |
| `no_county_linked_record` | Established | No records | No records | 523 | 42,167,012 |
| `published_count_floor` | Established | No records | Present | 438 | 83,910,033 |
| `no_county_linked_record` | Reported | No records | No records | 428 | 29,569,755 |
| `no_county_linked_record` | Established | No records | Present | 200 | 10,486,999 |
| `published_count_floor` | Established | No records | No records | 146 | 42,924,965 |
| `no_county_linked_record` | No records | Established | No records | 59 | 18,340,571 |
| `no_county_linked_record` | Unknown | Unknown | Unknown | 35 | 2,185,410 |
| `published_count_floor` | Reported | No records | No records | 30 | 5,941,373 |
| `no_county_linked_record` | No records | Established | Present | 28 | 12,217,147 |
| `published_count_floor` | No records | No records | No records | 25 | 2,557,405 |
| `no_county_linked_record` | Reported | No records | Present | 16 | 1,237,848 |
| `no_county_linked_record` | No records | Reported | No records | 14 | 1,309,650 |
| `published_count_floor` | No records | Established | No records | 5 | 5,712,251 |
| `published_count_floor` | No records | Established | Present | 5 | 14,274,351 |
| `published_count_floor` | Reported | No records | Present | 1 | 1,115,403 |
| `published_count_floor` | No records | Reported | No records | 1 | 2,265,926 |
| `no_county_linked_record` | No records | No records | Present | 1 | 19,860 |

The two established-tick, pathogen-present, no-human-floor rows are 200 and 28 counties. Together they are the 228-county pattern. That pattern is an evaluation question for a later task. It is not an input to the class-count rule.

## Estimand B

The tick-and-pathogen baseline drops human status and adds the matching rows. It is fit separately. It is not the four-state result with human status removed after the fact.

| Blacklegged tick | Western blacklegged tick | Pathogen | Counties | People |
| --- | --- | --- | ---: | ---: |
| No records | No records | No records | 1,214 | 57,419,039 |
| Established | No records | No records | 669 | 85,091,977 |
| Established | No records | Present | 638 | 94,397,032 |
| Reported | No records | No records | 458 | 35,511,128 |
| No records | Established | No records | 64 | 24,052,822 |
| Unknown | Unknown | Unknown | 35 | 2,185,410 |
| No records | Established | Present | 33 | 26,491,498 |
| Reported | No records | Present | 17 | 2,353,251 |
| No records | Reported | No records | 15 | 3,575,576 |
| No records | No records | Present | 1 | 19,860 |

## What a later fit has to show

A selected class count improves on its own baseline when the classes are a stable, smaller summary of that table: every county gets a class and class probabilities, and the dominant pattern inside each class can be read back to these levels. A higher likelihood than the full table is not the comparison. The full table already describes every occupied cell. The fit does not choose its class count by matching the 228-county rows or any other named cell.
