import os
import json
import time
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


def process_bitwarden_lookup_results(results):
    # results is a nested list
    # the first index represents each term in terms
    # the second index represents each item that matches that term
    flat_results = []
    for result_list in results:
        flat_results += result_list
    return flat_results


class LookupModule(LookupBase):

    def run(self, terms, variables=None, **kwargs):
        if len(terms) != 1:
            raise AnsibleError(f"exactly one posisional argument required. Given: {terms}")

        if "collection_id" not in kwargs and "default_bw_collection_id" in variables:
            kwargs["collection_id"] = variables["default_bw_collection_id"]

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

        if enable_cache:
            cache_path = os.path.join(os.path.expanduser("~"), ".unity.bitwarden.bitwarden.cache")
            try:
                if not os.path.exists(cache_path):
                    display.warning(f"storing plaintext secrets in '{cache_path}'")
                    open(cache_path, "w").close()
                os.chmod(cache_path, 0o600)
                if (time.time() - os.path.getmtime(cache_path)) > cache_timeout_seconds:
                    display.v("cache timed out, truncating...")
                    open(cache_path, "w").close()
                cache_fd = open(cache_path, "r+")  # "r+" = read and write but don't truncate
            except OSError as e:
                raise AnsibleError(f"Unable to open lockfile: {e}") from e
            try:
                display.v(f"acquiring lock on file '{cache_path}'...")
                fcntl.flock(cache_fd, fcntl.LOCK_EX)
                display.v(f"lock acquired on file '{cache_path}'.")
                try:
                    cache_fd.seek(0)
                    cache_contents = cache_fd.read()
                    cache = json.loads(cache_contents)
                except json.JSONDecodeError as e:
                    display.v(f"failed to parse cache: {e}")
                    display.v(cache_contents)
                    cache = {}
                cache_key = str(terms) + str(kwargs)
                if cache_key in cache:
                    display.v(f"using cached result for key '{cache_key}'.")
                    results = cache[cache_key]
                else:
                    display.v(f"no cache found for key '{cache_key}', performing lookup.")
                    results = lookup_loader.get("community.general.bitwarden").run(
                        terms, variables, **kwargs
                    )
                    results = process_bitwarden_lookup_results(results)
                    # write result back to cache unless it's empty
                    if results:
                        cache[cache_key] = results
                        cache_fd.seek(0)
                        cache_fd.truncate()
                        json.dump(cache, cache_fd)
                        cache_fd.flush()
            finally:
                fcntl.flock(cache_fd, fcntl.LOCK_UN)
                display.v(f"lock released on file '{cache_path}'.")
        else:
            results = lookup_loader.get("community.general.bitwarden").run(
                terms, variables, **kwargs
            )
            results = process_bitwarden_lookup_results(results)
        if len(results) == 0:
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

        if len(results) > 1:
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
        return [results[0]]
