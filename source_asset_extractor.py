"""Safe extraction of embedded raster assets from DOCX source files."""
from __future__ import annotations

import io
import zipfile
from PIL import Image


def extract_docx_assets(data: bytes, source_name: str, max_assets: int=40) -> list[dict]:
    assets=[]
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            names=[n for n in archive.namelist() if n.startswith("word/media/") and not n.endswith("/")][:max_assets]
            for index,name in enumerate(names,1):
                raw=archive.read(name)
                if len(raw)>12*1024*1024: continue
                try:
                    img=Image.open(io.BytesIO(raw)); img.verify()
                except Exception: continue
                assets.append({"asset_id":f"{source_name}#image-{index}","source_file":source_name,"member":name,
                               "filename":name.rsplit("/",1)[-1],"bytes":raw,"mime_type":Image.MIME.get(img.format,"image/png")})
    except (zipfile.BadZipFile,OSError):
        return []
    return assets

