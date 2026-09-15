# Repository guidance

## Scope

This repository is being initialized for a crowd-monitoring system. Keep early changes focused on project setup, documentation, and agreed architecture; do not add application features until requirements and the initial stack are confirmed.

## Development conventions

- Inspect existing files and the Git working tree before changing anything.
- Preserve user-authored or unrelated work; avoid destructive Git commands.
- Keep secrets, API keys, recordings, and personally identifiable data out of the repository. Use documented environment-variable configuration with an example file when configuration is introduced.
- Prefer small, focused changes with clear names and documentation for setup or operational decisions.
- Add or update automated checks alongside implementation work, and run the relevant checks before handing work back.

## Crowd-monitoring considerations

- Design for privacy, data minimization, and appropriate retention from the outset.
- Never commit raw camera footage, biometric identifiers, or production-derived sensitive data.
- Document assumptions, data sources, model limitations, and alerting thresholds when those capabilities are introduced.
