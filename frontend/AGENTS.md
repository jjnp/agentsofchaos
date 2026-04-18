## Project Configuration

- **Language**: TypeScript
- **Package Manager**: bun
- **Add-ons**: prettier, eslint, vitest, playwright, tailwindcss, mcp

## Local Working Standards

- Prefer TDD and use Vitest where appropriate.
- Implement only the minimal code needed.
- Use strict, narrow, mostly non-nullable TypeScript types.
- Use `valibot` schemas for important data models and derive types from them where appropriate.
- Use branded types for IDs and similar opaque values.
- Reuse existing components whenever possible.
- If an existing component could be extended instead of creating a new one, ask when in doubt.
- Write idiomatic Svelte code.
- The frontend generally uses Tailwind CSS, but not exclusively; use focused custom CSS when it is the clearer or more maintainable choice.
- Run linting, checks, and tests before finishing or committing.
- For staged frontend changes, prefer `bun run staged:verify` for fast validation and `bun run verify:quick` for fast validation plus `svelte-check`.
- Never commit code with failing tests, linting errors, type errors, or other failing checks.

---

Pi can use the Svelte MCP server, which provides comprehensive Svelte 5 and SvelteKit documentation.

## Available Svelte MCP Tools

### 1. `list-sections`

Use this first to discover all available documentation sections. It returns a structured list with titles, `use_cases`, and paths.

When asked about Svelte or SvelteKit topics, always start by calling this tool to find relevant sections.

### 2. `get-documentation`

Retrieves full documentation content for specific sections. Accepts one or multiple sections.

After calling `list-sections`, analyze the returned sections, especially the `use_cases` field, and then fetch all documentation sections relevant to the user's task.

### 3. `svelte-autofixer`

Analyzes Svelte code and returns issues and suggestions.

Use this whenever writing Svelte code before presenting the result. Keep calling it until it returns no issues or suggestions.

### 4. `playground-link`

Generates a Svelte Playground link with the provided code.

After completing code, ask the user whether they want a playground link. Only call this tool after user confirmation, and never if code was written directly to files in the project.
