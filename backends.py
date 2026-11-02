"""Pick the right client module for a host entry.

Every backend exposes the same three calls, all taking the host dict:

    list_vms(host)               -> (vms, error)   vms: [{"id","name","state"}]
    power_action(host, id, act)  -> (ok, error)
    connect(host, id, use_x11)   -> None, raises on failure

Hosts without a "type" are libvirt hosts, so hosts.json files written by
earlier versions keep working unchanged.
"""
import proxmox_client
import viewer
import virsh_client

LIBVIRT = "libvirt"
PROXMOX = "proxmox"


def host_type(host):
    return host.get("type", LIBVIRT)


def describe(host):
    """Short text shown next to the host name on its card."""
    if host_type(host) == PROXMOX:
        return host.get("url", "")
    return host.get("uri", "")


def list_vms(host):
    if host_type(host) == PROXMOX:
        return proxmox_client.list_vms(host)
    vms, error = virsh_client.list_vms(host["uri"])
    for vm in vms:
        vm["id"] = vm["name"]  # libvirt domain names are unique per URI
    return vms, error


def power_action(host, vm_id, action):
    if host_type(host) == PROXMOX:
        return proxmox_client.power_action(host, vm_id, action)
    return virsh_client.power_action(host["uri"], vm_id, action)


def connect(host, vm_id, use_x11=False):
    if host_type(host) == PROXMOX:
        proxmox_client.connect(host, vm_id, use_x11=use_x11)
    else:
        virsh_client.connect(host["uri"], vm_id, use_x11=use_x11)


def viewer_name(host):
    return viewer.name(proxmox=host_type(host) == PROXMOX)
