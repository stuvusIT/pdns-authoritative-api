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
| `pdns_auth_api_remove_unknown_zones:` | `false`            | Delete zones that are now known to this role        |

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
```

## License

This work is licensed under a [Creative Commons Attribution-ShareAlike 4.0 International License](http://creativecommons.org/licenses/by-sa/4.0/).

## Author Information

- [Janne Heß](https://github.com/dasJ)
