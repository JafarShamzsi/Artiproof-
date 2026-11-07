# Local schema setup

Set `DATABASE_URL_SYNC` to your dedicated local PostgreSQL database, then run
`alembic upgrade head` from backend. Never point review tests or migrations at a
shared or production database. Schema history is retained; SQLite is not a substitute.
