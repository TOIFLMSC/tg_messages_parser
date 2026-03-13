# SPEC.md

## 1. Project Overview

### Name
Telegram Filter Worker

### Goal
Build a Python CLI application that uses Telegram API via the user's own Telegram account to run multiple asynchronous workers in parallel. Each worker periodically polls its own set of Telegram channels/chats, filters messages by keywords and link patterns, and publishes matched results into its own target Telegram channel/chat configured per task.

### Primary Use Case
The user launches the application from the command line, selects one or more tasks from `config.yaml`, and the application starts them concurrently as asynchronous workers. Each worker continuously polls Telegram sources every N seconds, detects matching messages, deduplicates them, and sends formatted copies to that task's configured destination.

## 2. MVP Scope

The MVP must support:

- Authentication through Telegram user account using `api_id` and `api_hash`.
- Asynchronous architecture based on `asyncio`.
- Running multiple configured workers concurrently in one event loop.
- Reading messages from:
  - public channels
  - private channels
  - supergroups
  - chats where the account is a member
- Periodic polling with interval in seconds, configurable per task.
- Reading both message text and media caption.
- Case-insensitive filtering.
- OR-based filtering logic in MVP.
- Filtering by:
  - keywords
  - link patterns/domains
  - any URL present in the message
- Copying matched content into the task-specific target channel/chat as a new message.
- Appending metadata:
  - matched keywords
  - matched links
  - source title or identifier
  - original Telegram message link when available
- Deduplication by hash of normalized text.
- Local state persistence in files only, with no database.
- Task storage in `config.yaml`.
- Per-task output configuration in `config.yaml`.
- Basic CLI for task listing, creation, editing, deletion, and execution.

## 3. Out of Scope for MVP

The following are explicitly non-MVP:

- Boolean filter expressions beyond OR (`AND`, `NOT`, grouped conditions)
- Blacklist filtering
- Regex-based filtering
- LLM summarization through pplx-api
- Docker packaging
- VPS service packaging (`systemd`, supervisor, etc.)
- Web UI or REST API
- Full-text search history
- Rich media re-upload and album reconstruction
- Distributed multi-process execution

## 4. Functional Requirements

### 4.1 Authentication

- The application must authenticate via Telethon using a Telegram user account.
- The session must be stored locally using Telethon session storage.
- On first launch, the user may be prompted for phone number, code, and optionally 2FA password.

### 4.2 Async Execution Model

- The application must use one main `asyncio` event loop.
- Every configured task must run as an independent asynchronous worker.
- Workers must be scheduled concurrently, for example via `asyncio.create_task(...)`.
- One worker waiting on Telegram API or sleeping between polling cycles must not block other workers.
- The application must support graceful shutdown on Ctrl+C.
- On shutdown, pending tasks should be cancelled cleanly and the Telegram client should disconnect properly.

### 4.3 Source Support

A task may include sources in one or more of the following forms:

- public username, e.g. `@channel_name`
- numeric Telegram ID
- invite link
- entity reference resolvable by Telethon

Sources may be:

- channels
- supergroups
- private groups/channels
- chats where the account is already a member

### 4.4 Polling Model

- Each task defines `interval_seconds`.
- Each worker loops until manually stopped or cancelled.
- On each cycle, a worker polls all configured sources assigned to that task.
- It fetches recent messages using the last seen message ID (min_id) and a fixed per-source limit.
- There is no strict timestamp window; if more messages arrive between cycles than the limit allows, some older messages may be skipped.
- The app should avoid excessive overlap, but minor overlap is acceptable because deduplication exists.
- Workers may share one Telegram client instance in MVP if implemented safely in a single event loop.

### 4.5 Filter Logic

MVP logic:

```text
match = keyword_hit OR link_hit
```

Where:

- `keyword_hit` means at least one configured keyword is present in normalized text/caption.
- `link_hit` means at least one extracted URL matches at least one configured link pattern.

Matching rules:

- Case-insensitive.
- Search text includes:
  - message body
  - caption
- Blacklist is not used in MVP.

### 4.6 Link Matching

The application must detect links from:

- Telegram message entities
- plain text URL patterns in message body/caption

Pattern behavior for MVP:

- A pattern like `bestblades.ru` must match any URL pointing to that domain or its pages.
- A pattern may be treated as a case-insensitive substring/domain rule.
- All links should be considered, including Telegram links.

### 4.7 Output Behavior

Matched messages must not be forwarded.

Output delivery is per task using `tasks[].output.mode` (user or bot). Source reading always uses the logged-in user account via Telethon.

Instead, the worker sends a newly composed plain text message to the output target configured inside that task with the following structure:

1. copied original text/caption
2. blank line
3. `Matched keywords: ...`
4. `Matched links: ...`
5. `Source: ...`
6. `Original: ...`

Notes:

- If the source text is empty and there is no caption, the worker may skip the message in MVP.
- Formatting should remain plain text only in MVP.
- Message sending must be asynchronous.

### 4.8 Original Message Link

When possible, the worker must generate a link to the original Telegram message and append it to the outgoing message.

Behavior:

- For public sources, use standard public post links.
- For private chats/channels, use available Telegram deep-link/private post format when resolvable.
- If a stable link cannot be produced, write `Original: unavailable`.

### 4.9 Deduplication

- Deduplication is based on hash of normalized message text.
- Deduplication is global across tasks in MVP because workers share one hash store.
- Normalization must:
  - lowercase text
  - trim leading/trailing spaces
  - collapse repeated whitespace
- A processed message hash must be stored with timestamp.
- If the same normalized text appears again while its hash is still active, it must be skipped.

### 4.10 State Retention

- Hashes must expire after configurable TTL.
- Expired hashes must be periodically removed.
- Cleanup may run on startup and then once every fixed interval (for example every 10 minutes).
- State file writes must be safe under concurrent async workers.
- In MVP, file writes must be serialized through a shared async-safe state manager to avoid corruption.

### 4.11 Per-task Output Routing

The application must configure output routing inside each task.

Requirements:

- top-level global `output.target` must not be required
- every task must contain `output.target`
- a task may optionally contain `output.target_title`
- bot mode requires the bot to be added to the target channel/chat with permission to post
- the worker must use only its own task output target
- when running multiple tasks concurrently, each task must route matched messages independently

Example:

```yaml
tasks:
  - name: "news_scan"
    enabled: true
    interval_seconds: 1
    sources:
      - "@channel_one"
    output:
      mode: "user"
      target: "@news_target"
      target_title: "News Target"
    filters:
      mode: "or"
      keywords:
        - "vpn"
      link_patterns:
        - "bestblades.ru"
```

### 4.12 Target Resolution via CLI

The application must provide a CLI feature for resolving the numeric ID of a task target destination directly from the authenticated Telegram account.

Requirements:

- support `python main.py resolve-target`
- also expose the same action in the interactive main menu
- load dialogs available to the authenticated account
- display only candidate destinations of these types:
  - channel
  - supergroup / megagroup
  - group / chat
- do not display ordinary user dialogs in this flow by default
- allow the user to choose a candidate by number
- confirm the choice and show the numeric ID
- optionally assign the selected target to a task
- save the selected numeric ID into the chosen task in `config.yaml` as `tasks[].output.target`
- optionally save human-readable title as `tasks[].output.target_title`

#### 4.12.1 Candidate Filtering

The target resolver must show only channels and groups.

Included:

- broadcast channels
- megagroups / supergroups
- normal groups/chats if writable

Excluded by default:

- private one-to-one user chats
- service dialogs not intended as output targets

#### 4.12.2 Safe Entity Rule

The application must not treat an arbitrary numeric ID entered by the user as a valid Telegram target unless that entity has already been resolved and is known to the Telethon client.

Accepted target forms:

- `@username`
- numeric ID that has been resolved from dialogs or another valid Telethon resolution path
- invite/entity path successfully resolved by the client

Rationale:

- Telethon relies on known entities and entity cache
- target resolution should prefer dialogs visible to the authenticated account

#### 4.12.3 Config Update

After successful selection, the app must write:

```yaml
tasks:
  - name: "news_scan"
    output:
      mode: "user"
      target: 1419092328
      target_title: "My Private Channel"
```

Backward compatibility:

- existing string targets like `@my_target_channel` must continue to work

## 5. Non-Functional Requirements

- Python 3.11+
- Windows-first development experience
- Clear modular structure
- Minimal external dependencies
- No database in MVP
- Logging must be readable and practical
- Errors in one source or one worker must not stop the whole application
- The code should be suitable for later migration to VPS
- Async code must avoid blocking calls such as `time.sleep()` in worker logic

## 6. Project Structure

Recommended structure:

```text
project/
├─ main.py
├─ README.md
├─ SPEC.md
├─ AGENTS.md
├─ requirements.txt
├─ config.yaml
├─ .env.example
├─ app/
│  ├─ __init__.py
│  ├─ cli.py
│  ├─ config.py
│  ├─ telegram_client.py
│  ├─ runner.py
│  ├─ worker.py
│  ├─ polling.py
│  ├─ filtering.py
│  ├─ links.py
│  ├─ formatter.py
│  ├─ sender.py
│  ├─ state.py
│  ├─ models.py
│  ├─ logging_setup.py
│  └─ target_resolver.py
└─ state/
   ├─ processed_hashes.json
   └─ runtime.json
```

## 7. Config Design

Configuration file: `config.yaml`

Note: `output.mode` is required for every task. Older configs that omit it are invalid and must be updated.

Example schema:

```yaml
telegram:
  api_id: 123456
  api_hash: "your_api_hash"
  session_name: "tg_filter_worker"

storage:
  state_dir: "./state"
  hash_ttl_hours: 24
  cleanup_interval_minutes: 10

runtime:
  default_interactive_task_selection: true
  debug: false

tasks:
  - name: "news_scan"
    enabled: true
    interval_seconds: 1
    sources:
      - "@channel_one"
      - "@channel_two"
      - "https://t.me/+abcdef123456"
    output:
      mode: "user"
      target: "@news_target"
      target_title: "News Target"
    filters:
      mode: "or"
      keywords:
        - "vpn"
        - "санкции"
        - "telegram"
      link_patterns:
        - "bestblades.ru"
        - "github.com"

  - name: "security_scan"
    enabled: true
    interval_seconds: 3
    sources:
      - "@sec_channel"
    output:
      mode: "bot"
      bot_token: "123456:ABCDEF"
      target: -1001419092328
      target_title: "Private Security Channel"
    filters:
      mode: "or"
      keywords:
        - "cve"
        - "rce"
      link_patterns:
        - "nvd.nist.gov"
```

## 8. CLI Requirements

Supported commands:

```bash
python main.py
python main.py run <task_name>
python main.py run --all
python main.py add-task
python main.py edit-task <task_name>
python main.py delete-task <task_name>
python main.py list-tasks
python main.py resolve-target
```

### Default command behavior

Running `python main.py` with no arguments must:

- load `config.yaml`
- display existing tasks
- ask the user whether to:
  - run one task
  - run all enabled tasks concurrently
  - add a new task
  - edit a task
  - delete a task
  - resolve target
  - exit

## 9. Processing Pipeline

For each worker polling cycle:

1. Load task config.
2. Resolve source entities.
3. Fetch recent messages for each source.
4. Extract:
   - text
   - caption
   - URL entities
   - plain text URLs
5. Normalize text.
6. Evaluate keyword matches.
7. Evaluate link matches.
8. If matched:
   - build normalized hash
   - check dedup state
   - skip if already processed
   - format outgoing message
   - send to the task-specific target
   - persist processed hash
9. Run cleanup when due.
10. Await `asyncio.sleep(interval_seconds)` before the next cycle.

## 10. Concurrency Rules

- Multiple workers must run concurrently in the same process.
- A single worker should process its own sources sequentially in MVP for simplicity.
- Shared resources must be protected:
  - processed hash state
  - runtime state
  - optional shared logs if needed
- The state manager should use an `asyncio.Lock` or equivalent mechanism around file writes.
- Network calls and sleeps must always be awaited.
- The target resolver flow must remain compatible with the shared async client lifecycle.
- Concurrent workers must be able to send to different destinations without relying on global mutable output state.

## 11. Storage Design

No database in MVP.

Use only local files:

- `config.yaml` — user configuration and tasks
- Telethon session file — authentication and session persistence
- `state/processed_hashes.json` — dedup buffer
- `state/runtime.json` — last cleanup time and runtime metadata

Suggested JSON format for hash storage:

```json
{
  "items": {
    "hash1": "2026-03-12T16:00:00Z",
    "hash2": "2026-03-12T16:05:00Z"
  }
}
```

## 12. Error Handling

The application must gracefully handle:

- invalid YAML
- missing credentials
- source resolution failure
- inaccessible private source
- Telegram flood wait
- empty messages
- send failure to target
- malformed links
- session/auth errors
- cancellation during shutdown
- no eligible channel/group candidates found during target resolution
- invalid target selection input
- attempt to save unresolved arbitrary target ID
- missing task-local output configuration

Rules:

- log error
- continue processing other sources/tasks where possible
- do not crash on a single bad message
- cancellation should shut down a worker cleanly

## 13. Logging Requirements

Minimum logs:

- startup
- loaded task names
- worker start and stop
- polling cycle start and end per worker
- source fetch success and failure
- matched message detected
- target send success and failure
- dedup skip
- cleanup summary
- shutdown and task cancellation

Log style:

- concise
- timestamped
- human-readable
- include task name in every worker log line
- normal mode stays concise; debug mode enables verbose diagnostic logs including source/target resolution details

## 14. Coding Requirements

- Use type hints.
- Keep functions small and testable.
- Separate Telegram API logic from filter logic.
- Avoid hardcoded credentials.
- Validate config before worker start.
- Keep implementation simple and readable.
- All worker-facing code must be async-first.
- Avoid synchronous blocking operations in the worker runtime path.
- Add concise explanatory comments/docstrings in the existing codebase and new files so the flow of config loading, client lifecycle, worker scheduling, filtering, state writes, per-task routing, and target resolution is easy to understand.

## 15. Extension Points

Design the code so these can be added later without a major refactor:

- Advanced boolean filter expressions
- Blacklist filters
- Regex filters
- Summarization module:
  - interface like `async summarize(text: str) -> str`
  - future PPLX API integration
- Multiple fallback outputs per task
- Media handling improvements
- Docker and VPS packaging
- Per-task concurrency limits

## 16. Deliverables

Codex must generate:

- Working Python project for MVP
- All source files
- `requirements.txt`
- Example `config.yaml`
- `README.md`
- `SPEC.md`
- `AGENTS.md`

## 17. Acceptance Criteria

The MVP is accepted when:

- the app authenticates with Telegram via user account
- it can read configured public/private sources available to the account
- it can run multiple tasks concurrently as async workers
- each worker polls at its configured interval
- each task can send to its own configured target
- each task declares output.mode (user or bot)
- bot mode sends via Bot API using output.bot_token
- it matches messages by keywords and/or links
- it sends copied formatted text to target chat/channel
- it appends original message link when available
- it avoids duplicates using text hash
- it persists state locally without database
- tasks are managed through YAML and CLI
- it runs on Windows in a straightforward way
- the user can resolve a private target channel/group and optionally assign it to a task from CLI
- only channels/groups are shown in target selection
- the selected target numeric ID is saved into the chosen task config
- unresolved arbitrary numeric IDs are not treated as valid targets by the resolver flow



















