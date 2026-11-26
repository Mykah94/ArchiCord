# Discord bot token: permanently connected without editing .env

On **Windows**, ArchiCord now stores the Discord **bot** token in Windows Credential Manager under the current Windows user account. It is not a Discord user token, and cannot be extracted from a user login. The bot obtains its own stored token whenever it starts; the WebUI never sends the saved value back to the browser.

## First-time setup

1. Open the official [Discord Developer Portal](https://discord.com/developers/applications) and copy the **bot token** for your ArchiCord application. Do not copy your personal Discord account token.
2. Start the existing local ArchiCord WebUI and open **Bot Control** at `http://127.0.0.1:8765/`.
3. Paste the token once into **Discord-Bot-Token (einmalig einrichten oder ersetzen)** and choose **Save**, or **Save & Restart** if the bot is already running.
4. ArchiCord securely saves it to **Windows Credential Manager** (current user's persistent credential), displays only a configured indicator, and automatically reads it for every subsequent bot start. Leave `DISCORD_TOKEN=` empty in `.env`.

Changing other WebUI settings does **not** overwrite the stored bot token. An intentionally entered replacement is saved to the same user credential. Restart the bot after replacing a token to establish a new Discord session.

## Existing installations: automatic migration

On Windows, when the WebUI starts, it looks for an existing real `DISCORD_TOKEN` in the old `.env`. If found, it saves that token to Windows Credential Manager and then replaces the plaintext entry with an empty `DISCORD_TOKEN=` line, retaining unrelated configuration lines.

Migration creates **no new plaintext secret backup**. However, **older backups, previous folders, Windows file history or copies of the old `.env` may still contain the original token**. Secure or remove these copies separately. If saving to Windows Credential Manager fails, the token is not deleted from the old .env.

This storage is per Windows user. Run both the WebUI and the ArchiCord bot using the **same Windows account**. Credential Manager cannot automatically share its secrets between different accounts or computers. Copying ArchiCord to another machine requires entering the bot token again.

## Other operating systems and CLI use

Existing `DISCORD_TOKEN` environment-variable or `.env` support remains as a compatibility fallback. On non-Windows systems without a supported credential store, the WebUI continues to use the previous .env behavior. The bot prefers a Windows Credential Manager token when present, then falls back to the legacy variable.

## Security

- The bot token is never returned by `/api/status` or read settings endpoints, and it is masked in logs.
- The WebUI remains bound to `127.0.0.1` and uses its existing Origin, Host and CSRF checks on token-changing POST actions.
- The launched bot does **not** receive `DISCORD_TOKEN` in its inherited environment when Windows Credential Manager is configured.
- This is not Discord OAuth. You must still copy an official bot token **once** from the developer portal. Tokens cannot be silently pulled from Discord.
- Never paste tokens into a GitHub issue, chat message, support screenshot or repository.
