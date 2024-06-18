from ansible.plugins.action import ActionBase
from ansible.errors import AnsibleError
from ansible import constants as C
from ansible.plugins.loader import lookup_loader

import tempfile
import os
import shutil
import subprocess


class ActionModule(ActionBase):

    TRANSFERS_FILES = True

    def __del__(self):
        if hasattr(self, "tempfile_path"):
            os.remove(self.tempfile_path)

    def _download_attachment(self, bw_item_id: str, bw_attachment_filename: str) -> str:
        # I used to use /dev/shm but the copy module copies it from /dev/shm to ~/.ansible anyways
        fd, tempfile_path = tempfile.mkstemp(dir=C.DEFAULT_LOCAL_TMP)
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
        return tempfile_path

    def run(self, tmp=None, task_vars=None):
        if task_vars is None:
            task_vars = {}

        result = super(ActionModule, self).run(tmp, task_vars)

        bw_item_name = self._task.args["item_name"]
        bw_attachment_filename = self._task.args["attachment_filename"]

        # we will overwrite this argument later
        if "src" in self._task.args:
            result["failed"] = True
            result["msg"] = 'argument "src" is forbidden!'
            return result

        # optional argument collection_id
        try:
            bw_collection_id = self._task.args["collection_id"]
        except KeyError:
            bw_collection_id = task_vars.get("default_bw_collection_id", None)
        bw_lookup_kwargs = {}
        if bw_collection_id is not None:
            bw_lookup_kwargs["collection_id"] = bw_collection_id

        bw_records = lookup_loader.get("community.general.bitwarden").run(
            [bw_item_name], task_vars, **bw_lookup_kwargs
        )

        # bw_records is a nested list
        # the first index represents each term
        # the second index represents each item that matches that term
        bw_records_flat = []
        for result_list in bw_records:
            bw_records_flat += result_list
        if len(bw_records_flat) == 0:
            result["failed"] = True
            result["msg"] = (
                f'bitwarden lookup failed with search="{bw_item_name}" and collection_id="{bw_collection_id}"'
            )
            return result
        if len(bw_records_flat) > 1:
            result["failed"] = True
            result["msg"] = (
                f'bitwarden lookup returned too many (>1) bw_records with search="{bw_item_name}" and collection_id="{bw_collection_id}"'
            )
            return result
        bw_record = bw_records_flat[0]

        try:
            self.tempfile_path = self._download_attachment(bw_record["id"], bw_attachment_filename)
            # this object's __del__ method will delete the tempfile
        except subprocess.SubprocessError as e:
            result["failed"] = True
            result["msg"] = f"Failed to download attachment.\n{e}"
            return result

        new_task = self._task.copy()
        del new_task.args["item_name"]
        del new_task.args["attachment_filename"]
        if "collection_id" in new_task.args:
            del new_task.args["collection_id"]
        new_task.args["src"] = self.tempfile_path

        # don't show secrets in TTY
        new_play_context = self._play_context.copy()
        new_play_context.diff = False

        copy_action = self._shared_loader_obj.action_loader.get(
            "unity.copy_multi_diff.copy",
            task=new_task,
            connection=self._connection,
            play_context=new_play_context,
            loader=self._loader,
            templar=self._templar,
            shared_loader_obj=self._shared_loader_obj,
        )

        result.update(copy_action.run(task_vars=task_vars))

        return result
