This collection adds two new lookup plugins: `unity.bitwarden.bitwarden` and `unity.bitwarden.attachment_base64`, as well as a module `unity.bitwarden.write_base64_to_file`. Both lookup plugins will fail if you try to run them in parallel. This is due to a limitation in the official Bitwarden CLI client.

There is an argument `collection_id`, but the plugins also look for the variable `bw_default_collection_id`. Both are optional.

## example usage:

plaintext:
```yml
- name: store secret binary file as a variable in base64
  ansible.builtin.set_fact:
    secret: "{{ lookup('unity.bitwarden.attachment_base64', item_name='secret', field='notes') }}"
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
    secret_b64: "{{ lookup('unity.bitwarden.attachment_base64', item_name='secret', attachment_filename='secret') }}"
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
