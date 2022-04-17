#!/usr/bin/env python3
# _*_ coding: utf-8 _*_
#
# @File : nt_mounted_devices.py
# @Time : 2022-04-16 17:48
# Copyright (C) 2022 WeiKeting<weikting@gmail.com>. All rights reserved.
# @Description :
#       在一台Ubuntu（Linux）和Windows双系统的计算机，当Ubuntu系统运行的时候，
#       此脚本可帮助用户读取各磁盘分区在Windows系统的盘符
#
#

import os
import re
import subprocess
import sys
from subprocess import Popen, PIPE

import pyregf


def udev_info(dev_path):
    """
    磁盘分区的各种参数数据
    :param dev_path:
    :return:
    """
    lines = Popen(['udevadm', 'info', '-q', 'property', dev_path], stdout=PIPE).stdout.readlines()
    res = {}
    for ln in lines:
        if isinstance(ln, bytes):
            ln = ln.decode()
        ln = ln.strip()
        if '=' in ln:
            ll = ln.split('=', 2)
            res[ll[0]] = ll[1]
    return res


def dos_part_uuid(part):
    """
    生成分区的id
    :param part:
    :return:
    """
    pt = part.get('ID_PART_TABLE_TYPE', None)
    if pt != 'dos':
        return
    p1 = part.get('ID_PART_TABLE_UUID')
    p2 = int(part.get('ID_PART_ENTRY_OFFSET', 0)) * 512
    p2 = int.to_bytes(p2, 8, byteorder='little').hex()
    _id = p1 + '-' + p2
    part['DOS_PART_ENTRY_UUID'] = _id


def get_partitions():
    """
    获取分区列表
    :return:
    """
    lines = Popen("grep '^[ \t]*[0-9]' /proc/partitions|awk '{print $4}'", shell=True, stdout=PIPE).stdout.readlines()
    parts = []
    for ln in lines:
        if isinstance(ln, bytes):
            ln = ln.decode()
        ln = ln.strip()
        dev = '/dev/' + ln
        info = udev_info(dev)
        fs_type = info.get('ID_FS_TYPE', None)
        if fs_type is None or not (fs_type.lower() in ('ntfs', 'fat32', 'fat', 'fat16', 'exfat', 'vfat', 'msdos')):
            # 不是Windows的文件系统就不管了
            continue
        pn = info.get('PARTNAME', None)
        ignore = info.get('UDISKS_IGNORE', '')
        if pn == 'EFI System Partition' or ignore == '1':
            continue
        if info.get('DEVTYPE', None) == 'partition':
            dos_part_uuid(info)
            parts.append(info)
    return parts


def to_part_uuid(d: bytes):
    """
    对注册表中的记录分区id进行转换，以方便比较
    :param d:
    :return:
    """
    n = len(d)
    if d.startswith(b'DMIO:ID:'):
        # GPT
        p1 = d[8:12]
        p2 = d[12:14]
        p3 = d[14:16]
        p4 = d[16:18]
        p5 = d[18:]
        p1 = bytes(reversed(p1))
        p2 = bytes(reversed(p2))
        p3 = bytes(reversed(p3))
        return p1.hex() + "-" + p2.hex() + "-" + p3.hex() + "-" + p4.hex() + "-" + p5.hex()
    elif n == 12:
        # MBR
        p1 = bytes(reversed(d[:4]))
        p2 = bytes(d[4:])
        return p1.hex() + '-' + p2.hex()
    return d


def get_mounted_devices(rgf):
    """
    读取注册表中的盘符-分区id对应表
    :param rgf:
    :return:
    """
    regf_file = pyregf.file()

    regf_file.open(rgf)

    root_key = regf_file.get_root_key()
    device = root_key.get_sub_key_by_name("MountedDevices")
    devs = {}
    for d in device.values:
        n: str = d.get_name()
        d = d.get_data()
        if n.endswith(":"):
            d = to_part_uuid(d)
            if isinstance(d, str):
                devs[d] = n
    regf_file.close()
    return devs


def find_path_by_names(path, names):
    def path_by_name(_path, _name):
        nl = _name.lower()
        if not (os.path.isdir(path) and os.access(_path, os.R_OK) and os.access(_path, os.X_OK)):
            return None
        for _n in os.listdir(_path):
            if _n.lower() == nl:
                return os.path.join(_path, _n)
        return None

    ret = path
    for n in names:
        ret = path_by_name(ret, n)
        if ret is None:
            return None
    return ret


def find_windows_registry(parts):
    """
    查找Windows的注册表文件
    :param parts:分区列表
    :return:
    """
    lines = Popen("grep ^/dev /proc/mounts| awk '{print $1\" \"$2}'", shell=True, stdout=PIPE).stdout.readlines()
    mps = {}
    for ln in lines:
        if isinstance(ln, bytes):
            ln = ln.decode()
        ln = ln.strip()
        ll = ln.split(' ', 2)

        mps[ll[0]] = ll[1]
    rtf = None
    for p in parts:
        dn = p['DEVNAME']
        mp = mps.get(dn, None)
        if mp is None:
            continue
        p['MOUNT_POINT'] = mp
        rgf = find_path_by_names(mp, ['Windows', 'System32', 'config', "SYSTEM"])
        if rgf is None:
            continue
        p['REGISTRY_SYSTEM'] = rgf
        if rtf is None:
            rtf = rgf
    return rtf


def udisk_mount(dev_name):
    s = Popen("udisksctl info -b '{}'|grep MountPoints|sed 's/[ \t]*MountPoints:[ \t]*//g'".format(dev_name),
              shell=True,
              stdout=PIPE).stdout.read().strip()
    if len(s) > 1:
        # 已挂载，不再处理
        return
    subprocess.run("udisksctl mount -b '{}'".format(dev_name), shell=True,
                   stdout=subprocess.DEVNULL,
                   stderr=subprocess.DEVNULL)


def get_partition_drive(mount=False):
    """
    获取分区和windows盘符的对应表
    :param mount: true 挂载所有分区后，再搜索注册表文件
    :return:
    """
    partitions = get_partitions()
    if mount:
        for p in partitions:
            udisk_mount(p['DEVNAME'])
    rgf = find_windows_registry(partitions)
    if rgf is None:
        print("Can not find the Windows system", file=sys.stderr)
        return []
    mount_devs = get_mounted_devices(rgf)
    rets = []
    for p in partitions:
        pt = p.get('ID_PART_TABLE_TYPE', None)
        if pt is None:
            continue
        u = "__"
        if pt == 'gpt':
            u = p.get('ID_PART_ENTRY_UUID')
        elif pt == 'dos':
            u = p.get('DOS_PART_ENTRY_UUID', '')
        dn = mount_devs.get(u, None)
        if dn is not None:
            rets.append({
                "drive": re.sub('.*\\\\', '', dn),
                "dev": p['DEVNAME'],
                "mount_point": p['MOUNT_POINT']
            })

    return rets
