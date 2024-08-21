# unity.bitwarden

This collection adds two new lookup plugins: `unity.bitwarden.bitwarden` and `unity.bitwarden.attachment_base64`, as well as a module `unity.bitwarden.write_base64_to_file`. These lookups are wrappers for `community.general.bitwarden`, with some restrictions to the interface:

* must receive exactly one positional argument
* must output exactly one result.

Also, they check for the variable `default_bw_collection_id` and use it as an argument to `community.general.bitwarden` if no other collection ID was provided.

## example usage:

These lookups **should not be run in parallel**! The official Bitwarden CLI client is only designed to be run one at a time. Ansible does not provide a way for the lookup logic to detect whether it is being run in parallel, or else I would make the lookup instantly fail.

plaintext:
```yml
- name: store secret as a variable
  ansible.builtin.set_fact:
    secret: "{{ lookup('unity.bitwarden.bitwarden', 'secret', field='notes') }}"
    cacheable: false
  delegate_to: localhost
  delegate_facts: true
  run_once: true

- name: install secret file
  ansible.builtin.copy:
    dest: /path/to/secretfile
    content: "{{ hostvars['localhost']['secret'] }}"
    owner: root
    group: root
    mode: "0600"
```

binary:

```yml
- name: store secret binary file as a variable in base64
  ansible.builtin.set_fact:
    secret_b64: "{{ lookup('unity.bitwarden.attachment_base64', 'secret', attachment_filename='secret') }}"
    cacheable: false
  delegate_to: localhost
  delegate_facts: true
  run_once: true

- name: install secret file
  unity.bitwarden.write_base64_to_file:
    dest: /path/to/secretfile
    content: "{{ hostvars['localhost']['secret_b64'] }}"
    owner: root
    group: root
    mode: "0600"
```
