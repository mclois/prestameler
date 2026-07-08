# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Prestameler is a Django app to discover ebooks and check their borrowing availability across eBiblio España (the Spanish public library network, backed by Odilo). The project is in early/scaffold stage — the Django apps described in CONTEXT.md have not been created yet.

## Commands

```bash
# Install dependencies
uv sync

# Run dev server
uv run python manage.py runserver

# Apply migrations
uv run python manage.py migrate

# Django shell
uv run python manage.py shell

# Run tests (pytest-django, once configured)
uv run pytest
uv run pytest path/to/test_file.py::test_name
```

## Architecture (target — see CONTEXT.md for full spec)

Three Django apps, each with the same layered structure:

```
app/
├── models.py         # Django ORM models (local cache)
├── dtos.py           # Pydantic v2 DTOs for inter-layer transfer
├── managers.py       # Orchestration: serve from cache or delegate to repo
└── repositories/
    ├── base.py       # ABC interface
    └── <source>.py   # Third-party API implementation
```

**Apps:**
- `books` — fetches and caches book metadata (Hardcover GraphQL API primary, OpenLibrary fallback)
- `availability` — checks ebook borrow availability across eBiblio catalogs; `AvailabilityManager` dispatches per-catalog to the right backend repo based on `Catalog.backend` (`odilo` | `web`) via an internal `_REGISTRY` (no separate `CompositeRepository`). `Copy` stores availability data (`isbn`, `borrow_url`, `available`) plus `title`/`author`/`language`/`format`/`cover_image`, scraped/read alongside availability as a diagnostic denormalization — Hardcover's edition grouping in `Book`/`Edition` is inconsistent, so these fields help spot adaptations, translations, and other mismatched editions (see #30)
- `filter` — orchestrates `BookManager` + `AvailabilityManager`; owns Django views and URL routing

**Key invariant:** Repositories are the only layer that talks to external APIs. Managers never call external APIs directly — they check the local DB cache first and only delegate to a repository on a cache miss or TTL expiry.

## Multilanguage

Two independent language axes:
- **UI language**: Django i18n (`USE_I18N = True`), default `es`. Gettext-based, ready to add more locales without architectural changes.
- **Book filter language**: free parameter passed through to external APIs as-is. No restrictions.

## availability — CompositeRepository pattern

`AvailabilityManager` only ever calls `CompositeRepository`, which fans out to the right backend per catalog:

```python
REGISTRY = { "odilo": OdiloRepository, "web": EbiblioWebRepository }
for catalog in Catalog.objects.filter(is_active=True):
    repo = REGISTRY[catalog.backend](catalog)
    copies += repo.search(isbn)
```

Repository files:
- `repositories/odilo.py` — JSON endpoint (`https://{comunidad}.ebiblio.es/api/v1/resources?isbn=...`)
- `repositories/ebiblio_web.py` — HTML scraping for catalogs without Odilo
- `repositories/composite.py` — `CompositeRepository`; the only repo the manager instantiates

## External APIs

- **Hardcover**: GraphQL, requires auth credentials (not yet configured)
- **eBiblio/Odilo**: No public docs; endpoint pattern is `https://{comunidad}.ebiblio.es/api/v1/resources?isbn=...` — confirm by inspecting DevTools Network tab

## Pending decisions (from CONTEXT.md)

- Confirm real eBiblio endpoint by inspecting network traffic
- Hardcover API credentials
- Cache backend: Redis vs database
- CSS framework for templates
- Whether to combine Hardcover + OpenLibrary or pick one
