import os
import json
import fcntl

from ansible.plugins.lookup import LookupBase
from ansible.plugins.loader import lookup_loader
from ansible.errors import AnsibleError
from ansible.utils.display import Display

display = Display()


def make_shell_command(terms, **kwargs) -> str:
    """
    make a shell command which is equivalent to the logic of the community.general.bitwarden lookup
    purely for user debugging purposes
    """
    subcommands = ["bw sync"]
    for term in terms:
        subcommand = f"bw list items --search='{term}'"
        if "collection_id" in kwargs:
            subcommand += f" --collectionid='{kwargs['collection_id']}'"
        if "search" in kwargs:
            subcommand += f" | jq '.[] | select(.[\"{kwargs['search']}\"] == \"{term}\")'"
        if "field" in kwargs:
            subcommand += ' | jq \'.[] | {{"item[custom_fields][{x}]": .["fields"]["{x}"], "item[login][{x}]": .["login"]["{x}"], "item[{x}]": .["{x}"]}}\''.format(
                x=kwargs["field"],
            )
        subcommands.append(subcommand)
    return "; ".join(subcommands)


class LookupModule(LookupBase):

    def run(self, terms, variables=None, **kwargs):
        if len(terms) != 1:
            raise AnsibleError(f"exactly one posisional argument required. Given: {terms}")

        if "collection_id" not in kwargs and "default_bw_collection_id" in variables:
            kwargs["collection_id"] = variables["default_bw_collection_id"]

        cache_path = os.path.join(os.path.expanduser("~"), ".unity.bitwarden.bitwarden.cache")
        try:
            if not os.path.exists(cache_path):
                open(cache_path, "w").close()  # Create the file if it doesn't exist
            os.chmod(cache_path, 0o600)
            cache_fd = open(cache_path, "r+")
        except OSError as e:
            raise AnsibleError(f"Unable to open lockfile: {e}") from e
        display.v(f"Acquiring lock on file '{cache_path}'...")
        try:
            fcntl.flock(cache_fd, fcntl.LOCK_EX)
            display.v(f"Lock acquired on file '{cache_path}'.")
            cache_fd.seek(0)
            try:
                cache_contents = cache_fd.read()
                cache = json.loads(cache_contents)
            except json.JSONDecodeError as e:
                display.v(f"failed to read cache: {e}")
                display.v(cache_contents)
                cache = {}
            cache_key = str(terms) + str(kwargs)
            if cache_key in cache:
                display.v(f"Using cached result for key '{cache_key}'.")
                results = cache[cache_key]
            else:
                display.v(f"No cache found for key '{cache_key}', performing lookup.")
                results = lookup_loader.get("community.general.bitwarden").run(
                    terms, variables, **kwargs
                )
                cache[cache_key] = results
                cache_fd.seek(0)
                cache_fd.truncate()
                json.dump(cache, cache_fd)
                cache_fd.flush()
        finally:
            fcntl.flock(cache_fd, fcntl.LOCK_UN)
            display.v(f"Lock released on file '{cache_path}'.")

        # results is a nested list
        # the first index represents each term in terms
        # the second index represents each item that matches that term
        flat_results = []
        for result_list in results:
            flat_results += result_list
        if len(flat_results) == 0:
            raise AnsibleError(
                "\n".join(
                    [
                        "",
                        "no results found!",
                        'make sure that your item is in the "Ansible" bitwarden collection, or specify a different collection ID.',
                        "also make sure you run `bw sync` to get recent changes from upstream.",
                        "feel free to double check my work by using the bitwarden CLI yourself:",
                        make_shell_command(terms, **kwargs),
                    ]
                )
            )

        if len(flat_results) > 1:
            raise AnsibleError(
                "\n".join(
                    [
                        "",
                        "expected single result but multiple results found!",
                        "to use multiple results, use the `community.general.bitwarden` lookup.",
                        "feel free to double check my work by using the bitwarden CLI yourself:",
                        make_shell_command(terms, **kwargs),
                    ]
                )
            )
        # ansible requires that lookup returns a list
        return [flat_results[0]]
