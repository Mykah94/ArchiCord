"""Private Discord bot-token storage for ArchiCord on Windows.

Windows Credential Manager keeps a persistent user-scoped credential protected
by Windows. No token is written to application JSON, .env, logs or HTTP replies.
Legacy environment variables remain supported for existing non-Windows installs
and direct CLI launches.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import os
import re
import sys

TARGET = "ArchiCord/DiscordBotToken"
CRED_TYPE_GENERIC = 1
CRED_PERSIST_LOCAL_MACHINE = 2


class CredentialStoreUnavailable(RuntimeError):
    """The OS credential manager is unavailable to this process."""


def supported() -> bool:
    return sys.platform == "win32"


def normalize_token(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("Invalid Discord bot token")
    token = value.strip().strip('"\' ')
    if token.lower().startswith("bot "):
        token = token[4:].strip()
    if not 1 <= len(token) <= 300 or any(c.isspace() or ord(c) < 33 for c in token):
        raise ValueError("Invalid Discord bot token")
    if any(word in token.upper() for word in ("YOUR_TOKEN", "HIER_EINTRAGEN", "DEIN_TOKEN", "PLACEHOLDER")):
        raise ValueError("Enter a real Discord bot token")
    return token


class _FILETIME(ctypes.Structure):
    _fields_ = [("dwLowDateTime", wintypes.DWORD), ("dwHighDateTime", wintypes.DWORD)]


class _CREDENTIALW(ctypes.Structure):
    _fields_ = [
        ("Flags", wintypes.DWORD),
        ("Type", wintypes.DWORD),
        ("TargetName", wintypes.LPWSTR),
        ("Comment", wintypes.LPWSTR),
        ("LastWritten", _FILETIME),
        ("CredentialBlobSize", wintypes.DWORD),
        ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
        ("Persist", wintypes.DWORD),
        ("AttributeCount", wintypes.DWORD),
        ("Attributes", ctypes.c_void_p),
        ("TargetAlias", wintypes.LPWSTR),
        ("UserName", wintypes.LPWSTR),
    ]


def _api():
    if not supported():
        raise CredentialStoreUnavailable(
            "Secure token storage uses Windows Credential Manager; "
            "non-Windows installations may continue using a private .env file."
        )
    lib = ctypes.WinDLL("Advapi32.dll", use_last_error=True)
    lib.CredWriteW.argtypes = [ctypes.POINTER(_CREDENTIALW), wintypes.DWORD]
    lib.CredWriteW.restype = wintypes.BOOL
    lib.CredReadW.argtypes = [
        wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
        ctypes.POINTER(ctypes.POINTER(_CREDENTIALW)),
    ]
    lib.CredReadW.restype = wintypes.BOOL
    lib.CredFree.argtypes = [ctypes.c_void_p]
    lib.CredFree.restype = None
    return lib


def store_token(value: str) -> None:
    token = normalize_token(value)
    lib = _api()
    raw = bytearray(token.encode("utf-16-le"))
    blob = (ctypes.c_ubyte * len(raw)).from_buffer(raw)
    credential = _CREDENTIALW()
    credential.Type = CRED_TYPE_GENERIC
    credential.TargetName = TARGET
    credential.CredentialBlobSize = len(raw)
    credential.CredentialBlob = ctypes.cast(blob, ctypes.POINTER(ctypes.c_ubyte))
    credential.Persist = CRED_PERSIST_LOCAL_MACHINE
    credential.UserName = "ArchiCord"
    try:
        if not lib.CredWriteW(ctypes.byref(credential), 0):
            code = ctypes.get_last_error()
            raise CredentialStoreUnavailable(
                f"Windows Credential Manager could not save the token (error {code})."
            )
    finally:
        ctypes.memset(ctypes.addressof(blob), 0, len(raw))


def get_saved_token() -> str | None:
    if not supported():
        return None
    lib = _api()
    pointer = ctypes.POINTER(_CREDENTIALW)()
    if not lib.CredReadW(TARGET, CRED_TYPE_GENERIC, 0, ctypes.byref(pointer)):
        code = ctypes.get_last_error()
        if code == 1168:  # ERROR_NOT_FOUND
            return None
        raise CredentialStoreUnavailable(
            f"Windows Credential Manager could not read the token (error {code})."
        )
    try:
        cred = pointer.contents
        if not cred.CredentialBlobSize or cred.CredentialBlobSize > 2048:
            raise CredentialStoreUnavailable("Windows credential has an invalid size.")
        token = ctypes.string_at(cred.CredentialBlob, cred.CredentialBlobSize).decode("utf-16-le")
        return normalize_token(token)
    finally:
        lib.CredFree(pointer)


def configured() -> bool:
    return get_saved_token() is not None


def resolve_bot_token() -> str:
    """Prefer Windows Credential Manager; keep old .env/CLI compatibility."""
    saved = get_saved_token()
    if saved:
        return saved
    from_env = os.environ.get("DISCORD_TOKEN", "")
    if from_env:
        return normalize_token(from_env)
    raise SystemExit(
        "[Konfiguration] Discord bot token missing. Set it once in the "
        "local ArchiCord WebUI. On other platforms, use DISCORD_TOKEN in .env."
    )
