## Working Style

- Create small, clear commits.
- Use the `gh` CLI to create pull requests when prompted.
- Prefer TDD: write tests first when practical, use Vitest, and implement only the minimal code needed to satisfy the tests.
- Reuse existing components and utilities whenever possible.
- If an existing component might be extended instead of creating a new one, ask first when there is doubt.

## TypeScript Standards

- Make extensive, idiomatic use of TypeScript and its language features.
- Keep types strict, narrow, and typically non-nullable.
- Prefer explicit domain modeling over loose primitive types.
- Use branded types for IDs and other important opaque values.
- Use `valibot` to define schemas for important domain data and derive TypeScript types from those schemas where appropriate.

## Frontend / Svelte Standards

- Write idiomatic Svelte code.
- Build reusable components and favor composition over duplication.
- The frontend generally uses Tailwind CSS, but not exclusively; use focused custom CSS when it is the clearer or more maintainable choice.
- For Svelte work, run linting, checks, and tests before considering the task complete.
- In `frontend`, prefer `bun run staged:verify` for fast staged-file validation and `bun run verify:quick` for fast staged validation plus `svelte-check`.
- Do not commit code with failing tests, lint errors, type errors, or other failing checks.

## Quality Bar

- Keep implementations minimal and focused.
- Validate changes with the relevant test suite and project checks before committing.
