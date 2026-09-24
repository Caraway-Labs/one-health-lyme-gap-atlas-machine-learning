# Version-controlled Snowflake SQL

Place repeatable queries in `datasets/`, `features/`, `validation/`, or
`monitoring/` according to purpose. Create each directory when an approved
story has a real query for it. Governed ingestion and canonical transformations
remain in the data repository.

Each SQL file needs a stated read/write intent, approved source and target
objects, provenance, environment, and reviewable bounds. Qualify objects where
appropriate. Keep credentials and local connection identifiers outside Git.
Bind user inputs through supported parameters rather than building SQL from
untrusted strings. Review DEV versus PROD selection before execution. An SQL
file is never itself authorization to write.

The context query lives in Python as `snowflake.context.CONTEXT_SQL` because
the CLI equivalent is a single read-only statement documented in
`docs/snowflake-integration.md`; no dataset SQL is approved by Story #40.
