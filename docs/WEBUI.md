# Local Web UI 🌐

Start the control panel using `START_WEBUI.bat` or `sh start_webui.sh`.

- **Bot dashboard:** `http://127.0.0.1:8765/`
- **APWorld selection:** `http://127.0.0.1:8765/apworlds`

The Web UI starts, stops and restarts the bot, edits local `.env` settings, displays live logs and lists installed APWorlds. Mutating API requests require a session CSRF token. Host headers are restricted to localhost/127.0.0.1 at the configured port.

APWorld discovery reads the `archipelago.json` manifest inside an `.apworld` ZIP. It does **not** execute the world's Python code. Selected games are saved to `tracker/settings/apworld_selection.json`. You can save without a restart, or save and restart the bot.

## Artwork

The original historical PNG artwork was missing from the accessible repository. The current repository includes **new SVG replacements** for the ArchiCord logo and background; the original HTML/CSS/JavaScript dashboard design remains otherwise unchanged.

**Security:** Never publish this local administration interface through a reverse proxy, tunnel or port-forwarding rule.
