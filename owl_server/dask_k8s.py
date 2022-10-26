#!/usr/bin/env python3

import os
import sys
from functools import cache
from re import sub

import dask
import dask_kubernetes
import yaml
from dask.config import config as dask_config
from kubernetes import client, config

home = os.environ.get("HOME")


def dict_rename_key(iterable):
    if isinstance(iterable, dict):
        for key in list(iterable.keys()):
            new_key = to_camelcase(key)
            iterable[new_key] = dict_rename_key(iterable.pop(key))

    return iterable


def to_camelcase(s):
    if "_" not in s:
        return s
    s = sub(r"(_|-)+", " ", s).title().replace(" ", "").replace("*", "")
    return "".join([s[0].lower(), s[1:]])


@cache
def get_pod_spec():
    config.load_incluster_config()
    v1 = client.CoreV1Api()
    namespace = open("/var/run/secrets/kubernetes.io/serviceaccount/namespace").read()
    hostname = open("/etc/hostname").read().strip()
    pod_list = v1.list_namespaced_pod(namespace)
    this_pod = [pod for pod in pod_list.items if hostname in pod.metadata.name]
    this_pod = this_pod[0]
    return this_pod.spec


def get_command():
    spec = get_pod_spec()
    return spec.containers[0].command


def get_image():
    spec = get_pod_spec()
    return spec.containers[0].image


def get_envvars():
    spec = get_pod_spec()
    env = spec.containers[0].env
    return [{"name": e.name, "value": e.value} for e in env]


def get_volumes(vtype="config_map"):
    spec = get_pod_spec()
    volume_mounts = spec.containers[0].volume_mounts
    volumes = spec.volumes
    names = [vol.name for vol in volumes if getattr(vol, vtype)]
    vol_list = [
        {"name": vol.name, vtype: getattr(vol, vtype).to_dict()}
        for vol in volumes
        if vol.name in names
    ]
    vol_list = [dict_rename_key(v) for v in vol_list]
    vm_list = [
        {"name": vol.name, "mount_path": vol.mount_path}
        for vol in volume_mounts
        if vol.name in names
    ]
    vm_list = [dict_rename_key(v) for v in vm_list]
    return vol_list, vm_list


def save_config(config):
    res = yaml.safe_dump({"kubernetes": config})
    open(config["worker-template-path"], "w").write(res)


def update_dask_kubernetes():
    dc = dask_config["kubernetes"]
    vol1, volm1 = get_volumes("config_map")
    vol2, volm2 = get_volumes("nfs")

    for section in ["worker-template", "scheduler-template"]:
        dc[section]["spec"]["containers"][0]["env"] += get_envvars()
        dc[section]["spec"]["containers"][0]["volumeMounts"] = volm1 + volm2
        dc[section]["spec"]["volumes"] = vol1 + vol2
        dc[section]["spec"]["containers"][0]["command"] = get_command()
        dc[section]["spec"]["containers"][0]["image"] = get_image()

    # dc["worker-template-path"] = f"{home}/.config/dask/kubernetes.yaml"
    # save_config(dc)
