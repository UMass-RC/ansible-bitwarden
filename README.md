# unity.bitwarden

This collection adds two new lookup plugins: `unity.bitwarden.bitwarden` and `unity.bitwarden.attachment_base64`, as well as a module `unity.bitwarden.write_base64_to_file`. The Bitwarden CLI `bw` is slow and cannot run in parallel. These lookups implement their own cacheing and locking so they can be fast and run in parallel.

`unity.bitwarden.bitwarden.` is a wrapper around `community.general.bitwarden.` with some restrictions to the interface:

* must receive exactly one positional argument
* must output exactly one result.

Also, they check for the variable `default_bw_collection_id` and use it as an argument to `community.general.bitwarden` if no other collection ID was provided.

## example usage:

plaintext:
```yml
- name: install secret file
  ansible.builtin.copy:
    dest: /path/to/secretfile
    content: "{{ lookup('unity.bitwarden.bitwarden', 'secret', field='notes') }}"
    owner: root
    group: root
    mode: "0600"
```

binary:

```yml
- name: install secret file
  unity.bitwarden.write_base64_to_file:
    dest: /path/to/secretfile
    content: "{{ lookup('unity.bitwarden.attachment_base64', 'secret', attachment_filename='secret') }}"
    owner: root
    group: root
    mode: "0600"
```

## requirements:
- `community.general` collection
- Bitwarden CLI Client: `bw`
- linux or macos
  - for linux: the `/dev/shm/` directory must exist
  - for macos: setup a RamDisk for secure tempfiles

        brew install tmpdisk

    - using TmpDisk, create a ramdisk called `shm` in the default location: `~/.tmpdisk/shm`.
    - [TmpDisk github](https://github.com/imothee/tmpdisk)
