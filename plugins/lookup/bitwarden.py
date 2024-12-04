import hashlib

from ansible.plugins.lookup import LookupBase
from ansible.plugins.loader import lookup_loader
from ansible.errors import AnsibleError
from ansible.utils.display import Display

from ansible_collections.unity.bitwarden.plugins.plugin_utils import cache_lambda

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


def do_bitwarden_lookup(terms, variables, **kwargs):
    results = lookup_loader.get("community.general.bitwarden").run(terms, variables, **kwargs)
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
            return cache_lambda(
                hashlib.sha1((str(terms) + str(kwargs)).encode()).hexdigest()[:5],
                ".unity.bitwarden.cache",
                lambda: do_bitwarden_lookup(terms, variables, **kwargs),
                cache_timeout_seconds,
            )
        else:
            return do_bitwarden_lookup(terms, variables, **kwargs)
