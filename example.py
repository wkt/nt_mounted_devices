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
import sys

sys.path.append('.')

import os
import nt_mounted_devices


def test_get_partition_drive(write_drive=False):
    maps = nt_mounted_devices.get_partition_drive(mount=True)
    for m in maps:
        mp = m["mount_point"]
        dev = m['dev']
        drive = m['drive']
        label = m['fs_label']
        txt = f"Partition = {dev}\r\nLabel = {label}\r\nWindowsDrive = {drive}\r\nMountPoint = {mp}\r\n"
        print(txt)
        if write_drive:
            f = os.path.join(mp, 'nt_mounted_device.txt')
            with open(f, 'w') as fp:
                fp.write(txt)


if __name__ == '__main__':
    test_get_partition_drive()
