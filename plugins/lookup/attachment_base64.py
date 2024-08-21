import tempfile
import os
import subprocess
import base64


from ansible.plugins.lookup import LookupBase
from ansible.plugins.loader import lookup_loader
from ansible.errors import AnsibleError


class LookupModule(LookupBase):
    def run(self, terms, variables=None, **kwargs):
        if not os.path.isdir("/dev/shm"):
            raise AnsibleError("error: /dev/shm is not a directory.")
        if len(terms) != 1:
            raise AnsibleError(f"exactly one posisional argument required. Given: {terms}")

        bw_item_name = terms[0]
        bw_attachment_filename = kwargs["attachment_filename"]

        bw_item_id = lookup_loader.get("unity.bitwarden.bitwarden").run(
            [bw_item_name], variables, field="id"
        )[0]

        fd, tempfile_path = tempfile.mkstemp(dir="/dev/shm")
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
