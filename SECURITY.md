# SECURITY & ETHICS

This project aims to **reduce wildlife-vehicle collisions** and **help authorities respond** to health events ethically and lawfully.

## Privacy
- Do **not** store faces/plates unless explicitly permitted by local law & policy.
- Prefer **in-memory** inference, drop frames after decisioning.
- Configure masking/blur for any sensitive content.

## Safety
- **Fail-safe** defaults: if detection is uncertain, choose a conservative traffic phase (e.g., extend red / animal crossing mode).
- Provide a manual override and clear operator status.

## Data Use
- Share only **aggregated** or **event-based** data externally.
- If deploying, follow guidance from DOT, local transportation authorities, and wildlife agencies.

## Scope
- The included "health check" is **simulated**. Real deployments must use vetted, non-invasive sensors and be reviewed by bioethics boards and appropriate agencies.