# Prisma schema (deprecated)

`schema.prisma` is kept here as a historical reference of the schema that
Prisma originally `db push`-applied to the database. It is **no longer the
source of truth**.

The active schema lives in:

- `backend/app/models/` — SQLAlchemy ORM models (source of truth)
- `backend/alembic/versions/` — migration history

The Prisma client in `frontend/src/lib/prisma.ts` is currently unused at
runtime. Do not add new code that depends on it. Edit the SQLAlchemy models
and write an Alembic migration instead — see `backend/alembic/README.md`.
