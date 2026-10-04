# AI / OpenCode Workflow Rules

## 1. Primary Rule

OpenCode must develop the project incrementally.

NEVER ask the AI to build the entire system in one operation.

## 2. Read Before Coding

Before making changes, OpenCode must read:

```text
docs/01-project-overview.md
docs/02-product-requirements.md
docs/03-system-architecture.md
docs/04-database-specification.md
docs/05-api-specification.md
docs/00-development-roadmap.md
```

For the current task, it should also read:
- `docs/07-testing-strategy.md`
- relevant existing source files

## 3. One Phase at a Time

The user must explicitly identify the phase.

Example:

```text
Implement Phase 1 only.
```

OpenCode must not continue automatically to Phase 2.

## 4. Before Coding

OpenCode should:
1. Inspect the existing project.
2. Identify what is already implemented.
3. Compare it against the requested phase.
4. Identify files that need creation/change.
5. Explain the implementation plan briefly.
6. Implement only the approved scope.

## 5. Do Not Rewrite Working Code Unnecessarily

If existing code works:
- Reuse it.
- Extend it.
- Avoid unnecessary restructuring.
- Do not replace working architecture without a reason.

## 6. Database Rules

Whenever database models change:
1. Update SQLAlchemy models.
2. Generate/update Alembic migration.
3. Review migration.
4. Test migration.
5. Update database documentation if required.

Never edit the production database manually.

## 7. API Rules

Every new endpoint must have:
- Authentication decision
- Authorization decision
- Request schema
- Response schema
- Validation
- Error handling
- Test coverage

## 8. Security Rules

Never:
- Hard-code passwords
- Hard-code JWT secrets
- Commit `.env`
- Return password hashes
- Trust user role values from request bodies
- Allow operators to update arbitrary buses
- Expose database credentials

## 9. Location Rules

Location is sensitive operational information.

The backend must:
- Validate coordinates
- Associate updates with authenticated operators/trips
- Store timestamps
- Mark stale information
- Avoid exposing unnecessary historical location information

Do not claim a bus is currently at a location when the latest data is stale.

## 10. Analytics Rules

Analytics should use aggregated information where possible.

Do not expose individual commuter identity in management dashboards unless a separate requirement explicitly needs it.

## 11. Error Handling

Use controlled application errors.

Do not expose:
- Stack traces
- SQL statements
- Secrets
- Internal file paths

## 12. Testing Before Completion

After implementation:

```text
Run tests
   |
Fix failures
   |
Run lint/format checks
   |
Review changed files
   |
Update documentation
```

Do not declare a phase complete if tests are failing.

## 13. Documentation Rule

When implementation decisions change:
- Update the appropriate `.md` file.
- Keep documentation consistent with actual code.

## 14. Git Rule

After a successful phase, create a focused commit.

Example:

```text
feat: implement authentication and role authorization
```

Do not mix unrelated features into one phase commit.

## 15. Output Rule

At the end of each OpenCode task, report:

```text
Implemented:
- ...

Files changed:
- ...

Tests:
- ...

Migration:
- ...

Known limitations:
- ...

Next phase:
- ...
```

Do not start the next phase automatically.
