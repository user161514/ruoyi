"""
lnkmake.py — 生成 Windows .lnk 桌面快捷方式（不依赖 COM / WScript.Shell）

结构严格按 MS-SHLLINK：
  ShellLinkHeader(0x4C) -> LinkTargetIDList -> LinkInfo -> StringData -> ExtraData

用法:
    python lnkmake.py <输出lnk> <目标文件> [工作目录] [图标] [描述]
"""
import struct
import sys
import os


def _shell_link_header(flags, file_attr, file_size, icon_index, show_cmd):
    return (
        struct.pack("<I", 0x0000004C)              # HeaderSize
        + bytes.fromhex("0114020000000000C000000000000046")  # LinkCLSID
        + struct.pack("<I", flags)                 # LinkFlags
        + struct.pack("<I", file_attr)             # FileAttributes
        + struct.pack("<Q", 0)                     # CreationTime
        + struct.pack("<Q", 0)                     # AccessTime
        + struct.pack("<Q", 0)                     # WriteTime
        + struct.pack("<I", file_size)             # FileSize
        + struct.pack("<i", icon_index)            # IconIndex
        + struct.pack("<I", show_cmd)              # ShowCommand
        + struct.pack("<H", 0)                     # HotKey
        + struct.pack("<H", 0)                     # Reserved
        + struct.pack("<I", 0)                     # Reserved2
        + struct.pack("<I", 0)                     # Reserved3
    )


def _link_info(local_base_path):
    """构造 LinkInfo（本地路径）。卷序列号为 0，仅保留 drive type。"""
    drive = local_base_path[:3] if len(local_base_path) >= 2 and local_base_path[1] == ":" else "C:\\"
    lbp = local_base_path.encode("utf-8") + b"\x00"
    suffix = b"\x00"  # CommonPathSuffix 为空

    header_size = 0x1C
    volume_id_offset = header_size
    # VolumeID: size(4) + driveType(4) + driveSerial(4) + labelOffset(4)
    volume_id = struct.pack("<IIII", 16, 3, 0, 0)
    local_base_path_offset = volume_id_offset + len(volume_id)
    common_path_suffix_offset = local_base_path_offset + len(lbp)

    body = (
        volume_id
        + lbp
        + suffix
    )
    total_size = header_size + len(body)
    head = struct.pack(
        "<IIIIIII",
        total_size,      # LinkInfoSize
        header_size,     # LinkInfoHeaderSize
        0x01,            # LinkInfoFlags: VolumeIDAndLocalBasePath
        volume_id_offset,
        local_base_path_offset,
        0,               # CommonNetworkRelativeLinkOffset
        common_path_suffix_offset,
    )
    return head + body


def _string_data(name, relative_path, working_dir, icon_location):
    out = b""
    if name is not None:
        out += struct.pack("<H", len(name)) + name.encode("utf-16-le") + b"\x00\x00"
    if relative_path is not None:
        out += struct.pack("<H", len(relative_path)) + relative_path.encode("utf-16-le") + b"\x00\x00"
    if working_dir is not None:
        out += struct.pack("<H", len(working_dir)) + working_dir.encode("utf-16-le") + b"\x00\x00"
    if icon_location is not None:
        out += struct.pack("<H", len(icon_location)) + icon_location.encode("utf-16-le") + b"\x00\x00"
    return out


def _extra_environment_block():
    """ExtraData 中的 EnvironmentVariableDataBlock（clsid 0xA0000001）。"""
    entries = {
        "%USERPROFILE%": os.environ.get("USERPROFILE", ""),
    }
    body = b""
    for k, v in entries.items():
        if not v:
            continue
        body += (
            struct.pack("<H", len(k)) + k.encode("utf-16-le")
            + struct.pack("<H", len(v)) + v.encode("utf-16-le")
        )
    if not body:
        return b""
    size = 4 + 2 + 2 + len(body)
    return struct.pack("<II", size, 0xA0000001) + body


def make_lnk(out_path, target, working_dir=None, icon=None, description=None,
             relative_path=None, window_style=1, hotkey=0):
    target = os.path.abspath(target)
    if working_dir is None:
        working_dir = os.path.dirname(target)
    working_dir = os.path.abspath(working_dir)

    try:
        file_size = os.path.getsize(target)
    except OSError:
        file_size = 0

    # LinkFlags
    # 0x01 HasLinkTargetIDList(我们不写 IDList) -> 0x02 HasLinkInfo
    # 0x04 HasName, 0x08 HasRelativePath, 0x10 HasWorkingDir, 0x40 HasIconLocation
    flags = 0x02 | 0x04 | 0x10 | 0x40
    if relative_path:
        flags |= 0x08

    header = _shell_link_header(flags, 0x20, file_size, 0, window_style)
    link_info = _link_info(target)
    strings = _string_data(
        description or os.path.basename(target),
        relative_path,
        working_dir,
        icon,
    )
    extra = _extra_environment_block()

    data = header + link_info + strings + extra
    with open(out_path, "wb") as f:
        f.write(data)
    return len(data)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    out = sys.argv[1]
    tgt = sys.argv[2]
    wd = sys.argv[3] if len(sys.argv) > 3 and sys.argv[3] else None
    ic = sys.argv[4] if len(sys.argv) > 4 and sys.argv[4] else None
    ds = sys.argv[5] if len(sys.argv) > 5 and sys.argv[5] else None
    n = make_lnk(out, tgt, wd, ic, ds)
    print(f"created: {out} ({n} bytes) -> {tgt}")
