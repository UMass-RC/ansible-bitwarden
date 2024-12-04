import os
import json
import time
import fcntl
import subprocess

from ansible.errors import AnsibleError
from ansible.utils.display import Display

display = Display()

UNAME2TMPDIR = {
    "linux": "/dev/shm",
    "darwin": "~/.tmpdisk/shm",  # https://github.com/imothee/tmpdisk
}


def get_directory_ramdisk() -> str:
    """
    return the path to a directory on a ramdisk / ramfs / memory-backed filesystem
    in our case, ansible does not provide the infrastructure to share memory, so we use a file
    use RAM to avoid leaving behind artifacts on disk hardware, with automatic delete on reboot
    """
    try:
        uname = subprocess.check_output("uname", text=True).strip().lower()
    except FileNotFoundError as e:
        raise AnsibleError("unsupported operating system: `uname` command not found.") from e
    try:
        tmpdir = os.path.expanduser(UNAME2TMPDIR[uname])
    except KeyError as e:
        raise AnsibleError(f'unsupported OS: "{uname}". supported: {UNAME2TMPDIR.keys()}') from e
    if not os.path.isdir(tmpdir):
        if uname == "darwin":
            raise AnsibleError(
                f'"{tmpdir}" is not a directory! create it with [tmpdisk](https://github.com/imothee/tmpdisk)'
            )
        else:
            raise AnsibleError(f'"{tmpdir}" is not a directory!')
    return tmpdir


def cache_lambda(
    key,
    cache_basename: str,
    lambda_func,
    cache_timeout_seconds=3600,
):
    """
    run the lambda function and cache the result in memory
    if the result is cached, don't run the function

    key: unique key for the cache
    lambda_func: function that returns value for key
    cache_timeout_seconds: if the mtime of the cache is older, it will be truncated
    """
    cache_dir = get_directory_ramdisk()
    cache_path = os.path.join(cache_dir, cache_basename)
    try:
        if not os.path.exists(cache_path):
            open(cache_path, "w").close()
        if (time.time() - os.path.getmtime(cache_path)) > cache_timeout_seconds:
            display.v(f"({key}) cache timed out, truncating...")
            open(cache_path, "w").close()
        os.chmod(cache_path, 0o600)
        cache_fd = open(cache_path, "r+")  # read and write but don't truncate
    except OSError as e:
        raise AnsibleError(e) from e
    display.v(f"({key}) acquiring lock on file '{cache_path}'...'")
    fcntl.flock(cache_fd, fcntl.LOCK_EX)
    display.v(f"({key}) lock acquired on file '{cache_path}'.'")
    try:
        try:
            cache_fd.seek(0)
            cache_contents = cache_fd.read()
            cache = json.loads(cache_contents)
        except json.JSONDecodeError as e:
            display.v(f"({key}) failed to parse cache. contents may be overwritten.\n{e}")
            display.v(cache_contents)
            cache = {}
        if key in cache:
            display.v(f"({key}) cache hit")
            return cache[key]
        display.v(f"({key}) cache miss")
        result = lambda_func()
        cache[key] = result
        cache_fd.seek(0)
        cache_fd.truncate()
        json.dump(cache, cache_fd)
        cache_fd.flush()
    finally:
        display.v(f"({key}) releasing lock on file '{cache_path}'... ")
        fcntl.flock(cache_fd, fcntl.LOCK_UN)
        cache_fd.close()
    return result
