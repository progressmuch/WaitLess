# Transport System Documentation

This folder contains the specifications for the Transport Tracking and Commuter Information System.

## Technology

- Python
- FastAPI
- PostgreSQL
- SQLAlchemy
- Alembic
- Flutter
- JWT authentication
- GPS location tracking

## Documentation

| File | Purpose |
|---|---|
| `00-development-roadmap.md` | Incremental development phases |
| `01-project-overview.md` | System purpose and users |
| `02-product-requirements.md` | Functional/non-functional requirements |
| `03-system-architecture.md` | Architecture and component responsibilities |
| `04-database-specification.md` | PostgreSQL database design |
| `05-api-specification.md` | REST API contract |
| `06-deployment-specifications.md` | Deployment requirements |
| `07-testing-strategy.md` | Testing approach |
| `08-ai-workflow-rules.md` | Rules for OpenCode |
| `09-backend-project-structure.md` | Recommended backend structure |
| `10-openapi-and-api-conventions.md` | API conventions |
| `11-phase-implementation-prompts.md` | Ready-to-use OpenCode prompts |
| `12-phase1-summary.md` | Phase 1 summary |
| `15-completed-phases-5-8.md` | Summary of phases 5–8 |
| `16-supabase-setup.md` | Supabase database + Render deployment guide |
| `17-user-guide.md` | Plain-language user manual for management, operators and commuters |
| `convert_to_docx.ps1` | Converts the user guide to a Microsoft Word document (needs pandoc) |

## Important Development Principle

The system must be developed incrementally.

Start with:

```text
Phase 0 → Phase 1 → Phase 2 → Phase 3 → Phase 4
→ Phase 5 → Phase 6 → Phase 7 → Phase 8
```

OpenCode must not implement all phases in one request.

Each phase must be:
1. Implemented.
2. Tested.
3. Reviewed.
4. Documented.
5. Committed.

Only then should the next phase begin.
