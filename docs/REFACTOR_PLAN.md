# Refactoring Plan

This project is now a production-facing roleplay assistant, so the safest cleanup path is incremental. Preserve chat ingestion, character profile handling, AI response generation, and Socket.IO behavior at every step.

## Current Hotspots

- `app.py` mixes application setup, page routes, API routes, debug tools, log ingestion, and health checks.
- `nwn_roleplay_helper/chat_processing.py` mixes NWN log parsing, language tag handling, chat history, AI prompting, and translation.
- `static/js/main.js` mixes Socket.IO setup, chat rendering, AI response UI, character management, feedback, and translation.
- `templates/create_character.html` and `templates/edit_character.html` duplicate character form concerns.
- Legacy Nginx/Let's Encrypt deployment files are no longer the active server path; the current deployment uses systemd plus Caddy.

## Cleanup Already Started

- Runtime debug/operator routes are controlled by `ENABLE_DEBUG_TOOLS`.
- Unused diagram/favicon source files and legacy Nginx deployment files were moved to `docs/archive/`.
- The obsolete SVG test page was archived and its route removed.

## Safe Next Steps

1. Extract Flask routes into small modules:
   - `routes/pages.py`
   - `routes/characters.py`
   - `routes/ai.py`
   - `routes/logs.py`
   - `routes/debug.py`
2. Move `character_manager.py` into the package as `nwn_roleplay_helper/services/characters.py`.
3. Split `chat_processing.py` into focused modules:
   - `languages.py`
   - `chat_parser.py`
   - `history.py`
   - `ai_responses.py`
   - `translation.py`
4. Split `static/js/main.js` by browser responsibility:
   - `api.js`
   - `socket.js`
   - `chat.js`
   - `ai.js`
   - `characters.js`
   - `translation.js`
   - `feedback.js`
5. Introduce `templates/base.html` and shared character form partials.
6. Remove archived files only after at least one deployed release confirms no old references are needed.

## Risks To Watch

- NWN chat parsing is fragile because the game can produce subtly different line formats.
- Socket.IO diagnostics are useful while the log client is still evolving; keep debug tools available behind the flag.
- Character profile paths are user-visible data paths. Move profile code only with tests around list, load, edit, and save behavior.
- JavaScript splitting must preserve load order unless the app is converted cleanly to ES modules.
