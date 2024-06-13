This collection adds a new action plugin: `copy_attachment`. It takes a bitwarden item name, an attachment filename, and a collection ID, and passes all other arguments to `copy`. Example:

```yml
- name: copy from bitwarden attachment to /etc/secrets/secret.key
  unity.bitwarden.copy_attachment:
    item_name: secret-item
    attachment_filename: secret.key
    collection_id: foo
    dest: /etc/secrets/secret.key
    mode: "0400"
    owner: root
    group: root
```

Collection ID is optional. You can pass `collection_id` as an argument, or you can set the `default_bw_collection_id` fact.
