# AGENTS.md

## Project Context

This repository is Attestplane. Keep the release-train and planning workflow consistent with the active runbooks under `docs/runbooks/`.

## Planning Workflow

All three development tiers use the same task flow:

1. Consult Opus first.
2. Generate a plan.
3. Open a `development-plan` issue.
4. Convert the accepted plan into `planned-task` issues.
5. Execute the resulting tasks one by one.

The only difference between tiers is the consultation granularity:

- Daily development: diff-level consultation.
- Medium development: feature or milestone-level consultation.
- Architecture development: architecture-level consultation.

Do not skip the consultation step for any tier. Do not bypass the plan issue. Do not create `planned-task` issues directly without the plan flow.

## Safety Redlines

- Do not publish unless the release workflow explicitly requires it.
- Do not merge without the required gates.
- Do not push to any remote unless explicitly authorized for that target.
- Do not print secrets.
