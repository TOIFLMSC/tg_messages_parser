# Telegram Filter Worker

Telegram Filter Worker is an asynchronous Python CLI application that logs into Telegram using your own account, runs one or more workers concurrently, polls messages from selected channels or chats, filters them by keywords and link patterns, and posts matched results into task-specific target Telegram channels or chats.

## Features

- Telegram user-account authentication via Telethon
- Async architecture based on `asyncio`
- Multiple workers running concurrently
- Public and private source support
- Polling every N seconds per task
- Per-task output routing
- Task-level output modes (user or bot)
- Keyword filtering
- Link/domain filtering
- Case-insensitive matching
- Copy-posting matched content to a task-specific target channel/chat
- Original message link in output
- Local file-based deduplication
- YAML task config
- Simple CLI task management
- CLI target resolver for private channels/groups

## MVP Behavior

The application does not forward source posts.

Instead, each worker creates a new text message and sends it to the output target configured inside that specific task.

Each outgoing message contains:

- Copied source text or caption
- Matched keywords
- Matched links
- Source identifier
- Original post or message link, when available

## Async Model

Each task from `config.yaml` is launched as an independent async worker in the same event loop.

This means:

- Multiple tasks can run at the same time
- Each task has its own polling interval
- Each task has its own output target
- One worker sleeping or waiting on the Telegram API does not block other workers
- The application can run a single task or all enabled tasks concurrently

## Output Modes

Each task must declare its output delivery mode in `tasks[].output.mode`.

Supported modes:

- `user` — send matched messages using the logged-in Telegram user account (current behavior)
- `bot` — send matched messages using the Telegram Bot API and a task-specific `bot_token`

Source reading always uses the logged-in user account via Telethon. Output mode affects only the final delivery step.
There is no fallback between modes, and `output.mode` is required for every task.

If you use bot mode, add the bot to the target channel/chat and grant permission to post.
## Resolving Private Target ID

If you do not know the numeric ID of a private target channel/group, the app can resolve it through the authenticated Telegram session. This resolver uses the logged-in user account.

Command:

```bash
python main.py resolve-target
```

What it does:

- Loads dialogs visible to your account
- Shows only channels and groups
- Lets you choose one by number
- Shows the selected numeric ID
- Optionally assigns the selected target to one of your tasks
- Saves the numeric ID into that task in `config.yaml`

Example saved config:

```yaml
tasks:
  - name: "news_scan"
    enabled: true
    interval_seconds: 1
    sources:
      - "@channel_one"
    output:
      mode: "user"
      target: 1419092328
      target_title: "My Private Channel"
    filters:
      mode: "or"
      keywords:
        - "vpn"
      link_patterns:
        - "bestblades.ru"
```

## Important Safety Rule

The resolver flow should only use targets that were actually seen and resolved by the Telethon client.

This means:

- `@username` targets are still allowed
- Numeric IDs selected from the resolver are allowed
- The app should not assume that an arbitrary manually typed ID is valid unless the entity has been resolved by Telegram client logic first

## Requirements

- Python 3.11+
- A Telegram account
- `api_id` and `api_hash` from Telegram
- Access to the source chats or channels
- Write permission in each task target channel or chat

## Installation

### 1. Clone the project

```bash
git clone <your-repo-url>
cd <your-repo-folder>
```

### 2. Create a virtual environment

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

Windows CMD:

```bat
python -m venv .venv
.venv\Scriptsctivate.bat
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

## Telegram Credentials

You need:

- `api_id`
- `api_hash`

Add them to `config.yaml`.

Example:

```yaml
telegram:
  api_id: 123456
  api_hash: "your_api_hash"
  session_name: "tg_filter_worker"
```

On first run, Telethon will ask for:

- Your phone number
- Login code
- 2FA password, if enabled

After successful login, the local session file will be reused.

## Configuration

Note: output.mode is required for every task. Older configs that omit it are invalid and must be updated.

Example `config.yaml`:

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

## How Filtering Works

### MVP Matching Rule

```text
message matches if keyword_hit OR link_hit
```

### Keywords

- Compared case-insensitively
- Searched in message text and caption

### Links

- Extracted from message entities and plain text
- Compared against configured patterns
- A domain-style pattern like `bestblades.ru` matches links to that site and its pages

## How Sending Works

Matched messages are not forwarded.

The app sends a new text message to the `tasks[].output.target` configured for the worker that matched the message.

The delivery backend is chosen per task:

- `user` mode sends via the logged-in Telegram user account using Telethon
- `bot` mode sends via the Telegram Bot API using `output.bot_token`

There is no fallback between modes. If `output.mode` is missing, config validation fails.
That target may be:

- `@username`
- Numeric Telegram ID
- Another resolvable Telegram destination supported by the client

Example outgoing message:

```text
<copied post text>

Matched keywords: vpn, telegram
Matched links: https://bestblades.ru/item/123
Source: @channel_one
Original: https://t.me/channel_one/12345
```

## CLI Usage

### Interactive mode

```bash
python main.py
```

Expected behavior:

- Load config
- Show existing tasks
- Ask whether to run one task, run all enabled tasks, add, edit, delete tasks, or resolve target

### Run one task

```bash
python main.py run news_scan
```

### Run all enabled tasks concurrently

```bash
python main.py run --all
```

### List tasks

```bash
python main.py list-tasks
```

### Add a task

```bash
python main.py add-task
```

### Edit a task

```bash
python main.py edit-task news_scan
```

### Delete a task

```bash
python main.py delete-task news_scan
```

### Resolve private target ID

```bash
python main.py resolve-target
```

Expected behavior:

- Authenticate or reuse the current Telethon session
- List only channels/groups visible to the account
- Ask for selection by number
- Show the selected numeric ID
- Optionally assign it to a task and save into that task in `config.yaml`

## State Files

The project stores local runtime data in files:

- Telethon session file
- `config.yaml`
- `state/processed_hashes.json`
- `state/runtime.json`

No database is used in the MVP.

Because multiple async workers may touch shared state, writes must be serialized safely in the application code.

## Deduplication

The worker avoids duplicates using a hash of normalized message text.

Deduplication is global across tasks in the MVP because all workers share the same hash store.
This means identical normalized text matched by different tasks or sources may be treated as duplicates.

Normalization includes:

- Lowercase conversion
- Trimming leading and trailing whitespace
- Collapsing repeated whitespace

Hashes are stored with timestamps and removed after TTL expiration.

## Notes About Sources

The worker can only read sources that are accessible to the logged-in account.

This means:

- Public channels are supported if resolvable
- Private chats or channels are supported if your account is already a member or can resolve them via invite access
- Inaccessible sources will be logged as errors

## Polling Behavior

Polling is count-bounded per source. Each cycle fetches recent messages using a stored `min_id`
and a fixed upper fetch limit. If more messages arrive between cycles than the limit allows,
some older messages may be skipped.

## Notes About Target Posting

Your Telegram account must be able to post to the configured target for each task. In bot mode, the bot must have permission to post in the target channel/chat.

For example:

- For your own private group where you can write, sending should work
- For a channel, your account must have permission to post
- For a private channel without public username, using the resolved numeric ID inside the task is the preferred approach after selecting it from the CLI resolver

## Graceful Shutdown

The application should stop cleanly on `Ctrl+C`.

Expected shutdown behavior:

- Cancel running workers
- Flush or finish safe state writes
- Disconnect the Telethon client
- Exit without corrupting state files

## Logging

The app should log:

- Startup
- Task selection
- Worker start and stop
- Polling cycles
- Source fetch status
- Matches
- Send results
- Deduplication skips
- Cleanup actions
- Recoverable errors
- Shutdown events

Normal mode stays concise; debug mode enables verbose diagnostic logs, including detailed source/target resolution logging. Enable it with `runtime.debug: true` in `config.yaml`.

## Testing

Install dev dependencies and run tests:

```bash
pip install -r requirements.txt -r requirements-dev.txt
pytest
```
## Future Improvements

Planned for later:

- Advanced boolean filters
- Blacklist support
- Regex filters
- PPLX API summarization
- Docker packaging
- VPS deployment guide
- Richer media handling
- Per-task concurrency tuning
- Multiple fallback outputs per task

## Development Notes for Codex

When generating code:

- Prefer simple, readable modules
- Keep Telegram logic separated from filtering logic
- Use type hints
- Validate config early
- Do not add a database
- Implement async-first runtime
- Optimize for MVP reliability, not overengineering
- Add concise comments/docstrings in current and new modules so the codebase is easier to navigate
































