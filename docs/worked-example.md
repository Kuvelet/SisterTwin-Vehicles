# Fictional worked example

All brands, models, parts, and records below are invented. These examples demonstrate decisions, not real fitment advice.

## From existing application to candidate

An existing application says fictional `DEMO-001`, a relay, applies to the **2022 Aster Atlas**, with engine text `2.0L`, position `Front`, and region `North`. A relationship list pairs Atlas with **2022 Boreal Brook**. Both identities exist in our fictional validation fixture, but Brook has no relay description in its catalog coverage.

The target dictionary contains Brook/2022/`2.0L` with region `North`, so this source row becomes eligible. A second Atlas row using `3.0L` has no matching target region: it stays visible with `Exclude - Missing Region is NULL`. Vehicle existence alone did not make it eligible.

Two reference vehicles supply eligible relay applications for Brook:

| Reference | Distinct eligible parts | Engine style | Application rows |
| --- | --- | --- | --- |
| Aster Atlas | DEMO-001, DEMO-002 | All specified | 2 |
| Cedar Crest | DEMO-001, DEMO-002, DEMO-003 | All specified | 4 |

Cedar's four rows include two positions for DEMO-001. Cedar contains the whole union, so it wins. Even if Aster's engines were all blank, completeness would still select Cedar before the engine tie-break. All four eligible Cedar application rows receive `Include - selected reference vehicle`; the two eligible Aster rows receive `Exclude - another reference vehicle selected`.

These four rows are **candidates**, not four approved additions. A catalog reviewer must evaluate the relationship, engines, positions, notes, and other qualifiers. Approved candidates then require target-column preparation, overlap checks, PIM validation, and import. Approval or import counts cannot be inferred from this report alone.

## Ambiguous group

For fictional target **2022 Boreal Bay**, Aster has `{DEMO-001, DEMO-002}` and Cedar has `{DEMO-001, DEMO-003}`. The union is `{DEMO-001, DEMO-002, DEMO-003}`, but neither reference contains it. All four eligible rows receive `Needs review - no reference contains all eligible parts`.

The workflow deliberately leaves this unresolved. Combining both references would conceal the fact that neither supplies a complete source set. A human must investigate the disagreement before preparing any additions.

## Other boundaries

An eligible blank part number sends the entire eligible group for review. A blank part on a NULL-region row does not poison the eligible set. When complete references have identical part sets, engine category, eligible row count, and alphabetical order settle the tie. These examples explain the selection rules; they are not a runnable sample or real fitment recommendations.
