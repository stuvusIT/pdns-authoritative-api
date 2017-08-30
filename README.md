# pdns-authoritative-api

This Ansible role managed DNS zones via the PowerDNS HTTP API.

While it could run on any other machine and access the API remotely, the API currently lacks functionality, so `pdnsutil` is invoked.
This means this role must target the PowerDNS machine.

## Requirements

Arch Linux or Ubuntu

## Role Variables

| Name                                  | Default/Required   | Description                                         |
|---------------------------------------|:------------------:|-----------------------------------------------------|
| `pdns_auth_api_connect`               | :heavy_check_mark: | Connect to this URL (e.g. `http://127.0.0.1:1234`)  |
| `pdns_auth_api_server`                | `localhost`        | Server instance to connect to                       |
| `pdns_auth_api_key`                   | :heavy_check_mark: | API Key to use (may be empty if you don't have one) |
| `pdns_auth_api_zones`                 | :heavy_check_mark: | List of DNS zones (see below)                       |
| `pdns_auth_api_remove_unknown_zones`  | `false`            | Delete zones that are not known to this role        |

### DNS Zones

| Name                 | Default/Required   | Description                                                                                                                                         |
|----------------------|:------------------:|-----------------------------------------------------------------------------------------------------------------------------------------------------|
| `name`               | :heavy_check_mark: | Name of this zone                                                                                                                                   |
| `kind`               | `Master`           | Type of this zone (`Master`, `Slave`, or `Native`)                                                                                                  |
| `soaEdit`            | `DEFAULT`          | SOA-EDIT value for this zone                                                                                                                        |
| `soaEditApi`         |                    | SOA-EDIT value when using the API. Defaults to `soaEdit`                                                                                            |
| `dnssec`             | `false`            | Enable DNSSEC and NSEC3 for this zone                                                                                                               |
| `nsec3Iterations`    | `5`                | Amount of NSEC3 iterations                                                                                                                          |
| `nsec3Salt`          | `dada`             | Salt to use when hashing for NSEC3                                                                                                                  |
| `defaultNameservers` | :heavy_check_mark: | List of NS records (for `Master` and `Native` zones), or list of masters (for `Slave` zones). This is only used when creating the zone from scratch |
| `metadata`           |                    | Dict with the domain metadata. Items that are present in the database, but not here are removed                                                     |
| `rrsets`             | :heavy_check_mark: | List with all RRsets in this zone (see below)                                                                                                       |

### RRsets

An RRset is identified by the name and the type.
If both are the same, and the TTL or the records differ, the rrset is modified.
Unknown RRsets are removed.

| Name      | Default/Required   | Description                                                       |
|-----------|:------------------:|-------------------------------------------------------------------|
| `name`    | :heavy_check_mark: | Name of this RRset                                                |
| `type`    | :heavy_check_mark: | Record type of this RRset                                         |
| `ttl`     | :heavy_check_mark: | TTL of this RRset                                                 |
| `records` | :heavy_check_mark: | List of all records in this RRset. See below for more information |

### Records

| Name       | Default/Required   | Description                                                                                                                                   |
|------------|:------------------:|-----------------------------------------------------------------------------------------------------------------------------------------------|
| `content`  | :heavy_check_mark: | Content of this record                                                                                                                        |
| `disabled` | `false`            | Whether the record is marked as disabled for PowerDNS                                                                                         |
| `set-ptr`  | `false`            | Set the matching PTR record in the reverse zone (see the PowerDNS documentation). If this RRset is not changed, the PTR record is not written |


## Example Playbook

```yml
- hosts: dns
  roles:
  - pdns-authoritative-api
     pdns_auth_api_connect: 'http://127.0.0.1:1234'
     pdns_auth_api_key: 'secretsecretkey'
     pdns_auth_api_zones:
       - name: example.com
         dnssec: true
         nsec3Salt: abab
         defaultNameservers:
           - ns1.example.com
           - ns2.example.com
         metadata:
           ALLOW-AXFR-FROM:
             - AUTO-NS
             - 2001:db8::/48
         rrsets:
           - name: example.com
             type: SOA
             ttl: 86400
             records:
               - content: "ns1.example.com admin.example.com 0 3600 1800 604800 600"
           - name: foo.example.com
             type: A
             ttl: 9600
             records:
               - content: "10.0.0.2"
                 set-ptr: true
```

## License

This work is licensed under a [Creative Commons Attribution-ShareAlike 4.0 International License](http://creativecommons.org/licenses/by-sa/4.0/).

## Author Information

- [Janne Heß](https://github.com/dasJ)
