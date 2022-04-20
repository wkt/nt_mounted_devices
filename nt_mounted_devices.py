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
import binascii
import struct
from subprocess import Popen, PIPE


def cmd_lines(*args,**kwarg):
    lines = Popen(*args,stdout=PIPE,**kwarg).stdout.readlines()
    lns = []
    for ln in lines:
        if isinstance(ln, bytes):
            ln = ln.decode()
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
            ln = ln.decode()
        ln = ln.strip()
        if '=' in ln:
            ll = ln.split('=', 2)
            res[ll[0]] = ll[1]
    return res


def dos_disk_id(dev_path):
	a=open(dev_path,'rb').read(512)
	a=a[440:444]
	a=b''.join(list(reversed(a)))
	return binascii.b2a_hex(a)

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
    p2 = binascii.b2a_hex(struct.pack('Q',p2))
    _id = p1 + '-' + p2
    part['DOS_PART_ENTRY_UUID'] = _id

def disk_info(dev_path):
    lines = Popen("diskutil info {}|sed 's|[ \t]||g'".format(dev_path),shell=True, stdout=PIPE).stdout.readlines()
    res = {}
    for ln in lines:
        if isinstance(ln, bytes):
            ln = ln.decode()
        ln = ln.strip()
        if ':' in ln:
            ll = ln.split(':', 2)
            res[ll[0]] = ll[1]
    #print(dev_path,res)
    #print("\n\n\n")
    res['DEVNAME']=dev_path
    res['ID_FS_TYPE']=res.get('Type(Bundle)','')
    res['ID_PART_ENTRY_UUID']=res.get('Disk/PartitionUUID','').lower()
    res['ID_FS_LABEL'] = res.get('VolumeName','')
    return res

def gpt_r_show(dk):
	lines = Popen("gpt -r show {}|grep 'part'".format(dk),shell=True, stdout=PIPE).stdout.readlines()
	info = {}
	for ln in lines:
		if isinstance(ln, bytes):
			ln = ln.decode()
		ln = ln.strip()
		ll = re.split('[ \t]+',ln,maxsplit=3)
		pf = {'ID_PART_ENTRY_OFFSET':ll[0],'uuid':ll[-1]}
		if 'MBR' in  ll[-1]:
			pf['ID_PART_TABLE_TYPE'] = 'dos'
			pf['ID_PART_TABLE_UUID'] = dos_disk_id(dk)
		if 'GPT' in ll[-1]:
			pf['ID_PART_TABLE_TYPE']='gpt'
		info[dk + "s"+ll[2]] = pf
	return info

def get_partitions_mac():
	disks = cmd_lines("diskutil list|grep ^/dev/",shell=True)
	d_inf = {}
	for d in disks:
		d_inf.update(gpt_r_show(d))
	
	lines = Popen("diskutil list|grep 'disk[0-9]*s[0-9]*'|sed 's|.*[ \t]disk|disk|g'", shell=True, stdout=PIPE).stdout.readlines()
	parts = []
	for ln in lines:
		if isinstance(ln, bytes):
			ln = ln.decode()
		ln = ln.strip()
		dev = '/dev/' + ln
		pinf = disk_info(dev)
		pinf.update(d_inf.get(dev,{}))
		pt = pinf.get('PartitionType',None)
		if pt is None or pt == 'EFI' or pt == 'Apple_partition_map' or pt == 'Apple_Boot':
			continue
		proto = pinf.get('Protocol',None)
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
            ln = ln.decode()
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


def get_partitions():
	"""
	获取分区列表
	:return:
	"""
	if os.uname()[0] == 'Darwin':
		return get_partitions_mac()
	return get_partitions_linux()


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
        p1 =  b''.join(list(reversed(p1)))
        p2 =  b''.join(list(reversed(p2)))
        p3 =  b''.join(list(reversed(p3)))
        return binascii.b2a_hex(p1) + "-" + binascii.b2a_hex(p2) + "-" + binascii.b2a_hex(p3) + "-" + binascii.b2a_hex(p4) + "-" + binascii.b2a_hex(p5)
    elif n == 12:
        # MBR
        p1 = b''.join(list(reversed(d[:4])))
        p2 = d[4:]
        return binascii.b2a_hex(p1) + '-' + binascii.b2a_hex(p2)
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
        except :
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
            ln = ln.decode()
        ln = ln.strip()
        ll = ln.split()
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
    s = Popen("df | grep '{}[ \t]\\+' |sed 's|.*[ \t]/|/|g'".format(dev_name),
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
        print("Can not find the Windows system")
        return []
    mount_devs = get_mounted_devices(rgf)
    print("mount_devs: \n{}".format(mount_devs))
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
                'fs_label': p.get('ID_FS_LABEL', ''),
                "mount_point": p['MOUNT_POINT']
            })

    return rets

if __name__ == '__main__':
	print(get_partition_drive())
