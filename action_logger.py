from pathlib import Path
import json
import time
import threading
import traceback
import logging
import asyncio
import inspect
from datetime import datetime, timezone
from typing import Any, Callable
from functools import wraps

# Set up logger for action_logger module
logger = logging.getLogger(__name__)

# --- Action Logging Utilities ---
class ActionLogger:
    """Append-only JSONL logger with simple rotation and thread safety."""

    def __init__(self, path: Path, max_bytes: int = 5 * 1024 * 1024, backups: int = 1):
        self.path = Path(path)
        self.max_bytes = max_bytes
        self.backups = backups
        self._lock = threading.Lock()
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _should_rotate(self) -> bool:
        try:
            return self.path.exists() and self.path.stat().st_size >= self.max_bytes
        except Exception:
            return False

    def _rotate(self):
        try:
            if not self.path.exists():
                return
            backup = self.path.with_suffix(self.path.suffix + ".1")
            if backup.exists():
                backup.unlink()
            self.path.replace(backup)
        except Exception as e:
            logger.warning("Action log rotation failed: %s", e)

    def append(self, record: dict):
        line = json.dumps(record, ensure_ascii=False)
        with self._lock:
            if self._should_rotate():
                self._rotate()
            try:
                with self.path.open("a", encoding="utf-8") as f:
                    f.write(line + "\n")
            except Exception as e:
                logger.error("Failed to write action log: %s", e)


def _truncate(value: Any, limit: int = 2000) -> Any:
    """Truncate large values to prevent log bloat."""
    try:
        s = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    except Exception:
        s = str(value)
    if len(s) > limit:
        return s[:limit] + "...<truncated>"
    return s


def make_tool_logger(action_logger: ActionLogger, server_type: str = "gnb") -> Callable:
    """Factory to create a decorator that logs tool calls to the given action_logger.

    Works with both async and sync functions. Captures args (excluding ctx),
    result/exception details, and duration in milliseconds.
    """

    def log_tool_calls(func):
        if asyncio.iscoroutinefunction(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                start = time.perf_counter()
                ts = datetime.now(timezone.utc).isoformat()
                tool_name = func.__name__
                safe_kwargs = {k: v for k, v in kwargs.items() if k != "ctx"}
                safe_args = list(args) if args else []
                entry: dict = {
                    "ts": ts,
                    "server_type": server_type,
                    "tool": tool_name,
                    "args": _truncate({"args": safe_args, "kwargs": safe_kwargs}),
                }
                try:
                    result = await func(*args, **kwargs)
                    duration_ms = int((time.perf_counter() - start) * 1000)
                    entry.update({
                        "status": "ok",
                        "duration_ms": duration_ms,
                        "result": _truncate(result),
                    })
                    return result
                except Exception as e:
                    duration_ms = int((time.perf_counter() - start) * 1000)
                    entry.update({
                        "status": "error",
                        "duration_ms": duration_ms,
                        "error": str(e),
                        "traceback": _truncate(traceback.format_exc(), 4000),
                    })
                    raise
                finally:
                    try:
                        action_logger.append(entry)
                    except Exception as log_err:
                        logger.warning("Failed to append action log entry: %s", log_err)
            
            # Preserve original signature for FastMCP tool parsing
            try:
                wrapper.__signature__ = inspect.signature(func)
            except Exception:
                pass
            return wrapper

        else:
            @wraps(func)
            def wrapper(*args, **kwargs):
                start = time.perf_counter()
                ts = datetime.now(timezone.utc).isoformat()
                tool_name = func.__name__
                safe_kwargs = {k: v for k, v in kwargs.items() if k != "ctx"}
                safe_args = list(args) if args else []
                entry = {
                    "ts": ts,
                    "server_type": server_type,
                    "tool": tool_name,
                    "args": _truncate({"args": safe_args, "kwargs": safe_kwargs}),
                }
                try:
                    result = func(*args, **kwargs)
                    duration_ms = int((time.perf_counter() - start) * 1000)
                    entry.update({
                        "status": "ok",
                        "duration_ms": duration_ms,
                        "result": _truncate(result),
                    })
                    return result
                except Exception as e:
                    duration_ms = int((time.perf_counter() - start) * 1000)
                    entry.update({
                        "status": "error",
                        "duration_ms": duration_ms,
                        "error": str(e),
                        "traceback": _truncate(traceback.format_exc(), 4000),
                    })
                    raise
                finally:
                    try:
                        action_logger.append(entry)
                    except Exception as log_err:
                        logger.warning("Failed to append action log entry: %s", log_err)
            
            try:
                wrapper.__signature__ = inspect.signature(func)
            except Exception:
                pass
            return wrapper

    return log_tool_calls