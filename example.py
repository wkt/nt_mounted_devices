#!/usr/bin/env python3
# _*_ coding: utf-8 _*_
#
#
# @File : example.py
# @Time : 2022-04-17 13:42 
# Copyright (C) 2022 WeiKeting<weikting@gmail.com>. All rights reserved.
# @Description :
#
#
import json
import sys

sys.path.append('.')

import os
import nt_mounted_devices


def test_get_partition_drive(write_drive=False):
    maps = nt_mounted_devices.get_partition_drive(mount=True)
    if write_drive:
        for m in maps:
            mp = mp['mount_point']
            txt = json.dumps(m, indent=2, ensure_ascii=False)
            f = os.path.join(mp, 'nt_mounted_device.txt')
            with open(f, 'w') as fp:
                fp.write(txt)
    json.dump(maps, sys.stdout, indent=2, ensure_ascii=False)
    print("")


def read_window_version():
    import pyregf
    regf_file = pyregf.file()

    rgf = 'SOFTWARE'
    regf_file.open(rgf)

    root_key = regf_file.get_root_key()
    path = "\\Microsoft\\Windows NT\\CurrentVersion"
    print("path:", path, len(path))
    device = root_key.get_sub_key_by_path(path)
    pn = device.get_value_by_name('ProductName')
    csd = device.get_value_by_name('CSDVersion')
    bde = device.get_value_by_name('BuildLabEx')
    bits = ''
    if 'x86' in bde.get_data_as_string():
        bits = 'x86 32 bit'
    if 'amd64' in bde.get_data_as_string():
        bits = 'x86 64 bit'
    print(pn.get_data_as_string())
    print(bde.get_data_as_string())
    print(bits)


if __name__ == '__main__':
    test_get_partition_drive()
    #read_window_version()
