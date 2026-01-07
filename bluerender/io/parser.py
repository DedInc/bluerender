"""
PRBM (BlueMap 3D geometry) format parser.

Based on BlueMap's PRBMLoader.js - a variant of the PRWM format.
"""

from typing import Dict

import numpy as np

from bluerender.core import PRBMGeometry, MaterialGroup
from bluerender.core import (
    PRBM_SUPPORTED_VERSION,
    PRBM_HEADER_SIZE,
    PRBM_GROUP_SIZE,
    PRBM_END_MARKER,
    PRBM_TYPE_MAP,
)


class PRBMParseError(Exception):
    """Raised when PRBM parsing fails."""

    pass


def parse_prbm(data: bytes) -> PRBMGeometry:
    """
    Parse PRBM (BlueMap 3D geometry) format.

    Args:
        data: Raw PRBM file bytes

    Returns:
        PRBMGeometry with all vertex attributes

    Raises:
        PRBMParseError: If the format is invalid or unsupported
    """
    parser = _PRBMParser(bytearray(data))
    return parser.parse()


class _PRBMParser:
    """Internal PRBM parser implementation."""

    def __init__(self, data: bytearray):
        self.data = data
        self.pos = 0

    def parse(self) -> PRBMGeometry:
        """Parse the PRBM data and return geometry."""
        header = self._parse_header()
        attributes = self._parse_attributes(header)
        self._skip_indices(header)
        groups = self._parse_groups()
        return self._build_geometry(attributes, groups)

    def _parse_header(self) -> dict:
        """Parse PRBM header (8 bytes)."""
        if len(self.data) < PRBM_HEADER_SIZE:
            raise PRBMParseError("Data too short for PRBM header")

        version = self.data[0]
        if version != PRBM_SUPPORTED_VERSION:
            raise PRBMParseError(f"Unsupported PRBM version: {version}")

        flags = self.data[1]
        big_endian = bool((flags >> 5) & 1)

        if big_endian:
            values_num = (self.data[2] << 16) + (self.data[3] << 8) + self.data[4]
            indices_num = (self.data[5] << 16) + (self.data[6] << 8) + self.data[7]
        else:
            values_num = self.data[2] + (self.data[3] << 8) + (self.data[4] << 16)
            indices_num = self.data[5] + (self.data[6] << 8) + (self.data[7] << 16)

        self.pos = PRBM_HEADER_SIZE

        return {
            "indexed": bool((flags >> 7) & 1),
            "indices_type": (flags >> 6) & 1,  # 0=Uint16, 1=Uint32
            "num_attrs": flags & 0x1F,
            "values_num": values_num,
            "indices_num": indices_num,
        }

    def _parse_attributes(self, header: dict) -> Dict[str, np.ndarray]:
        """Parse all vertex attributes."""
        attributes = {}

        for _ in range(header["num_attrs"]):
            name = self._read_string()
            attr_data = self._read_attribute_data(header["values_num"])
            attributes[name] = attr_data

        return attributes

    def _read_string(self) -> str:
        """Read null-terminated string."""
        chars = []
        while self.pos < len(self.data):
            c = self.data[self.pos]
            self.pos += 1
            if c == 0:
                break
            chars.append(chr(c))
        return "".join(chars)

    def _read_attribute_data(self, values_num: int) -> np.ndarray:
        """Read attribute data based on flags."""
        aflags = self.data[self.pos]
        cardinality = ((aflags >> 4) & 0x03) + 1
        encoding_type = aflags & 0x0F
        self.pos += 1

        # Align to 4 bytes
        self.pos = ((self.pos + 3) // 4) * 4

        dtype = np.dtype(PRBM_TYPE_MAP[encoding_type])
        count = cardinality * values_num

        values = np.frombuffer(self.data, dtype=dtype, count=count, offset=self.pos)

        if cardinality > 1:
            values = values.reshape(-1, cardinality)

        self.pos += dtype.itemsize * count
        return values

    def _skip_indices(self, header: dict) -> None:
        """Skip over index data if present."""
        if not header["indexed"] or header["indices_num"] <= 0:
            return

        self.pos = ((self.pos + 3) // 4) * 4
        index_dtype = np.uint32 if header["indices_type"] == 1 else np.uint16
        self.pos += np.dtype(index_dtype).itemsize * header["indices_num"]

    def _parse_groups(self) -> list[MaterialGroup]:
        """Parse material groups."""
        groups = []
        self.pos = ((self.pos + 3) // 4) * 4

        while self.pos + PRBM_GROUP_SIZE <= len(self.data):
            mat_idx = int.from_bytes(
                self.data[self.pos : self.pos + 4], "little", signed=True
            )
            if mat_idx == PRBM_END_MARKER:
                break

            start = int.from_bytes(
                self.data[self.pos + 4 : self.pos + 8], "little", signed=True
            )
            count = int.from_bytes(
                self.data[self.pos + 8 : self.pos + 12], "little", signed=True
            )

            groups.append(
                MaterialGroup(
                    material_index=mat_idx,
                    start=start,
                    count=count,
                )
            )
            self.pos += PRBM_GROUP_SIZE

        return groups

    def _build_geometry(
        self, attributes: Dict[str, np.ndarray], groups: list[MaterialGroup]
    ) -> PRBMGeometry:
        """Build PRBMGeometry from parsed attributes."""
        return PRBMGeometry(
            position=attributes.get("position", np.zeros((0, 3), dtype=np.float32)),
            normal=attributes.get("normal", np.zeros((0, 3), dtype=np.int8)),
            color=attributes.get("color", np.zeros((0, 3), dtype=np.uint8)),
            uv=attributes.get("uv", np.zeros((0, 2), dtype=np.float32)),
            ao=_flatten_or_default(attributes.get("ao"), np.uint8, 255),
            blocklight=_flatten_or_default(attributes.get("blocklight"), np.int8, 0),
            sunlight=_flatten_or_default(attributes.get("sunlight"), np.int8, 15),
            groups=groups,
        )


def _flatten_or_default(
    arr: np.ndarray | None, dtype: type, default_value: int
) -> np.ndarray:
    """Flatten array or return empty with default value."""
    if arr is not None:
        return arr.flatten()
    return np.array([], dtype=dtype)
