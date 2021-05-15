#!/usr/bin/env python3

import copy
import json
import os
import requests
import sys


def main():
    """
    Reads records for a single zone from an input file and synchronizes the
    records into a remote PowerDNS server.
    The PDNS_AUTH_API_KEY must contain the API key for the X-API-Key header.

    Example:
        upsert-records.py http://dns1.example.com:8081 localhost hostvars.json example.com

    Usage:
        upsert-records.py SERVER_LOCATION SERVER_ID VARFILE ZONE_ID

    Arguments
    ---------
    SERVER_LOCATION : str
        Location where the PowerDNS API is reachable.
    SERVER_ID : str
        PowerDNS server_id.
        In the PowerDNS Authoritative Server, the server_id is always localhost.
    VARFILE : str
        Path to the file from which records are read.
    ZONE_ID : str
        PowerDNS zone_id.
        This is the domain of the zone, without trailing dot.
    """
    arg_server_location = sys.argv[1]
    arg_server_id = sys.argv[2]
    arg_varfile = sys.argv[3]
    arg_zone_id = sys.argv[4]
    arg_api_key = os.environ["PDNS_AUTH_API_KEY"]

    zone = load_json_from_filepath(arg_varfile)["pdns_auth_api_zones"][arg_zone_id]

    remote_rrsets = http_get_rrsets(arg_server_location, arg_server_id, arg_zone_id, arg_api_key)

    target_rrsets = add_heritage_records(
        patch_soa(
            make_rrsets(zone["records"], zone["defaultTTL"]),
            remote_rrsets,
            arg_zone_id,
        ),
        zone["defaultTTL"],
    )

    owned_keys = get_owned_keys_from_rrsets(remote_rrsets)

    conflicting_rrset_list = [ (key, rrset) for key, rrset in target_rrsets.items() if key in remote_rrsets and key not in owned_keys and key[1] not in ["NS", "SOA"] ]
    if len(conflicting_rrset_list) != 0:
        for key, rrset in conflicting_rrset_list:
            for record in rrset["records"]:
                print(
                    "Could not write record: {} {} {}"
                    .format(rrset["name"], rrset["type"], record["content"]),
                    file=sys.stderr,
                )
            for record in remote_rrsets[key]["records"]:
                print(
                    " Hint: Would overwrite: {} {} {}"
                    .format(rrset["name"], rrset["type"], record["content"]),
                    file=sys.stderr,
                )
        raise ValueError("Attempted to overwrite foreign-owned record(s)")

    rrset_patches = [
        {
            **rrset,
            "changetype": "REPLACE",
        }
        for key, rrset in target_rrsets.items() if normalized_rrset(rrset) not in remote_rrsets.values()
    ] + [
        {
            "name": rrset["name"],
            "type": rrset["type"],
            "changetype": "DELETE",
        }
        for key, rrset in remote_rrsets.items() if key in owned_keys and key not in target_rrsets
    ]

    if len(rrset_patches) != 0:
        http_patch_rrsets(arg_server_location, arg_server_id, arg_zone_id, arg_api_key, rrset_patches)

    print(json.dumps(rrset_patches))


def load_json_from_filepath(filepath):
    """
    Loads JSON from the file at filepath.
    """
    with open(filepath) as f:
        return json.load(f)


def http_get_rrsets(server_location, server_id, zone_id, api_key):
    """
    Gets the list of RRsets of a certain zone from a remote PowerDNS Server.

    Parameters
    ----------
    server_location : str
        See SERVER_LOCATION argument to this script.
    server_id : str
        See SERVER_ID argument to this script.
    zone_id : str
        See ZONE_ID argument to this script.
    api_key : str
        The API key for the X-API-Key header.
    """
    url = "{}/api/v1/servers/{}/zones/{}.".format(server_location, server_id, zone_id)
    headers = {"X-API-Key": api_key}
    print("GET {}".format(url), file=sys.stderr)
    rrset_list = requests.get(url, headers=headers).json()["rrsets"]
    return index_rrsets([ normalized_rrset(rrset) for rrset in rrset_list ])


def http_patch_rrsets(server_location, server_id, zone_id, api_key, rrset_patches):
    """
    Patches the list of RRsets of a certain zone on a remote PowerDNS Server.

    Parameters
    ----------
    server_location : str
        See SERVER_LOCATION argument to this script.
    server_id : str
        See SERVER_ID argument to this script.
    zone_id : str
        See ZONE_ID argument to this script.
    api_key : str
        The API key for the X-API-Key header.
    rrset_patches : list of dict
        List of RRsets where each RRset has the following form:
        https://doc.powerdns.com/authoritative/http-api/zone.html#rrset
    """
    url = "{}/api/v1/servers/{}/zones/{}.".format(server_location, server_id, zone_id)
    headers = {"X-API-Key": api_key}
    print("PATCH {}".format(url), file=sys.stderr)
    requests.patch(url, headers=headers, data=json.dumps({"rrsets": rrset_patches}))


def normalized_rrset(rrset):
    """
    Returns a copy of the given RRset with comments removed and records sorted.
    """
    normalized = copy.copy(rrset)
    if "comments" in rrset:
        del normalized["comments"]
    if "records" in normalized:
        normalized["records"].sort(key=lambda record: record["content"])
    return normalized


def make_rrsets(records, default_ttl):
    """
    Converts a dict of records into a list of RRsets as understood by the
    PowerDNS API, and returns that list.

    Parameters
    ----------
    records : dict
        Dict of records as read from the input file's "records" key.
    default_ttl : int
        Default TTL to use for RRsets where none is specified in the dict of
        records.
    """
    rrset_list = []
    for domain, records_by_type in records.items():
        for record_type, item_list in records_by_type.items():
            rrset_list.append(make_rrset(domain, record_type, item_list, default_ttl))
    return index_rrsets(rrset_list)


def make_rrset(domain, record_type, item_list, default_ttl):
    """
    Constructs and returns an RRset object as understood by the PowerDNS API.

    Parameters
    ----------
    domain : str
        "name" of the RRset.
    record_type : str
        "type" of the RRset.
    item_list : str
        List of records as described by the README.md of this Ansible role.
    default_ttl : int
        TTL to use if none is specified in the item_list.
    """
    name = domain + "." # Append trailing dot
    records = []
    ttl_from_item_list = None
    for item in item_list:
        if "c" in item:
            illegal_keys = [key for key in item.keys() if key not in ['c', 'r']]
            if len(illegal_keys) != 0:
                for key in illegal_keys:
                    print("Illegal key: {}".format(key), file=sys.stderr)
                raise ValueError("Illegal key(s) in item for RRset '{} {}'".format(name, record_type))
            record = {
                "content": item["c"],
                "disabled": False,
                **({"set-ptr": bool(item["r"])} if "r" in item else {})
            }
            records.append(record)
        elif "t" in item:
            illegal_keys = [key for key in item.keys() if key not in ['t']]
            if len(illegal_keys) != 0:
                for key in illegal_keys:
                    print("Illegal key: {}".format(key), file=sys.stderr)
                raise ValueError("Illegal key(s) in item for RRset '{} {}'".format(name, record_type))
            if ttl_from_item_list is not None:
                raise ValueError("Duplicate TTL for RRset '{} {}'".format(name, record_type))
            ttl_from_item_list = item["t"]
    return {
        "name": name,
        "type": record_type,
        "records": records,
        "ttl": int(ttl_from_item_list if ttl_from_item_list is not None else default_ttl)
    }


def index_rrsets(rrset_list):
    """
    Converts a list of RRsets into a dict of RRsets, indexed by name and type.
    """
    return { (rrset["name"], rrset["type"]): rrset for rrset in rrset_list } # map comprehension


def patch_soa(dst_rrsets, src_rrsets, zone_id):
    """
    Takes two dicts of RRsets where each dict must contain an SOA record, and
    returns a copy of the first dict.
    If the first SOA record has "AUTO" as its serial, then the serial from
    the second SOA record is injected into the returned dict.

    Parameters
    ----------
    dst_rrsets : dict
        Dict of RRsets that should be returned.
    src_rrsets : dict
        Dict of RRsets that's only used in order to read the serial of the SOA
        record, if required.
    zone_id : str
        Domain of the SOA record.
    """
    dst_soa = extract_soa(dst_rrsets, zone_id)
    src_soa = extract_soa(src_rrsets, zone_id)
    tokens = dst_soa.split(" ")
    if tokens[2] == "AUTO":
        tokens[2] = src_soa.split(" ")[2]
    result_soa = " ".join(tokens)
    result_rrsets = copy.deepcopy(dst_rrsets)
    for rrset in result_rrsets.values():
        if rrset["type"] == "SOA":
            rrset["records"][0]["content"] = result_soa
    return result_rrsets


def extract_soa(rrsets, zone_id):
    """
    Takes a dict of RRsets which must contain a SOA record, and returns its SOA
    record.

    Parameters
    ----------
    rrsets : dict
        Dict of RRsets.
    zone_id : str
        Domain of the SOA record.
    """
    name = zone_id + "."
    if (name, "SOA") not in rrsets:
        raise ValueError("Zone has no SOA RRset")
    rrset = rrsets[(name, "SOA")]
    if len(rrset["records"]) < 1:
        raise ValueError("Zone has SOA RRset with zero records")
    if len(rrset["records"]) > 1:
        raise ValueError("Zone has SOA RRset with multiple records")
    return rrset["records"][0]["content"]


def get_owned_keys_from_rrsets(rrsets):
    """
    Given a complete dict of RRsets for a zone, returns the list of keys that
    are owned by this Ansible role.
    For this purpose, a key is a pair of name and type.
    Ownership of such a key is indicated by the presence of such a record:

    _ansible-pdns-api.<name> TXT "heritage=ansible-pdns-api,type=<type>"
    """
    owned_keys = set()
    for rrset in rrsets.values():
        if rrset["type"] == "TXT":
            owned_keys.update(get_owned_keys_from_rrset(rrset))
    return owned_keys


def get_owned_keys_from_rrset(rrset):
    """
    Given an RRset of type TXT, returns the key for which it indicates
    ownership.
    See get_owned_keys_from_rrsets for more information.
    """
    if rrset["type"] != "TXT":
        raise ValueError("Can not read heritage from RRset of type {}, must be type TXT".format(rrset["type"]))
    # Get name
    name_prefix = "_ansible-pdns-api."
    if not rrset["name"].startswith(name_prefix):
        return set()
    # Own the heritage record itself:
    owned_keys = { (rrset["name"], "TXT") }
    # Own the keys referenced by the heritage record:
    name = rrset["name"][len(name_prefix):]
    record_prefix = '"heritage=ansible-pdns-api,type='
    record_suffix = '"'
    for record in rrset["records"]:
        if not record["content"].startswith(record_prefix) or not record["content"].startswith(record_suffix):
            print(
                "WARNING: Malformed heritage record: {} {} {}"
                .format(rrset["name"], rrset["type"], record["content"]),
                file=sys.stderr,
            )
        else:
            owned_type = record["content"][len(record_prefix):-len(record_suffix)]
            owned_keys.add((name, owned_type))
    return owned_keys


def add_heritage_records(rrsets, default_ttl):
    """
    Adds heritage records to a copy of the given dict of RRsets and returns
    the result.
    For each contained record of name <name> and type <type>, the added heritage
    record has the following form:

    _ansible-pdns-api.<name> TXT "heritage=ansible-pdns-api,type=<type>"

    Parameters
    ----------
    rrsets : dict
        Dict of RRsets.
    default_ttl : int
        TTL to use for the heritage records.
    """
    extended_rrsets = copy.copy(rrsets)
    for rrset in rrsets.values():
        heritage_name = "_ansible-pdns-api.{}".format(rrset["name"])
        key = (heritage_name, "TXT")
        if key not in extended_rrsets:
            extended_rrsets[key] = {
                "name": heritage_name,
                "type": "TXT",
                "records": [],
                "ttl": default_ttl,
            }
        extended_rrsets[key]["records"].append({
            "content": '"heritage=ansible-pdns-api,type={}"'.format(rrset["type"]),
            "disabled": False,
        })
    return extended_rrsets


# Execute only if run as a script.
if __name__ == "__main__":
    main()
