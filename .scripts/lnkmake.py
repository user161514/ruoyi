"""
lnkmake.py — 创建 Windows .lnk 桌面快捷方式

优先使用 pywin32（调用系统 IShellLink 接口，生成的文件带完整 IDList，
资源管理器能正确解析目标与图标）。若 pywin32 不可用，则回退到手工拼装
MS-SHLLINK 二进制（含 LinkInfo，但缺 IDList 时可能显示为白纸图标）。

用法:
    python lnkmake.py <输出lnk> <目标文件> [工作目录] [图标位置] [描述]

图标位置格式: C:\\path\\to\\file.dll,15  或留空自动取目标文件自带图标
"""
import os
import sys


def _create_with_pywin32(out_path, target, working_dir, icon, description):
    """走系统 IShellLink COM 接口生成，产物带完整 IDList，图标可正常显示。

    注意：SHCreateItemFromParsingName + IID_IShellLink 在本机会报「不支持此接口」，
    必须用 CoCreateInstance(CLSID_ShellLink) 直接创建；保存要走 IPersistFile.Save，
    IShellLink 本身没有 Save 方法。
    """
    import pythoncom
    from win32com.shell import shell

    link = pythoncom.CoCreateInstance(
        shell.CLSID_ShellLink,
        None,
        pythoncom.CLSCTX_INPROC_SERVER,
        shell.IID_IShellLink,
    )
    link.SetPath(target)
    if working_dir:
        link.SetWorkingDirectory(working_dir)
    if description:
        link.SetDescription(description)
    if icon:
        link.SetIconLocation(icon, 0)
    persist = link.QueryInterface(pythoncom.IID_IPersistFile)
    persist.Save(out_path, True)


def _create_manual(out_path, target, working_dir, icon, description):
    import struct

    def header(flags, file_size):
        return (
            struct.pack("<I", 0x0000004C)
            + bytes.fromhex("0114020000000000C000000000000046")
            + struct.pack("<I", flags)
            + struct.pack("<I", 0x20)        # FileAttributes = ARCHIVE
            + struct.pack("<Q", 0)           # CreationTime
            + struct.pack("<Q", 0)           # AccessTime
            + struct.pack("<Q", 0)           # WriteTime
            + struct.pack("<I", file_size)
            + struct.pack("<i", 0)           # IconIndex
            + struct.pack("<I", 1)           # ShowCommand = SW_SHOWNORMAL
            + struct.pack("<H", 0)           # HotKey
            + struct.pack("<H", 0)           # Reserved
            + struct.pack("<I", 0)
            + struct.pack("<I", 0)
        )

    def link_info(path):
        lbp = path.encode("utf-8") + b"\x00"
        suffix = b"\x00"
        hdr = 0x1C
        vol_off = hdr
        volume_id = struct.pack("<IIII", 16, 3, 0, 0)
        lbp_off = vol_off + len(volume_id)
        suffix_off = lbp_off + len(lbp)
        body = volume_id + lbp + suffix
        return struct.pack(
            "<IIIIIII",
            hdr + len(body), hdr, 0x01, vol_off, lbp_off, 0, suffix_off
        ) + body

    def string_data(icon_loc):
        out = struct.pack("<H", len(description or ""))
        out += (description or "").encode("utf-16-le") + b"\x00\x00"
        out += struct.pack("<H", len(working_dir))
        out += working_dir.encode("utf-16-le") + b"\x00\x00"
        if icon_loc:
            out += struct.pack("<H", len(icon_loc))
            out += icon_loc.encode("utf-16-le") + b"\x00\x00"
        return out

    try:
        size = os.path.getsize(target)
    except OSError:
        size = 0

    flags = 0x02 | 0x04 | 0x10 | 0x40   # LinkInfo | Name | WorkingDir | IconLocation
    data = header(flags, size) + link_info(target) + string_data(icon)
    with open(out_path, "wb") as f:
        f.write(data)


def make_lnk(out_path, target, working_dir=None, icon=None, description=None):
    target = os.path.abspath(target)
    if working_dir is None:
        working_dir = os.path.dirname(target)
    working_dir = os.path.abspath(working_dir)
    description = description or os.path.basename(target)

    try:
        _create_with_pywin32(out_path, target, working_dir, icon, description)
        return "pywin32"
    except ImportError as e:
        print(f"[warn] pywin32 不可用，回退手工二进制：{e}")
        _create_manual(out_path, target, working_dir, icon, description)
        return "manual"


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    out = sys.argv[1]
    tgt = sys.argv[2]
    wd = sys.argv[3] if len(sys.argv) > 3 and sys.argv[3] else None
    ic = sys.argv[4] if len(sys.argv) > 4 and sys.argv[4] else None
    ds = sys.argv[5] if len(sys.argv) > 5 and sys.argv[5] else None
    how = make_lnk(out, tgt, wd, ic, ds)
    print(f"created({how}): {out} -> {tgt}")
