# ML Lab operations runbook

Owner steps for the ML cloud-agent identity created for
[Epic #155](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/155).
This runbook is story
[#164](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/164).
Matthew runs the SQL with an admin role. Provisioning of this lab used
`ACCOUNTADMIN`. Use a session that is not itself authenticated with a
programmatic access token. Snowflake rejects `REMOVE PROGRAMMATIC ACCESS TOKEN`
in a session that authenticated with a programmatic access token.

The cloud agent does not run this runbook. Documentation work does not
connect to Snowflake. No step here raises the credit cap, attaches a network
policy, writes to PROD, or automates rotation.

Policy for the same identity is in
[`AGENTS.md`](../../AGENTS.md), the
[Cursor Cloud Agent runbook](cursor-cloud-agent.md), and
[Snowflake integration](../snowflake-integration.md).
Secret names only: `SNOWFLAKE_PAT` (Runtime Secret), `SNOWFLAKE_ACCOUNT`,
`SNOWFLAKE_USER`, `SNOWFLAKE_ROLE`, `SNOWFLAKE_WAREHOUSE`, `SNOWFLAKE_DATABASE`.
SQL below uses placeholders for the new token name, the token being removed,
and each scratch object. Do not paste a token, password, or account secret
into this file, a worksheet you save, git, an issue, or chat.

## Rotation reminder

Token `ML_CLOUD_AGENT_PAT` on user `OH_LYME_ML_AGENT_SVC` expires on
**2026-11-23**. Rotate it on or before **2026-11-16**, at least seven days
before expiry. After every later rotation, replace this paragraph with the
new token name and expiry date. Record the date only.

## PAT rotation

Do this for the reminder above, and again at least seven days before each
new expiry. The token lifetime is 30 days (`DAYS_TO_EXPIRY = 30`). Snowflake's
default of 15 days is too short for this user.

The service user is `OH_LYME_ML_AGENT_SVC` (type SERVICE). Its only role is
`OH_LYME_ML_AGENT`. Its authentication policy is
`ONE_HEALTH_LYME_GAP_ATLAS_ML_LAB.PUBLIC.ML_AGENT_PAT_AUTH`
(`NETWORK_POLICY_EVALUATION = ENFORCED_NOT_REQUIRED`, owner decision on
[#157](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/157#issuecomment-6391048205)).
Leave that policy in place. Do not set
`MINS_TO_BYPASS_NETWORK_POLICY_REQUIREMENT`. This procedure adds a second
token and removes the previous one after the context check passes.

1. Confirm the user, policy, and live token. The `SHOW` list has no secret
   column. Keep the result.

   ```sql
   SHOW PARAMETERS LIKE 'AUTHENTICATION_POLICY' IN USER OH_LYME_ML_AGENT_SVC;

   SHOW USER PROGRAMMATIC ACCESS TOKENS FOR USER OH_LYME_ML_AGENT_SVC;
   ```

   The authentication-policy value must identify
   `ONE_HEALTH_LYME_GAP_ATLAS_ML_LAB.PUBLIC.ML_AGENT_PAT_AUTH`.
   If the row shows only `ML_AGENT_PAT_AUTH`, confirm the database and schema
   are `ONE_HEALTH_LYME_GAP_ATLAS_ML_LAB.PUBLIC` before continuing.
   For the current token, expect `name` `ML_CLOUD_AGENT_PAT`, `status`
   `ACTIVE`, `role_restriction` `OH_LYME_ML_AGENT`, and `expires_at`
   2026-11-23. `mins_to_bypass_network_policy_requirement` stays 0.

2. Issue a new token. `<new_token_name>` must not be the name of a token that
   is still active. Omit `IF NOT EXISTS`. That clause finishes without
   returning a secret when the name already exists.

   ```sql
   ALTER USER IF EXISTS OH_LYME_ML_AGENT_SVC
     ADD PROGRAMMATIC ACCESS TOKEN <new_token_name>
     ROLE_RESTRICTION = 'OH_LYME_ML_AGENT'
     DAYS_TO_EXPIRY = 30
     COMMENT = 'ML cloud agent; rotate at least 7 days before expiry';
   ```

   The result includes `token_secret` once. Copy that value only into the
   Dashboard field in step 4. Confirm `token_name` is `<new_token_name>`.
   The secret is not in the `SHOW` output in the next step.

3. List the tokens again. This list does not contain the secret. Confirm both
   the previous token and `<new_token_name>` are `ACTIVE`, both have
   `role_restriction` `OH_LYME_ML_AGENT`, and the new `expires_at` is about
   30 days out. If `<new_token_name>` has an empty role restriction or any
   role other than `OH_LYME_ML_AGENT`, remove it with the statement in step 6
   (use `<new_token_name>` as `<old_token_name>`) and stop. Do not update the
   Dashboard.

   ```sql
   SHOW USER PROGRAMMATIC ACCESS TOKENS FOR USER OH_LYME_ML_AGENT_SVC;
   ```

4. Update the Cursor Dashboard secret. Open **Dashboard → Cloud Agents**,
   then the environment for this repository. Edit the Runtime Secret named
   `SNOWFLAKE_PAT` and replace its value with the new `token_secret`. Leave
   `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER`, `SNOWFLAKE_ROLE`,
   `SNOWFLAKE_WAREHOUSE`, and `SNOWFLAKE_DATABASE` as they are. Save. An
   agent that is already running keeps the previous secret. The check in the
   next step has to be a new process started after this save.

5. Verify with the context check. From a new cloud-agent run, or from a shell
   that already has the six `SNOWFLAKE_*` variables in its environment:

   ```bash
   uv sync --locked --extra dev --extra snowflake
   uv run python scripts/check_ml_agent_context.py
   ```

   A passing run exits 0 and prints:

   ```text
   role: OH_LYME_ML_AGENT
   warehouse: OH_LYME_ML_LAB_XS_WH
   database: ONE_HEALTH_LYME_GAP_ATLAS_ML_LAB
   prod_select: pass
   scratch_write: pass
   prod_write_denied: pass
   ```

   The script reads `SNOWFLAKE_PAT` and does not print it. `scratch_write`
   creates a temporary table in
   `ONE_HEALTH_LYME_GAP_ATLAS_ML_LAB.SCRATCH` and drops that table in the
   same session.

   If the exit code is not 0, or any of the three checks is not `pass`, put
   the previous secret back into Dashboard `SNOWFLAKE_PAT`, remove
   `<new_token_name>` with the statement in step 6, and leave the previous
   token in place.

6. After the check passes, revoke the previous token. For the first rotation,
   `<old_token_name>` is `ML_CLOUD_AGENT_PAT`.

   ```sql
   ALTER USER IF EXISTS OH_LYME_ML_AGENT_SVC
     REMOVE PROGRAMMATIC ACCESS TOKEN <old_token_name>;
   ```

   Run `SHOW USER PROGRAMMATIC ACCESS TOKENS FOR USER OH_LYME_ML_AGENT_SVC`
   again. One `ACTIVE` token should remain: `<new_token_name>`, restricted to
   `OH_LYME_ML_AGENT`, with the new expiry. Then update the
   [rotation reminder](#rotation-reminder) in this runbook with that name and
   date. A removed token cannot be restored. The secret from step 2 is the
   one stored in `SNOWFLAKE_PAT`.

## Monthly resource monitor review

Do this once a month. The warehouse is `OH_LYME_ML_LAB_XS_WH`: X-Small, 60
second auto-suspend, assigned to resource monitor `OH_LYME_ML_LAB_MONITOR`.
The monitor quota is 20 credits per monthly interval. Triggers from
provisioning ([#156](https://github.com/Caraway-Labs/one-health-lyme-gap-atlas-machine-learning/issues/156#issuecomment-6391047967)):
notify at 75 percent, suspend at 100 percent, suspend immediately at 110
percent.

```sql
SHOW RESOURCE MONITORS LIKE 'OH_LYME_ML_LAB_MONITOR';

SHOW WAREHOUSES LIKE 'OH_LYME_ML_LAB_XS_WH';
```

Read these fields on the monitor: `credit_quota` 20, `frequency` monthly,
`level` warehouse, `notify_at` 75, `suspend_at` 100,
`suspend_immediately_at` 110, plus `used_credits` and `remaining_credits`.
Read these fields on the warehouse: size X-Small, `auto_suspend` 60, and
`resource_monitor` `OH_LYME_ML_LAB_MONITOR`. `SHOW RESOURCE MONITORS` is the
usage figure for this review. Account-usage views lag and are not required.

Treat the review as near the cap when `used_credits` is 15 or higher (the
75 percent notify threshold) or `remaining_credits` is 5 or lower.

When the warehouse shape has drifted, put the provisioned settings back
before any further ML Lab query:

```sql
ALTER WAREHOUSE IF EXISTS OH_LYME_ML_LAB_XS_WH SET
  WAREHOUSE_SIZE = XSMALL
  AUTO_SUSPEND = 60
  RESOURCE_MONITOR = OH_LYME_ML_LAB_MONITOR;
```

When usage is near the cap, or the monitor has already suspended the
warehouse:

- Stop new cloud-agent work that queries Snowflake.
- Leave the 20 credit quota, the three triggers, and the monitor assignment
  as they are. This review does not raise the quota.
- At 100 percent the monitor suspends the warehouse after running queries
  finish. At 110 percent it suspends immediately and cancels running queries.
  A suspended warehouse stays suspended until the next monthly interval
  starts, or until a separate owner decision changes the quota or the suspend
  threshold. Resuming it without one of those changes does not hold.
- Wait for that interval when there is no separate decision. Cloud-services
  credits can still move `used_credits` a little after the warehouse suspends.
- A decision to raise the quota belongs in a recorded issue. After that
  change, confirm `OH_LYME_ML_LAB_MONITOR` is still assigned to
  `OH_LYME_ML_LAB_XS_WH` and the quota reset or increase is visible in
  `SHOW RESOURCE MONITORS`.

## SCRATCH cleanup

`ONE_HEALTH_LYME_GAP_ATLAS_ML_LAB.SCRATCH` is the transient schema for
short-lived agent objects. Review it once a month, in the same sitting as the
resource monitor. Review it sooner when objects are piling up between those
sittings. Matthew drops the old objects with an admin role. The cloud agent
does not run this cleanup. `OH_LYME_ML_AGENT` drops only the temporary probe
table inside `scripts/check_ml_agent_context.py`. Objects the agent creates
are owned by `OH_LYME_ML_AGENT` because the token role restriction owns them.
An admin role can still drop those objects.

`REGISTRY`, `EDA`, `FEATURES`, and `EXPERIMENTS` are not part of this
cleanup. Run history, metrics, and artifact rows stay there.

List object names, kinds, and created times. Do not query table contents, and
do not copy rows into git or chat.

```sql
SHOW OBJECTS IN SCHEMA ONE_HEALTH_LYME_GAP_ATLAS_ML_LAB.SCRATCH;
```

An object is old when `created_on` is 30 days ago or older. Also drop a
leftover object whose name starts with `CTX_` when `created_on` is at least
one day ago. The context check uses a session temporary table of that form
and drops it before the session ends, so a durable `CTX_` object is leftover.

Drop one named object at a time, using the kind from `SHOW OBJECTS`.
`<object_name>` is that name. Leave the schema in place.

```sql
DROP TABLE IF EXISTS ONE_HEALTH_LYME_GAP_ATLAS_ML_LAB.SCRATCH.<object_name>;
DROP VIEW IF EXISTS ONE_HEALTH_LYME_GAP_ATLAS_ML_LAB.SCRATCH.<object_name>;
DROP STAGE IF EXISTS ONE_HEALTH_LYME_GAP_ATLAS_ML_LAB.SCRATCH.<object_name>;
```

Use the one statement that matches the kind. For any other kind, stop on that
object and decide it on its own before dropping it. Run `SHOW OBJECTS` again
and confirm the dropped names are gone.

## Out of scope

Rotation stays manual. This repository does not contain a scheduler, a second
service user, or a script that calls `ADD` or `REMOVE`.
