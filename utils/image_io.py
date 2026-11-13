"""支持 Windows 中文目录的图像写入，失败时明确报错。"""

from pathlib import Path
import cv2


def write_image(path, image):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    success, encoded = cv2.imencode(path.suffix, image)
    if not success:
        raise OSError(f"无法编码图像: {path}")
    path.write_bytes(encoded.tobytes())
