# litestar-sqlstack Guides

Comprehensive guides for the litestar-sqlstack reference implementation (Litestar + SQLSpec + PostgreSQL).

> **Purpose**: Central documentation for patterns, best practices, and architectural decisions
> **Audience**: Developers working on litestar-sqlstack
> **Last Updated**: 2025-10-27
> **Status**: ✅ Current

## Available Guides

### Core Architecture

- **[architecture.md](architecture.md)** - System overview, component structure, data flow
- **[sqlspec-patterns.md](sqlspec-patterns.md)** - Database service patterns with SQLSpec
- **[litestar-framework.md](litestar-framework.md)** - Litestar integration patterns

### Database & Performance

- **[postgres-advanced.md](postgres-advanced.md)** - PostgreSQL optimization, indexing, advanced features
- **[named-sql-queries.md](named-sql-queries.md)** - Using named SQL query system

### Testing

- **[testing-guide.md](testing-guide.md)** - pytest patterns, fixtures, coverage

### Development

- **[development-workflow.md](development-workflow.md)** - Local development, make commands, debugging

## Guide Format

All guides follow this structure:

```markdown
# Guide Title

> **Purpose**: What this guide covers
> **Audience**: Who should read this
> **Last Updated**: YYYY-MM-DD
> **Status**: ✅ Current / 🔄 Needs Update / ⚠️ Deprecated

## Table of Contents

(for guides >200 lines)

## Content Sections

...

## Sources

- Context7: /library/name (date)
- Local guide: path/to/guide.md
- Expert research: specs/active/requirement/research/file.md

## Changelog

### YYYY-MM-DD

- Changes made

```

## Contributing to Guides

When updating guides:

1. **Read existing content** - Understand current structure
2. **Use real code examples** - From actual codebase, not hypothetical
3. **Add source attribution** - Where did information come from?
4. **Update changelog** - Document what changed
5. **NO before/after** - Describe current way only (except migration guides)
6. **Verify examples work** - Test code snippets

## Guide Lifecycle

- **✅ Current**: Up to date with latest patterns
- **🔄 Needs Update**: Contains outdated information
- **⚠️ Deprecated**: No longer applicable

## Sources

This guide system is based on patterns from:
- oracledb-vertexai-demo reference implementation
- Litestar documentation best practices
- SQLSpec project standards

## Changelog

### 2025-10-27

- Initial guides structure created
- Added README with guide format standards
- Created placeholder guides for core topics
