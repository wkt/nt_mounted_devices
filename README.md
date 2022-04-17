# Linux读取磁盘分区的Windows盘符
对于Linux和Windows多系统的计算机，当我们运行的是Linux系统时，<br/>
如何知道各个磁盘分区在Windows系统的盘符呢？<br/>
我们的这个脚本就是解决这个问题的。<br/>
原理也比较简单：<br/>
&nbsp;&nbsp;先搜索windows的注册表文件，再使用pyregf读取注册表中盘符-分区id对应信息，<br/>
&nbsp;&nbsp;再根据分区id生成规则计算出id，然后一比对就OK了。

### 依赖
    udev
    grep
    awk
    udisks2
    python3
    pyregf (https://github.com/libyal/libregf, Ubuntu包名: python3-libregf)


### 代码示例
代码
```
import os
import nt_mounted_devices

def test_get_partition_drive(write_drive=False):
    maps = nt_mounted_devices.get_partition_drive(mount=True)
    for m in maps:
        mp = m["mount_point"]
        dev = m['dev']
        drive = m['drive']
        txt = "Device = {}\r\nMountPoint = {}\r\nWindowsDrive = {}\r\n\r\n".format(dev, mp, drive)
        print(txt)
        if write_drive:
            f = os.path.join(mp, 'nt_mounted_device.txt')
            with open(f, 'w') as fp:
                fp.write(txt)


if __name__ == '__main__':
    test_get_partition_drive()

```
运行
```
python3 example.py
```

## 运行环境
    原则上只要是满足依赖的Linux系统就可以工作
    但是实测的系统只有:
        Linux: Ubuntu 21.10, Ubuntu 18.04
        Windows: Windows 7/10


### 参考文献
https://github.com/libyal/libregf/wiki/Python-development <br/>
http://what-when-how.com/windows-forensic-analysis/registry-analysis-windows-forensic-analysis-part-6/ <br/>
https://winreg-kb.readthedocs.io/en/latest/sources/system-keys/Mounted-devices.html


