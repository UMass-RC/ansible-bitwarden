import os
import base64
import tempfile
import subprocess


from ansible.plugins.lookup import LookupBase
from ansible.plugins.loader import lookup_loader
from ansible.errors import AnsibleError

DOCUMENTATION = """
short_description: Retrieve attachment from Bitwarden, base64 encoded
description:
  - Uses unity.bitwarden.bitwarden to retrieve the UUID of the record.
  - Uses the `bw` CLI to download attachment on a tmpfs ramdisk.
  - Reads attachment into memory and deletes attachment.
requirements
  - linux or macOS
extends_documentation_fragment: unity.bitwarden.lookup
seealso:
  - unity.bitwarden.bitwarden
  - community.general.bitwarden
"""

RETURN = """
_raw:
  description: base64 encoded contents of the specified attachment of the specified record
  type: string
"""


DOCUMENTATION = """
    name: attachment_base64
    author:
      - Simon Leary (@simonLeary42)
    requirements:
      - linux or macOS
    short_description: fetch the base64 representation of a bitwarden attachment
    version_added: 0.1.0
    description: []
    notes: []

    options:
      _terms:
        description:
        required: true

    extends_documentation_fragment:
      - unity.bitwarden.lookup
"""

EXAMPLES = """
- name: Retrieve a private key from 1Password
  ansible.builtin.debug:
    var: lookup('community.general.onepassword_doc', 'Private key')
"""

RETURN = """
  _raw:
    description: Requested document
    type: string
"""

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
