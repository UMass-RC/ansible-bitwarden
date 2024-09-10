import os
import base64
import tempfile
import subprocess


from ansible.plugins.lookup import LookupBase
from ansible.plugins.loader import lookup_loader
from ansible.errors import AnsibleError


UNAME2TMPDIR = {
    "linux": "/dev/shm",
    "darwin": "~/.tmpdisk/shm",  # https://github.com/imothee/tmpdisk
}


class LookupModule(LookupBase):
    def run(self, terms, variables=None, **kwargs):
        try:
            uname = subprocess.check_output("uname", text=True).strip().lower()
        except FileNotFoundError as e:
            raise AnsibleError("unsupported operating system: `uname` command not found.") from e
        try:
            tmpdir = os.path.expanduser(UNAME2TMPDIR[uname])
        except KeyError as e:
            raise AnsibleError(f'unsupported OS: "{uname}"') from e
        if uname == "darwin" and not os.path.isdir(tmpdir):
            raise AnsibleError(f'"{tmpdir}" is not a directory. https://github.com/imothee/tmpdisk')
        if len(terms) != 1:
            raise AnsibleError(f"exactly one posisional argument required. Given: {terms}")

        bw_item_name = terms[0]
        bw_attachment_filename = kwargs["attachment_filename"]

        bw_item_id = lookup_loader.get("unity.bitwarden.bitwarden").run(
            [bw_item_name], variables, field="id"
        )[0]

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
            output = base64.b64encode(fd.read())
        os.remove(tempfile_path)
        return [output]
