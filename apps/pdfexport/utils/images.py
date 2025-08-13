import base64
from pathlib import Path

def png_path_to_data_uri(path: str) -> str:
    p = Path(path)
    with p.open("rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")
    return f"data:image/png;base64,{b64}"