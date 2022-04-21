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
import stat
import subprocess
import sys
import binascii
import struct
import json
from subprocess import Popen, PIPE


def cmd_lines(*args, **kwarg):
    lines = Popen(*args, stdout=PIPE, **kwarg).stdout.readlines()
    lns = []
    for ln in lines:
        if isinstance(ln, bytes):
            ln = ln.decode('utf-8')
        ln = ln.strip()
        if len(ln) == 0:
            continue
        lns.append(ln)
    return lns


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
            ln = ln.decode('utf-8')
        ln = ln.strip()
        if '=' in ln:
            ll = ln.split('=', 2)
            res[ll[0]] = ll[1]
    return res


def _py_dos_disk_id(dev_path):
    a = open(dev_path, 'rb').read(512)
    a = a[440:444]
    a = b''.join(list(reversed(a)))
    return binascii.b2a_hex(a)


def _cmd_dos_disk_id(prog, dev_path):
    st = os.stat(prog)
    sudo = ""
    if st.st_uid != 0:
        sudo += "chown root '{}';".format(prog)
    if st.st_mode & stat.S_ISUID != stat.S_ISUID:
        sudo += "chmod u+rxs '{}';".format(prog)
    if len(sudo) > 0:
        cmd_lines(['sudo', 'sh', '-c', sudo])
    ll = cmd_lines([prog, dev_path])
    if len(ll) > 0:
        ll = ll[0]
    else:
        ll = ''
    return re.sub('^/dev/.*:[ \t]', '', ll).strip()


def dos_disk_id(dev_path):
    prog = os.path.join(os.path.dirname(__file__), 'dos_disk_id')
    if os.path.isfile(prog) and os.getuid() != 0:
        return _cmd_dos_disk_id(prog, dev_path)
    return _py_dos_disk_id(dev_path)


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
    p2 = int(part.get('ID_PART_ENTRY_OFFSET', 0))
    if not is_darwin():
        p2 = p2 * 512
    p2 = binascii.b2a_hex(struct.pack('Q', p2))
    _id = p1 + '-' + p2
    part['DOS_PART_ENTRY_UUID'] = _id


def disk_info(dev_path):
    lines = Popen("diskutil info {}|sed 's|[ \t]||g'".format(dev_path), shell=True, stdout=PIPE).stdout.readlines()
    res = {}
    for ln in lines:
        if isinstance(ln, bytes):
            ln = ln.decode('utf-8')
        ln = ln.strip()
        if ':' in ln:
            ll = ln.split(':', 2)
            res[ll[0]] = ll[1]
    # print(dev_path,res)
    # print("\n\n\n")
    res['DEVNAME'] = dev_path
    res['ID_FS_TYPE'] = res.get('Type(Bundle)', '')
    res['ID_PART_ENTRY_UUID'] = res.get('Disk/PartitionUUID', '').lower()
    res['ID_FS_LABEL'] = res.get('VolumeName', '')
    return res


def gpt_r_show(dk):
    lines = Popen("gpt -r show {} 2>/dev/null |grep part".format(dk), shell=True, stdout=PIPE).stdout.readlines()
    info = {}
    for ln in lines:
        if isinstance(ln, bytes):
            ln = ln.decode('utf-8')
        ln = ln.strip()
        ll = re.split('[ \t]+', ln, maxsplit=3)
        pf = {'ID_PART_ENTRY_OFFSET': ll[0], 'uuid': ll[-1]}
        if 'MBR' in ll[-1]:
            pf['ID_PART_TABLE_TYPE'] = 'dos'
            pf['ID_PART_TABLE_UUID'] = dos_disk_id(dk)
        if 'GPT' in ll[-1]:
            pf['ID_PART_TABLE_TYPE'] = 'gpt'
        info[dk + "s" + ll[2]] = pf
    return info


def ioreg_info():
    s = Popen("ioreg -c IOMedia -r -a", shell=True, stdout=PIPE).stdout.read()
    import xml.etree.ElementTree as ET
    tree = ET.fromstring(s)
    root = tree

    def to_object(e):
        res = {}
        k = None
        for c in e:
            if c.tag == 'key':
                k = c.text
            elif c.tag == 'integer':
                res[k] = int(c.text)
            elif c.tag == 'false':
                res[k] = False
            elif c.tag == 'true':
                res[k] = True
            elif c.tag == 'dict':
                res[k] = to_object(c)
            elif c.tag == 'array':
                res[k] = to_array(c)
            else:
                res[k] = c.text
        return res

    def to_array(e):
        res = []
        for c in e:
            if c.tag == 'dict':
                res.append(to_object(c))
            elif c.tag == 'array':
                res.append(to_array(c))
            else:
                res.append((c.tag, c.text))
        return res

    res = {}
    array = to_array(root[0])
    for a in array:
        pt = a["Content"]
        disk_id = ''
        if pt == "GUID_partition_scheme":
            pt = 'gpt'
        else:
            disk_id = dos_disk_id('/dev/' + a["BSD Name"])
            pt = 'dos'
        for ll in a.get('IORegistryEntryChildren', []):
            for d in ll.get('IORegistryEntryChildren', []):
                dk = d.get("BSD Name", None)
                if dk is None:
                    continue
                dk = '/dev/' + dk
                pf = {'ID_PART_ENTRY_OFFSET': d.get("Base", 0), 'uuid': d.get("UUID", ""), 'ID_PART_TABLE_TYPE': pt}
                if pt == 'dos':
                    pf['ID_PART_TABLE_UUID'] = disk_id
                res[dk] = pf
    json.dump(res, sys.stdout, indent=2, ensure_ascii=False)
    print("")
    return res


def get_partitions_mac():
    # disks = cmd_lines("diskutil list|grep ^/dev/|sed 's|[ \t][ \t]*(.*||g'", shell=True)
    d_inf = ioreg_info()

    lines = Popen("diskutil list|grep 'disk[0-9]*s[0-9]*'|sed 's|.*[ \t]disk|disk|g'", shell=True,
                  stdout=PIPE).stdout.readlines()
    parts = []
    for ln in lines:
        if isinstance(ln, bytes):
            ln = ln.decode('utf-8')
        ln = ln.strip()
        dev = '/dev/' + ln
        pinf = disk_info(dev)
        pinf.update(d_inf.get(dev, {}))

        pt = pinf.get('PartitionType', None)
        if pt is None or pt == 'EFI' or pt == 'Apple_partition_map' or pt == 'Apple_Boot':
            continue
        proto = pinf.get('Protocol', None)
        if proto is None or proto == 'DiskImage':
            continue
        dos_part_uuid(pinf)
        parts.append(pinf)
    return parts


def get_partitions_linux():
    lines = Popen("grep '^[ \t]*[0-9]' /proc/partitions|awk '{print $4}'", shell=True, stdout=PIPE).stdout.readlines()
    parts = []
    for ln in lines:
        if isinstance(ln, bytes):
            ln = ln.decode('utf-8')
        ln = ln.strip()
        dev = '/dev/' + ln
        info = udev_info(dev)
        fs_type = info.get('ID_FS_TYPE', None)
        if fs_type is None or not (fs_type.lower() in ('ntfs', 'fat32', 'fat', 'fat16', 'exfat', 'vfat', 'msdos')):
            # 不是Windows的文件系统的分区就暂且不管了
            continue
        pn = info.get('PARTNAME', None)
        ignore = info.get('UDISKS_IGNORE', '')
        if pn == 'EFI System Partition' or ignore == '1':
            continue
        if info.get('DEVTYPE', None) == 'partition':
            dos_part_uuid(info)
            parts.append(info)
    return parts


def is_darwin():
    return os.uname()[0] == 'Darwin'


def get_partitions():
    """
    获取分区列表
    :return:
    """
    if is_darwin():
        return get_partitions_mac()
    return get_partitions_linux()


def bytes_reverse(d):
    if sys.version_info[0] >= 3:
        return bytes(reversed(d))
    return b''.join(list(reversed(d)))


def to_part_uuid(d):
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
        p1 = bytes_reverse(p1)
        p2 = bytes_reverse(p2)
        p3 = bytes_reverse(p3)
        _id = binascii.b2a_hex(p1) + b"-" + binascii.b2a_hex(p2) + b"-" + binascii.b2a_hex(
            p3) + b"-" + binascii.b2a_hex(
            p4) + b"-" + binascii.b2a_hex(p5)
        return str(_id.decode())
    elif n == 12:
        # MBR
        p1 = bytes_reverse(d[:4])
        p2 = d[4:]
        _id = binascii.b2a_hex(p1) + b'-' + binascii.b2a_hex(p2)
        return str(_id.decode())
    return d


def get_mounted_devices_regf(rgf):
    """
    https://github.com/libyal/libregf
    :param rgf:
    :return:
    """
    import pyregf
    regf_file = pyregf.file()

    regf_file.open(rgf)

    root_key = regf_file.get_root_key()
    device = root_key.get_sub_key_by_name("MountedDevices")
    devs = {}
    for d in device.values:
        n = d.get_name()
        d = d.get_data()
        if n.endswith(":"):
            d = to_part_uuid(d)
            if isinstance(d, str):
                devs[d] = n
    regf_file.close()
    return devs


def get_mounted_devices_regfi(rgf):
    """
    http://projects.sentinelchicken.org/reglookup/
    :param rgf:
    :return:
    """
    import pyregfi
    hive = pyregfi.openHive(rgf)
    devs = {}
    for d in hive.root.subkeys['MountedDevices'].values:
        n = d.name
        d = d.fetch_data()
        if n.endswith(":"):
            d = to_part_uuid(d)
            if isinstance(d, str):
                devs[d] = n
    return devs


def get_mounted_devices_hivex(rgf):
    import hivex
    h = hivex.Hivex(rgf)
    m = None
    devs = {}
    for i in h.node_children(h.root()):
        if h.node_name(i) == 'MountedDevices':
            m = i
            break
    if m is None:
        return devs
    for i in h.node_values(m):
        n = h.value_key(i)
        _, d = h.value_value(i)
        if n.endswith(":"):
            d = to_part_uuid(d)
            if isinstance(d, str):
                devs[d] = n
    return devs


def get_mounted_devices(rgf):
    """
    读取注册表中的盘符-分区id对应表
    :param rgf: 注册表文件
    :return:
    """
    try:
        return get_mounted_devices_hivex(rgf)
    except:
        try:
            return get_mounted_devices_regfi(rgf)
        except:
            return get_mounted_devices_regf(rgf)


def find_path_by_names(path, names):
    def path_by_name(_path, _name):
        nl = _name.lower()
        if not (os.path.isdir(path) and os.access(_path, os.R_OK) and os.access(_path, os.X_OK)):
            return None
        for _n in os.listdir(_path):
            if _n.lower() == nl:  # 不区分大小写
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
    lines = Popen("df|grep ^/dev|sed 's|[ \t].*%| |g'", shell=True, stdout=PIPE).stdout.readlines()
    mps = {}
    for ln in lines:
        if isinstance(ln, bytes):
            ln = ln.decode('utf-8')
        ln = ln.strip()
        ll = re.split('[ \t]+', ln, maxsplit=1)
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


def disk_mount(dev_name):
    s = Popen("df | grep '{}[ \t][ \t]*' |sed 's|.*[ \t]/|/|g'".format(dev_name),
              shell=True,
              stdout=PIPE).stdout.read().strip()
    if len(s) > 1:
        # 已挂载，不再处理
        return
    if is_darwin():
        cmd_lines("diskutil mount '{}'".format(dev_name), stderr=subprocess.STDOUT, shell=True)
    else:
        cmd_lines("udisksctl mount -b '{}'".format(dev_name), stderr=subprocess.STDOUT, shell=True)


def get_partition_drive(mount=False):
    """
    获取分区和windows盘符的对应表
    :param mount: true 挂载所有分区后，再搜索注册表文件
    :return:
    """
    partitions = get_partitions()
    if mount:
        for p in partitions:
            disk_mount(p['DEVNAME'])
    rgf = find_windows_registry(partitions)
    if rgf is None:
        print("Can not find the Windows system")
        return []
    mount_devs = get_mounted_devices(rgf)
    # print("mount_devs: \n{}".format(mount_devs))
    # json.dump(partitions, sys.stdout, indent=2, ensure_ascii=False)
    # print("")
    # json.dump(mount_devs, sys.stdout, indent=2, ensure_ascii=False)
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
                "windows_drive": re.sub('.*\\\\', '', dn),
                "partition": p['DEVNAME'],
                'fs_label': p.get('ID_FS_LABEL', ''),
                "mount_point": p['MOUNT_POINT']
            })

    return rets


if __name__ == '__main__':
    print(get_partition_drive())
