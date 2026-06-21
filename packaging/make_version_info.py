# -*- coding: utf-8 -*-
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from partspack import APP_NAME, ORG, __version__   # noqa: E402

parts = (__version__.split(".") + ["0", "0", "0", "0"])[:4]
v = ", ".join(parts)
out = os.path.join(os.path.dirname(__file__), "version_info.txt")

txt = """# UTF-8
# Windows version resource for the Parts Packing Generator .exe.
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=(%s),
    prodvers=(%s),
    mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        u"040904B0",
        [StringStruct(u"CompanyName", u"%s"),
         StringStruct(u"FileDescription",
                      u"%s - parametric 3D-printable nesting trays"),
         StringStruct(u"FileVersion", u"%s"),
         StringStruct(u"InternalName", u"PartsPack"),
         StringStruct(u"OriginalFilename", u"PartsPack.exe"),
         StringStruct(u"ProductName", u"%s"),
         StringStruct(u"ProductVersion", u"%s")])
    ]),
    VarFileInfo([VarStruct(u"Translation", [1033, 1200])])
  ]
)
""" % (v, v, ORG, APP_NAME, __version__, APP_NAME, __version__)

open(out, "w", encoding="utf-8").write(txt)
print("wrote %s for %s %s" % (out, APP_NAME, __version__))
