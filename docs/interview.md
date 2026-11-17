# Talking about the project

## Résumé bullet

Built SisterTwin from scratch using SQL Server, Python, and C#/.NET to identify automotive catalog coverage gaps and produce reviewable application candidates; the initial phase supported 62k successfully imported application lines after cleanup and validation.

The import result is owner-reported and confirmed, not independently reconciled to an import ledger. Do not describe the 62k lines as unique parts or vehicles, or attribute them to a specific later algorithm version.

## Short interview explanation

“I built this after listening to what our catalog team needed. Related vehicles can help us spot missing coverage, but sharing a platform doesn't mean every part fits. I translated that distinction into checks for vehicle identity, target eligibility, and competing part lists. The tool produces reports that show what was selected and what needs review. In the initial phase, I used the project to add 62k application lines after cleanup and validation. The technical decision I'd highlight is requiring one reference to contain the complete eligible part set, while keeping the application details and leaving unresolved cases for a person to review.”

## Most valuable next improvement

Add an approval-to-import audit trail: stable candidate identifiers, reviewer decisions and reasons, validation outcomes, and imported record identifiers. This would make approved additions and the measured catalog impact reproducible, while keeping human review separate from automated candidate selection.
