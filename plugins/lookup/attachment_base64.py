import os
import base64
import tempfile
import subprocess


from ansible.plugins.lookup import LookupBase
from ansible.plugins.loader import lookup_loader
from ansible.errors import AnsibleError

from ansible_collections.unity.bitwarden.plugins.plugin_utils import (
    cache_lambda,
    get_directory_ramdisk,
)

UNAME2TMPDIR = {
    "linux": "/dev/shm",
    "darwin": "~/.tmpdisk/shm",  # https://github.com/imothee/tmpdisk
}


def get_attachment_base64(bw_item_id, bw_attachment_filename) -> str:
    tmpdir = get_directory_ramdisk()
    fd, tempfile_path = tempfile.mkstemp(dir=tmpdir, prefix="snap.bw.")
    os.close(fd)
    os.chmod(tempfile_path, 0o600)
    subprocess.run(
        [
            "bw",
            "get",
            "attachment",
            bw_attachment_filename,
            "--itemid",
            bw_item_id,
            "--output",
            tempfile_path,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    with open(tempfile_path, "rb") as fd:
        output = base64.b64encode(fd.read()).decode("utf8")
    os.remove(tempfile_path)
    return output


class LookupModule(LookupBase):
    def run(self, terms, variables=None, **kwargs):
        if len(terms) != 1:
            raise AnsibleError(f"exactly one posisional argument required. Given: {terms}")
        bw_item_name = terms[0]

        if "attachment_filename" not in kwargs:
            raise AnsibleError(f"required keyword argument: 'attachment_filename'")
        bw_attachment_filename = kwargs["attachment_filename"]

        if "cache_timeout_seconds" in kwargs:
            cache_timeout_seconds = kwargs["cache_timeout_seconds"]
            kwargs.pop("cache_timeout_seconds")
        else:
            cache_timeout_seconds = 3600

        if "enable_cache" in kwargs:
            enable_cache = kwargs["enable_cache"]
            kwargs.pop("enable_cache")
        else:
            enable_cache = True

        kwargs.pop("attachment_filename")
        if len(kwargs) != 0:
            raise AnsibleError(f"unrecognized keyword arguments: {kwargs.keys()}")

        bw_item_id = lookup_loader.get("unity.bitwarden.bitwarden").run(
            [bw_item_name], variables, field="id"
        )[0]

        if enable_cache:
            output = cache_lambda(
                f"{bw_item_id}.{bw_attachment_filename}",
                ".unity.bitwarden.cache",
                lambda: get_attachment_base64(bw_item_id, bw_attachment_filename),
                cache_timeout_seconds,
            )
        else:
            output = get_attachment_base64(bw_item_id, bw_attachment_filename)

        # ansible requires that lookup returns a list
        return [output]
