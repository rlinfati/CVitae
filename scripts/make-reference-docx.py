#!/usr/bin/env python3
"""Build assets/reference.docx: Quarto's default docx template with justified body text."""
import os
import re
import subprocess
import zipfile

OUT = "assets/reference.docx"
JUSTIFIED = ("BodyText", "FirstParagraph", "Compact")

os.makedirs("assets", exist_ok=True)
subprocess.run(
    ["quarto", "pandoc", "-o", OUT, "--print-default-data-file", "reference.docx"],
    check=True,
)

with zipfile.ZipFile(OUT) as zin:
    items = [(i, zin.read(i.filename)) for i in zin.infolist()]

with zipfile.ZipFile(OUT, "w", zipfile.ZIP_DEFLATED) as zout:
    for info, data in items:
        if info.filename == "word/styles.xml":
            xml = data.decode()
            for sid in JUSTIFIED:
                style = re.search(rf'<w:style [^>]*w:styleId="{sid}".*?</w:style>', xml, re.S).group(0)
                if "<w:jc" in style:
                    new = re.sub(r"<w:jc [^>]*/>", '<w:jc w:val="both"/>', style)
                elif "<w:pPr>" in style:
                    new = style.replace("<w:pPr>", '<w:pPr><w:jc w:val="both"/>', 1)
                elif "<w:pPr/>" in style:
                    new = style.replace("<w:pPr/>", '<w:pPr><w:jc w:val="both"/></w:pPr>', 1)
                else:
                    new = style.replace("</w:style>", '<w:pPr><w:jc w:val="both"/></w:pPr></w:style>')
                xml = xml.replace(style, new)
            data = xml.encode()
        zout.writestr(info, data)
