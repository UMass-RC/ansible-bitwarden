from ansible.plugins.lookup import LookupBase
from ansible.plugins.loader import lookup_loader
from ansible.errors import AnsibleError


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
        if variables == None:
            raise AnsibleError("no variables given!")
        if len(variables["ansible_play_batch"]) > 1:
            raise AnsibleError("too many hosts! use `run_once: true` or `serial: 1`.")
        if len(terms) != 1:
            raise AnsibleError(f"exactly one posisional argument required. Given: {terms}")

        if "collection_id" not in kwargs and "default_bw_collection_id" in variables:
            kwargs["collection_id"] = variables["default_bw_collection_id"]

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
