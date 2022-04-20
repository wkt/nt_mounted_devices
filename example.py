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


if __name__ == '__main__':
    test_get_partition_drive()
