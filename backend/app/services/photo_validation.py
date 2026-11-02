import warnings
from dataclasses import dataclass
from io import BytesIO
from typing import BinaryIO

from PIL import Image, UnidentifiedImageError

MAX_PHOTO_BYTES = 10 * 1024 * 1024
CHUNK_BYTES = 64 * 1024
IMAGE_FORMATS = {
    "JPEG": ("image/jpeg", "jpg"),
    "PNG": ("image/png", "png"),
    "WEBP": ("image/webp", "webp"),
}


class PhotoValidationError(Exception):
    def __init__(self, detail: str, status_code: int = 422):
        super().__init__(detail)
        self.status_code = status_code


@dataclass(frozen=True)
class ValidatedPhoto:
    data: bytes
    content_type: str
    extension: str


def read_bounded(file: BinaryIO) -> bytes:
    file.seek(0)
    data = bytearray()
    while chunk := file.read(min(CHUNK_BYTES, MAX_PHOTO_BYTES + 1 - len(data))):
        data.extend(chunk)
        if len(data) > MAX_PHOTO_BYTES:
            raise PhotoValidationError("Photo exceeds the 10 MB limit", 413)
    return bytes(data)


def validate_photo(file: BinaryIO, declared_type: str | None) -> ValidatedPhoto:
    if declared_type not in {mime for mime, _ in IMAGE_FORMATS.values()}:
        raise PhotoValidationError(
            "Only image/jpeg, image/png and image/webp are allowed"
        )
    data = read_bounded(file)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(data), formats=list(IMAGE_FORMATS)) as image:
                detected = IMAGE_FORMATS[image.format]
                if declared_type != detected[0]:
                    raise PhotoValidationError(
                        "Declared MIME does not match image format"
                    )
                image.verify()
            # verify() alone does not decode JPEG pixels. Decode every frame,
            # sequentially, so truncated/corrupt data cannot pass on its header.
            with Image.open(BytesIO(data), formats=list(IMAGE_FORMATS)) as image:
                for frame in range(getattr(image, "n_frames", 1)):
                    image.seek(frame)
                    image.load()
    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
        SyntaxError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as exc:
        raise PhotoValidationError("Invalid or unsafe image") from exc
    return ValidatedPhoto(data, *detected)
