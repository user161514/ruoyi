import struct, sys, io

def dump(path):
    d = open(path, 'rb').read()
    print("=" * 60)
    print(path, "size=", len(d))
    hs, clsid, flags, attr = struct.unpack_from('<II II', d, 0)
    # proper
    hs = struct.unpack_from('<I', d, 0)[0]
    clsid = d[4:20]
    flags = struct.unpack_from('<I', d, 20)[0]
    attr = struct.unpack_from('<I', d, 24)[0]
    ctime, atime, wtime = struct.unpack_from('<QQQ', d, 28)
    fsize, iconidx, showcmd = struct.unpack_from('<iII', d, 52)
    hotkey = struct.unpack_from('<H', d, 64)[0]
    print(f"HeaderSize=0x{hs:X} clsid={clsid.hex()} flags=0x{flags:X} attr=0x{attr:X}")
    print(f"iconidx={iconidx} showcmd={showcmd} hotkey=0x{hotkey:X} fsize={fsize}")
    off = 0x4C
    # IDList (flag 0x01) comes BEFORE LinkInfo per MS-SHLLINK
    if flags & 0x01:
        idsz = struct.unpack_from('<H', d, off)[0]
        print(f"IDList @0x{off:X} size={idsz} raw={d[off:off+2+idsz].hex()}")
        off += 2 + idsz
    # LinkInfo
    if flags & 0x02:
        lisize, lihdr, liflags, voloff, lbpoff, cnrloff, cpsoff = struct.unpack_from('<IIIIIII', d, off)
        print(f"LinkInfo @0x{off:X} size={lisize} hdrsize={lihdr} flags=0x{liflags:X} voloff={voloff} lbpoff={lbpoff} cpsoff={cpsoff}")
        lb = off + lbpoff - 1
        print("  LocalBasePath:", d[lb:d.index(b'\x00', lb)].decode('utf-16-le'))
        cps = off + cpsoff - 1
        print("  CommonPathSuffix:", repr(d[cps:d.index(b'\x00', cps)].decode('utf-16-le')))
        off += lisize
    # StringData
    def read_str(o):
        n = struct.unpack_from('<H', d, o)[0]
        s = d[o+2:o+2+n*2].decode('utf-16-le')
        o2 = o + 2 + n*2 + 2
        return s, o2
    if flags & 0x04:
        s, off = read_str(off); print("NameString:", s)
    if flags & 0x08:
        s, off = read_str(off); print("RelativePath:", s)
    if flags & 0x10:
        s, off = read_str(off); print("WorkingDir:", s)
    if flags & 0x20:
        s, off = read_str(off); print("Arguments:", repr(s))
    if flags & 0x40:
        s, off = read_str(off); print("IconLocation:", s)
    # ExtraData
    while off + 4 <= len(d):
        sz, cls = struct.unpack_from('<II', d, off)
        if sz == 0: break
        print(f"ExtraData @0x{off:X} size={sz} cls=0x{cls:08X}")
        off += sz

for p in sys.argv[1:]:
    try:
        dump(p)
    except Exception as e:
        print("ERR", p, e)
