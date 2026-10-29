# CLAUDE.md

@AGENTS.md

## Claude-specific notes
- Start every session with `git pull --rebase`, then read the task you were given. If the task touches contracts (`backend/domain/models.py`), the state machine or the ledger, stop and ask the human to confirm with the tech lead (Alex).
- Run `python dev.py check` before you tell the human you are done. Report the test count and the eval headline (false accepts must be 0).
- Prefer small diffs inside your track's files (see the map in AGENTS.md). Don't reformat files you didn't change.
- When you add behaviour, add the test first or in the same change; security behaviour needs a deny-path test that asserts zero MCP invocations.
- Use the Bedrock adapter only through `LLM.complete(...)`. Don't send `temperature` to Claude Haiku 5.5 (it returns HTTP 400). Model IDs need the `us.`/`eu.` prefix.
- Never print or write the Bedrock key. It lives only in `.env` (gitignored).
- At the end, propose a commit message `<task-id>: <what changed>` and a 3–5 line note for the team.
