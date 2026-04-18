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

You are able to use the Svelte MCP server, where you have access to comprehensive Svelte 5 and SvelteKit documentation. Here's how to use the available tools effectively:

## Available Svelte MCP Tools:

### 1. list-sections

Use this FIRST to discover all available documentation sections. Returns a structured list with titles, use_cases, and paths.
When asked about Svelte or SvelteKit topics, ALWAYS use this tool at the start of the chat to find relevant sections.

### 2. get-documentation

Retrieves full documentation content for specific sections. Accepts single or multiple sections.
After calling the list-sections tool, you MUST analyze the returned documentation sections (especially the use_cases field) and then use the get-documentation tool to fetch ALL documentation sections that are relevant for the user's task.

### 3. svelte-autofixer

Analyzes Svelte code and returns issues and suggestions.
You MUST use this tool whenever writing Svelte code before sending it to the user. Keep calling it until no issues or suggestions are returned.

### 4. playground-link

Generates a Svelte Playground link with the provided code.
After completing the code, ask the user if they want a playground link. Only call this tool after user confirmation and NEVER if code was written to files in their project.
