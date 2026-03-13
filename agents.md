
## AGENTS.md

```md
# AGENTS.md

## Project
Telegram Filter Worker — Python async CLI application using Telethon to poll Telegram channels/chats, filter matched posts, and route results to task-specific target channels/chats.

## Key Files
- SPEC.md — full project specification, read it before writing any code
- README.md — setup and usage guide
- config.yaml — task and credential configuration
- app/ — all application modules
- state/ — local runtime files (do not add database dependencies)

## Key Rules
- MVP is async-first.
- Every configured task must run as an independent asyncio worker.
- Multiple workers must run concurrently in one process.
- Each task has its own output target.
- Do not implement a database in MVP.
- Do not forward messages; always send a newly composed text message.
- Never hardcode `api_id`, `api_hash`, phone number, or any credentials.
- Use type hints throughout the project.
- Validate `config.yaml` before starting workers.
- Handle errors per source and per worker; one failure must not crash the whole app.
- Catch and respect Telethon flood wait errors.
- Avoid blocking calls such as `time.sleep()` in runtime code; use `await asyncio.sleep(...)`.
- Add concise explanatory comments/docstrings to existing and new code where they clarify module responsibilities, async flow, state handling, routing, and Telegram entity resolution.

## Stack
- Python 3.11+
- Telethon (Telegram MTProto client)
- PyYAML
- Standard library only for JSON, hashing, file I/O

## Rules
- No database in MVP; use local JSON files for state
- No forwarding messages; always send a new composed text message
- Never hardcode `api_id`, `api_hash`, or any credentials
- Use type hints in all functions
- Keep modules small and single-responsibility
- Validate `config.yaml` before starting the worker
- Handle errors per source: one bad source must not crash the whole worker
- FloodWaitError from Telethon must be caught and respected
- Worker output routing must be task-local, not global

## Commands
- Install deps: `pip install -r requirements.txt`
- Run interactive: `python main.py`
- Run task directly: `python main.py run <task_name>`
- Add task: `python main.py add-task`
- Resolve target: `python main.py resolve-target`

## Module Map
- `app/cli.py` — CLI entry, task selection, interactive prompts
- `app/config.py` — load and validate config.yaml
- `app/telegram_client.py` — Telethon client init and session handling
- `app/runner.py` — async worker lifecycle management
- `app/worker.py` — polling loop for a single task
- `app/polling.py` — fetch messages per source
- `app/filtering.py` — keyword and link matching
- `app/links.py` — URL extraction and domain matching
- `app/formatter.py` — compose outgoing message text
- `app/sender.py` — send message to task target via Telethon
- `app/state.py` — hash dedup, TTL cleanup, JSON state files
- `app/models.py` — dataclasses/TypedDicts for shared structures
- `app/logging_setup.py` — logging configuration
- `app/target_resolver.py` — load dialogs, filter only channels/groups, present candidates, and optionally assign a resolved target to a task

## Behavior Requirements
- Read text and caption
- Match case-insensitively
- MVP match rule is `keyword_hit OR link_hit`
- Copy original text into a new message
- Append matched keywords, matched links, source, original link
- Each task must declare output.mode (user or bot) and output delivery is task-local
- Bot mode sends via Bot API using output.bot_token; source reading always uses the user account
- Bot must be added to the target channel/chat with permission to post
- Deduplicate by hash of normalized text
- Deduplication is global across tasks in MVP
- Persist state in local JSON files only
- Normal mode stays concise; debug mode enables verbose diagnostic logs, including source/target resolution details
- Support running one task or all enabled tasks concurrently
- Polling is count-bounded per source using last seen message ID and a fixed per-cycle limit
- Support resolve-target discovery and optional task assignment
- In target resolver, show only channels and groups
- Save selected numeric target ID into the chosen task in `config.yaml` after optional assignment
- Keep backward compatibility with `@username` targets
- Do not treat arbitrary user-entered numeric IDs as valid resolver output unless the entity has already been resolved by Telethon through dialogs or another valid resolution path

## Out of Scope for MVP
- Docker
- pplx-api summarization
- Advanced boolean filters
- Regex filters
- Blacklist
- Database
- Multi-process execution






