# Security and private data 🔒

ArchiCord is intended for self-hosted community use. The Web UI is **local-only**; it is not an authenticated public administration service.

## Keep private

**Never commit or publicly upload:**

- `.env`, Discord tokens, Archipelago passwords or similar credentials.
- `archicord_data/`, `deathlinks/`, private player YAMLs, seed files and spoiler logs.
- Universal Tracker exports or third-party APWorlds without permission.

These paths are covered by `.gitignore`, but check `git status` and `git diff --cached` before every push.

## If your Discord token is exposed

1. Open the [Discord Developer Portal](https://discord.com/developers/applications).
2. Select your application, then **Bot → Reset Token**.
3. Save only the new token in your local `.env`.

Treat any published token as compromised, even if you remove it from the latest commit.

## Web UI security

The Web UI binds to `127.0.0.1` and checks Host headers and write-action CSRF tokens. It provides **no public login system**. Do not expose its port via forwarding, tunnels or reverse proxies. The status API omits stored Discord tokens and Archipelago passwords. Log redaction is defense in depth, not a guarantee that arbitrary external tool output contains no secrets.

## Universal Tracker and APWorlds

APWorlds can execute Python code when loaded by Archipelago. **Install only worlds you trust.** Scanning an APWorld manifest from the Web UI does not execute its Python code.

The optional Universal Tracker CLI may receive an Archipelago connection URI containing credentials as process arguments. Other users with sufficient local process-inspection privileges might see these arguments. Run ArchiCord on a trusted machine with an appropriately protected account.

## Report a vulnerability

Please contact the repository maintainer privately where possible. Never put secrets, credentials, seed files or private connection logs into a public GitHub issue.
