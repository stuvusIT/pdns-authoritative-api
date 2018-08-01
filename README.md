# pdns-authoritative-api

This Ansible role managed DNS zones via the PowerDNS HTTP API.

## Requirements

Debian or Ubuntu

## Role Variables

| Name                                 | Default/Required   | Description                                         |
|--------------------------------------|:------------------:|-----------------------------------------------------|
| `pdns_auth_api_connect`              | :heavy_check_mark: | Connect to this URL (e.g. `http://127.0.0.1:1234`)  |
| `pdns_auth_api_server`               | `localhost`        | Server instance to connect to                       |
| `pdns_auth_api_key`                  | :heavy_check_mark: | API Key to use (may be empty if you don't have one) |
| `pdns_auth_api_zones`                | :heavy_check_mark: | Name-contents dict of DNS zones (see below)         |
| `pdns_auth_api_remove_unknown_zones` | `false`            | Delete zones that are not known to this role        |
| `pdns_auth_api_default_metadata`     |                    | Default metadata that can be overridden per-zone    |

### DNS Zones

| Name          | Default/Required      | Description                                                                                     |
|---------------|:---------------------:|-------------------------------------------------------------------------------------------------|
| `kind`        | `Master`              | Type of this zone (`Master`, `Slave`, or `Native`)                                              |
| `soaEdit`     | (:heavy_check_mark:)  | (not for Slave zones)  SOA-EDIT value for this zone                                             |
| `soaEditApi`  | (`{{soaEdit}}`        | (not for slave zones) SOA-EDIT-API value                                                        |
| `dnssec`      | `false`               | (not for slave zones) Enable DNSSEC and NSEC3 for this zone                                     |
| `presigned`   | `false`               | (not for slave zones) Whether the zone is presigned and does not need to be signed by PowerDNS  |
| `apiRectify`  | `true`                | (not for slave zones) Whether to automatically rectify the one on changes via the API           |
| `nsec3Param`  |                       | (not for slave zones) NSEC3PARAM record value                                                   |
| `nsec3Narrow` | `false`               | (not for slave zones) Whether to use NSEC3 in narrow mode (white lies)                          |
| `masters`     | (:heavy_check_mark:)  | List of masters of this zone                                                                    |
| `records`     | *not for Slave zones* | List with all records in this zone (see below)                                                  |
| `defaultTTL`  | (:heavy_check_mark:)  | (not for slave zones) TTL for all RRsets with no TTL explicitly set                             |
| `metadata`    |                       | Dict with the domain metadata. Items that are present in the database, but not here are removed |

### Records

This role automatically sorts records of the same name and type into RRsets.
Each record can either set a content (`c`) **or** can set a TTL which applies for the entire RRset (`t`).

Records are grouped into types which are grouped into names.
See the example below.
Unknown RRsets are removed.

If a SOA record has `AUTO` as its serial, the current value from the current zone is used.
This is helpful when setting `soaEditApi` to automatically increment the serial.

### Contents

| Name | Default/Required     | Description                                             |
|------|:--------------------:|---------------------------------------------------------|
| `c`  | (:heavy_check_mark:) | Content of this record. Must be omitted when `t` is set |
| `t`  | (:heavy_check_mark:) | TTL of this RRset. Must be omitted when `c` is set      |
| `r`  |                      | Also set the PTR record in the reverse zone             |

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
         records:
           example.com:
             SOA:
               - c: ns1.example.com admin.example.com AUTO 3600 1800 604800 600
             NS:
               - c: ns1.example.com.
               - c: ns2.example.com.
               - t: 15200
           ns1.example.com:
             A:
               - c: 10.0.0.2
                 r: True
             AAAA:
               - c: fe80::1
                 r: True
```

## License

This work is licensed under a [Creative Commons Attribution-ShareAlike 4.0 International License](https://creativecommons.org/licenses/by-sa/4.0/).

## Author Information

- [Janne Heß](https://github.com/dasJ)
