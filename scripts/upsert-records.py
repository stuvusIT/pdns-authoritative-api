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

    target_rrsets = patch_soa(
        make_rrsets(zone["records"], zone["defaultTTL"]),
        remote_rrsets,
        arg_zone_id,
    )

    rrset_patches = [
        {
            **rrset,
            "changetype": "REPLACE",
        }
        for key, rrset in target_rrsets.items() if rrset not in remote_rrsets.values()
    ] + [
        {
            "name": rrset["name"],
            "type": rrset["type"],
            "changetype": "DELETE",
        }
        for key, rrset in remote_rrsets.items() if key not in target_rrsets
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
    for rrset in rrset_list:
        if "comments" in rrset:
            del rrset["comments"]
    return index_rrsets(rrset_list)


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


# Execute only if run as a script.
if __name__ == "__main__":
    main()
