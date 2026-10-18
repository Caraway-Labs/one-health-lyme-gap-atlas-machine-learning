# 119: Which surveillance situations does the county release contain?

- Issue: [ML #119](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/119); evaluation task [ML #134](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/134). The question is which surveillance situations the national county release contains, how many counties and people sit in each, and which are large enough to describe separately. A class is a surveillance situation. It is not disease risk, incidence, or a production score.
- Data: `PRESENTATION.CURRENT_COUNTY_ATLAS_V` in `ONE_HEALTH_LYME_GAP_ATLAS_PROD`. Release `governed-2026-10-15-january-climate-prod`. Bundle SHA-256 `53e50aa37c701635e96c48cd4931c4c4a9e7e695c146263fb9bb335e541ae74d`. Task #134 names the earlier October 6 release. [ML #136](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/136) replaced that identity before the fit, and the fit used the October 15 release.
- Cohort: all 3,144 counties, including the District of Columbia, Connecticut planning regions, Alaska, and Hawaii. Human status is calendar year 2023. Tick and pathogen status are cumulative through 2025-12-31. Population is the 2022 reporting denominator, 331,097,593 people. Primary seed `1192026`.

## Method and assumptions

The evaluation plan is [119-evaluation-plan.md](../methodology/119-evaluation-plan.md). It was fixed before these class descriptions. The assignments come from the finished fit. This note does not choose a new class count.

Estimand A uses human status, blacklegged-tick status, western-blacklegged-tick status, and pathogen status. Estimand B uses the tick and pathogen statuses only. Within a class, the model treats those indicators as independent. `No records` and `Unknown` stay categories. The human blank stays `no_county_linked_record`.

The class count is 4 for each estimand. That is the count selected in [119-class-count-selection.md](../methodology/119-class-count-selection.md). The baseline remains the 19 occupied four-state cells in [119-baseline-comparison.md](../methodology/119-baseline-comparison.md). Four classes are a coarser summary of that table. They are not a better likelihood than the table.

## Material findings and limits

County shares below use 3,144 counties. Population shares use 331,097,593 people. Shares are shown to one decimal. Class numbers are labels from the primary seed.

### Four-state situations

| Class | Name | Counties | County share | People | Population share |
| ---: | --- | ---: | ---: | ---: | ---: |
| 0 | Established blacklegged tick | 801 | 25.5% | 139,675,248 | 42.2% |
| 1 | Unknown tick and pathogen status | 35 | 1.1% | 2,185,410 | 0.7% |
| 2 | Western blacklegged tick recorded | 112 | 3.6% | 54,119,896 | 16.3% |
| 3 | Pathogen not recorded | 2,196 | 69.8% | 135,117,039 | 40.8% |

Class 0 is 801 counties. Blacklegged tick status is `Established` in 784 and `Reported` in 17. Western blacklegged tick status is `No records` in all 801. Pathogen status is `Present` in 655 and `No records` in 146. Human status is `published_count_floor` in 585 and `no_county_linked_record` in 216. The largest single combination is a published human floor, an established blacklegged tick, no western blacklegged record, and pathogen present: 438 counties and 83,910,033 people.

Class 1 is one combination: human blank, and `Unknown` for both tick species and the pathogen. It has 35 counties and 2,185,410 people.

Class 2 is 112 counties. Blacklegged tick status is `No records` in all 112. Western blacklegged tick status is `Established` in 97 and `Reported` in 15. Human status is blank in 101. Pathogen status is `No records` in 79 and `Present` in 33. The largest combination is a human blank, no blacklegged record, an established western blacklegged tick, and no pathogen record: 59 counties and 18,340,571 people.

Class 3 is 2,196 counties. Pathogen status is `No records` in 2,195. Western blacklegged tick status is `No records` in all 2,196. Human status is blank in 2,141. Blacklegged tick status is mixed: `No records` in 1,215, `Established` in 523, and `Reported` in 458. The largest combination is a human blank and no records for both ticks and the pathogen: 1,189 counties and 54,861,634 people. The 523 established-blacklegged counties in this class have no pathogen record and no published human floor.

Alaska has 30 counties and Hawaii has 5. All 35 are in class 1, and class 1 contains no other county. The Unknown check passes. This class is the Alaska and Hawaii surveillance record. It is the situation for those states in this release. A lower-48 field description does not include it.

The 228-county pattern is the two baseline cells with a human blank, one tick species `Established`, the other `No records`, and pathogen `Present`. All 200 blacklegged-tick counties in that pattern are in class 0. All 28 western-blacklegged counties in that pattern are in class 2. None are in class 1 or class 3. The pattern is not its own class. It sits inside the established-tick situations, split by species. Class 0 also holds 438 counties with the same tick and pathogen pattern and a published human floor. The class count was not changed after this count.

Classes 0 and 3 are large in both counties and people. Class 2 is 112 counties and 54,119,896 people, and its tick species differs from class 0, so it is a separate situation. Class 3 still mixes counties with no tick records and counties with an established blacklegged tick and no pathogen record. One description of class 3 has to keep that mix visible.

### Stability of the chosen count

Four-state BIC, median adjusted Rand index, smallest class, and eligibility:

| Classes | BIC | Median adjusted Rand index | Smallest class | Eligible |
| ---: | ---: | ---: | ---: | --- |
| 2 | 12836.468 | 1.0000 | 820 | True |
| 3 | 12253.163 | 0.9471 | 35 | True |
| 4 | 12054.338 | 1.0000 | 35 | True |
| 5 | 12083.116 | 0.9990 | 35 | True |
| 6 | 12162.629 | 0.8060 | 33 | False |

Counts 2 through 5 are eligible. Count 4 has the lowest BIC, 12054.338. Count 5 is 28.778 higher, outside the margin of 6. The rule selects 4.

Tick-and-pathogen:

| Classes | BIC | Median adjusted Rand index | Smallest class | Eligible |
| ---: | ---: | ---: | ---: | --- |
| 2 | 10653.471 | 1.0000 | 673 | True |
| 3 | 10093.738 | 1.0000 | 68 | True |
| 4 | 9939.742 | 0.9997 | 35 | True |
| 5 | 10002.975 | 0.5700 | 15 | False |
| 6 | 10075.454 | 0.7801 | 0 | False |

Counts 2 through 4 are eligible. Count 4 has the lowest BIC, 9939.742. Count 5 fails the stability rule. The rule selects 4. Both selected models converged.

### Tick-and-pathogen probabilities for later use

| Class | Name | Counties | County share | People | Population share |
| ---: | --- | ---: | ---: | ---: | ---: |
| 0 | Established blacklegged tick | 1,325 | 42.1% | 181,862,120 | 54.9% |
| 1 | Blacklegged tick not established, pathogen not recorded | 1,687 | 53.7% | 96,505,743 | 29.1% |
| 2 | Western blacklegged tick established | 97 | 3.1% | 50,544,320 | 15.3% |
| 3 | Unknown tick and pathogen status | 35 | 1.1% | 2,185,410 | 0.7% |

This fit does not use human status. Class 3 is the same 35 Alaska and Hawaii counties. The 200-county blacklegged gap cell is inside class 0. The 28-county western gap cell is inside class 2.

The probabilities are fit to offer to a later linear model, and to [ML #122](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/122), as a grouping of tick and pathogen surveillance. They are separate from every class that includes human status. The four-state class must stay out of a later model whose outcome is the human floor.

The offer has a hard limit. In the tick-and-pathogen fit, the established-blacklegged class assigns probability essentially 1 both to the 638 counties with pathogen `Present` and to the 669 counties with pathogen `No records`. The probability does not separate those two cells. A later model may use the class or the probabilities as this grouping. It may not read them as pathogen presence, human risk, incidence, or as the 228-county list.

County rows in one state are dependent. BIC and the adjusted Rand index are descriptive. They are not independent-sample tests. `No records` is not biological absence. `Unknown` is not a measured zero.

## Decision

**PROCEED** to the lifecycle decision. Keep both assignment tables as the experiment result. Offer the tick-and-pathogen probabilities to later stories only as the grouping described above. Do not publish a production score, and do not refit from the 228-county count.

## Reproduction and retained evidence

- Code revision: `cd936fe345664e606c916b137dd642caa0d6d73b`. Result: [119-latent-class-v1-result.json](../../config/experiments/119-latent-class-v1-result.json). Experiment config: [119-latent-class-v1.json](../../config/experiments/119-latent-class-v1.json). Dependencies recorded in the result: numpy 2.2.6 and scikit-learn 1.9.1.
- Entry points: `scripts/describe_119_latent_class.py`, `scripts/fit_119_latent_class.py`, and `sql/datasets/119_surveillance_latent_class_inputs.sql`.
- Replay the class tables from the local extract of the pinned release:

  ```powershell
  uv run python scripts/describe_119_latent_class.py --counties outputs/119-latent-class/counties.json
  ```

- Verification: `uv run python scripts/verify.py`.
- Lifecycle evidence: [119-lifecycle-state.json](../methodology/119-lifecycle-state.json).
- Transient artifacts intentionally not committed: `outputs/119-latent-class/`, including the county extract and the working summaries used to draft this note.
