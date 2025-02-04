# Copyright (C) 2025 the astropix team.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.


"""Basic packet description for the astropix chips.
"""

from __future__ import annotations

from contextlib import contextmanager
import json
import struct
import typing

from modules.setup_logger import logger


# Table to reverse the bit order within a byte---we pre-compute this once and
# forever to speedup the computation at runtime and avoid doing the same
# calculation over and over again.
_BIT_REVERSE_TABLE = bytes.maketrans(
    bytes(range(256)),
    bytes(int(f'{i:08b}'[::-1], 2) for i in range(256))
)


def reverse_bit_order(data: bytearray) -> None:
    """Reverses the bit order within of a bytearray."""
    return data.translate(_BIT_REVERSE_TABLE)


class BitPattern(str):

    """Small convenience class representing a bit pattern, that we can slice
    (interpreting the result as the binary representation of an integer) without
    caring about the byte boundaries.

    This is not very memory-efficient and probably not blazingly fast either, but
    it allows to reason about the incoming bits in a straighforward fashion, and
    I doubt we will ever need to optimize this. (If that is the case, there are
    probably ways, using either numpy or the bitarray third-party package.)

    Arguments
    ---------
    data : bytes
        The binary representation of the bit pattern.
    """

    def __new__(cls, data: bytes) -> None:
        """Strings are immutable, so use __new__ to start.
        """
        return super().__new__(cls, ''.join(f'{byte:08b}' for byte in data))

    def __getitem__(self, index):
        """Slice the underlying string and convert to integer in base 2.
        """
        return int(super().__getitem__(index), 2)


class AstroPixHitBase:

    """Base class for a generic AstroPix hit.

    While the original decode routine was working in terms of the various bytes
    in the binary representation of the hit, since there seem to be no meaning
    altogether in the byte boundaries (at least for AstroPix 4), and the various
    fields are arbitrary subsets of a multi-byte word, it seemed more naturale to
    describe the hit as a sequence of fields, each one with its own length in bits.

    Arguments
    ---------
    data : bytearray
        The portion of a full AstroPix readout representing a single hit.
    """

    SIZE = None
    FIELD_DICT = None

    def __init__(self, data: bytearray) -> None:
        """Constructor.
        """
        # Since we don't need the underlying bit pattern to be mutable, turn the
        # bytearray object into a bytes object.
        self._data = bytes(data)
        # Build a bit pattern to extract the fields and loop over the hit fields
        # to set all the class members.
        bit_pattern = BitPattern(self._data)
        pos = 0
        for name, width in self.FIELD_DICT.items():
            self.__setattr__(name, bit_pattern[pos:pos + width])
            pos += width

    def write(self, otuput_file: typing.BinaryIO) -> None:
        """Write the binary data to a file.

        Arguments
        ---------
        output_file : BinaryIO
            A file object opened in "wb" mode.
        """
        otuput_file.write(self._data)

    def __eq__(self, other: 'AstroPixHitBase') -> bool:
        """Comparison operator---this is handy in the unit tests.
        """
        return self._data == other._data

    @staticmethod
    def gray_to_decimal(gray: int) -> int:
        """Convert a Gray code (integer) to decimal.

        A Gray code (or reflected binary code) is a binary numeral system where
        two consecutive values differ by only one bit, which makes it useful in
        error correction and minimizing logic transitions in digital circuits.
        This function is provided as a convenience to translate counter values
        encoded in Gray code into actual decimal values.
        """
        decimal = gray  # First bit is the same
        mask = gray
        while mask:
            mask >>= 1
            decimal ^= mask  # XOR each shifted bit
        return decimal

    def _format_attributes(self, attrs: tuple[str], fmts: tuple[str] = None) -> tuple[str]:
        """Helper function to join a given set of class attributes in a properly
        formatted string.

        Arguments
        ---------
        attrs : tuple
            The names of the class attributes we want to include in the representation.

        fmts : tuple, optional
            If present determines the formatting of the given attributes.
        """
        vals = (getattr(self, attr) for attr in attrs)
        if fmts is None:
            fmts = ('%s' for _ in attrs)
        return tuple(fmt % val for val, fmt in zip(vals, fmts))

    def _repr(self, attrs: tuple[str], fmts: tuple[str] = None) -> str:
        """Helper function to provide sensible string formatting for the packets.

        The basic idea is that concrete classes would use this to implement their
        `__repr__()` and/or `__str__()` special dunder methods.

        Arguments
        ---------
        attrs : tuple
            The names of the class attributes we want to include in the representation.

        fmts : tuple, optional
            If present determines the formatting of the given attributes.
        """
        vals = self._format_attributes(attrs, fmts)
        info = ', '.join([f'{attr}={val}' for attr, val in zip(attrs, vals)])
        return f'{self.__class__.__name__}({info})'

    def _text(self, attrs: tuple[str], fmts: tuple[str], separator: str) -> str:
        """Helper function for text formatting.

        Note the output includes a trailing endline.

        Arguments
        ---------
        attrs : tuple
            The names of the class attributes we want to include in the representation.

        fmts : tuple,
            Determines the formatting of the given attributes.

        separator : str
            The separator between different fields.
        """
        vals = self._format_attributes(attrs, fmts)
        return f'{separator.join(vals)}\n'


class AstroPix3Hit(AstroPixHitBase):

    """Class describing an AstroPix3 hit.

    .. warning::

        This is copied from decode.py and totally untested.
    """

    SIZE = 5
    FIELD_DICT = {
        'chip_id': 5,
        'payload': 3,
        'column': 1,
        'reserved1': 1,
        'location': 6,
        'timestamp': 8,
        'reserved2': 4,
        'tot_msb': 4,
        'tot_lsb': 8
    }
    _FIELD_NAMES = tuple(FIELD_DICT.keys()) + ('tot', 'tot_us')
    CLOCK_CYCLES_PER_US = 200.

    def __init__(self, data: bytearray) -> None:
        """Constructor.
        """
        super().__init__(data)
        # Calculate the TOT in physical units.
        self.tot = (self.tot_msb << 8) + self.tot_lsb
        self.tot_us = self.tot / self.CLOCK_CYCLES_PER_US


class AstroPix4Hit(AstroPixHitBase):

    """Class describing an AstroPix4 hit.
    """

    SIZE = 8
    FIELD_DICT = {
        'chip_id': 5,
        'payload': 3,
        'row': 5,
        'column': 5,
        'ts_neg1': 1,
        'ts_coarse1': 14,
        'ts_fine1': 3,
        'ts_tdc1': 5,
        'ts_neg2': 1,
        'ts_coarse2': 14,
        'ts_fine2': 3,
        'ts_tdc2': 5
    }
    _FIELD_NAMES = tuple(FIELD_DICT.keys()) + ('ts_dec1', 'ts_dec2', 'tot_us', 'timestamp')
    CLOCK_CYCLES_PER_US = 20.
    CLOCK_ROLLOVER = 2**17

    def __init__(self, data: bytearray, timestamp: float = None) -> None:
        """Constructor.
        """
        super().__init__(data)
        # Calculate the values of the two timestamps in clock cycles.
        self.ts_dec1 = self._compose_timestamp(self.ts_coarse1, self.ts_fine1)
        self.ts_dec2 = self._compose_timestamp(self.ts_coarse2, self.ts_fine2)
        # Take into account possible rollovers.
        if self.ts_dec2 < self.ts_dec1:
            self.ts_dec2 += self.CLOCK_ROLLOVER
        # Calculate the actual TOT in us.
        self.tot_us = (self.ts_dec2 - self.ts_dec1) / self.CLOCK_CYCLES_PER_US
        self.timestamp = timestamp

    @staticmethod
    def _compose_timestamp(ts_coarse: int, ts_fine: int) -> int:
        """Compose the actual decimal representation of the timestamp counter,
        putting together the coarse and fine counters (in Gray code).

        Arguments
        ---------
        ts_coarse : int
            The value of the coarse counter (MSBs) in Gray code.

        ts_fine : int
            The value of the fine counter (3 LSBs) in Gray code.

        Returns
        -------
        int
            The actual decimal value of the timestamp counter, in clock cycles.
        """
        return AstroPixHitBase.gray_to_decimal((ts_coarse << 3) + ts_fine)

    @classmethod
    def text_header(cls, fields=_FIELD_NAMES, separator=',') -> str:
        """Return a proper header for a text file representing a list of hits.
        """
        return ','.join(fields)

    def to_csv(self, fields=_FIELD_NAMES) -> str:
        """Return the hit representation in csv format.
        """
        return self._text(fields, fmts=None, separator=',')

    def __str__(self) -> str:
        """String formatting.
        """
        return self._repr(self._FIELD_NAMES)


class AstroPixReadout:

    """Class describing an AstroPix readout, i.e., a full readout from the NEXYS board.

    This comes in the form of a fixed-length bytearray object that is padded at the
    end with a fixed byte (0xff).

    What remains when the padding bytes have been removed should be a sequence of
    frames of the form

    bcbc ... hit data ... bcbcbcbcbcbc

    where the hit data are 8-byte long and encapsulate all the information within
    a single hit.

    Arguments
    ---------
    data : bytearray
        A full readout from a NEXYS board.

    timestamp : float (optional)
        A timestamp (s since the epoch) assigned by the hist machine.
    """

    PADDING_BYTE = bytes.fromhex('ff')
    HIT_HEADER = bytes.fromhex('bcbc')
    HIT_TRAILER = bytes.fromhex('bcbcbcbcbcbc')
    HIT_DATA_SIZE = AstroPix4Hit.SIZE
    HIT_HEADER_LENGTH = len(HIT_HEADER)
    HIT_TRAILER_LENGTH = len(HIT_TRAILER)
    HIT_LENGTH = HIT_HEADER_LENGTH + HIT_DATA_SIZE + HIT_TRAILER_LENGTH

    def __init__(self, data: bytearray, timestamp: int = None) -> None:
        """Constructor.
        """
        # Strip all the trailing padding bytes from the input bytearray object.
        self._data = data.rstrip(self.PADDING_BYTE)
        # Check that the length of the readout is a multiple of the frame length.
        if not len(self) % self.HIT_LENGTH == 0:
            raise RuntimeError(f'Readout length ({len(self)}) not a multiple of {self.HIT_LENGTH}')
        self.timestamp = timestamp
        self.hits = self.__decode()

    def __decode(self, reverse: bool = True) -> list[AstroPix4Hit]:
        """Decode the underlying data and turn them into a list of hits.

        Arguments
        ---------
        reverse : bool (default True)
            If True, the bit order within each byte is reversed.
        """
        hits = []
        pos = 0
        # Loop over the underlying data.
        while pos < len(self):
            # Select the data portion corresponding to the next frame.
            hit_data = self._data[pos:pos + self.HIT_LENGTH]

            # Check that the frame header and trailer are what we expect.
            header = hit_data[:self.HIT_HEADER_LENGTH]
            if header != self.HIT_HEADER:
                raise RuntimeError(f'Wrong frame header {header}, expected {self.HIT_HEADER}')
            trailer = hit_data[-self.HIT_TRAILER_LENGTH:]
            if trailer != self.HIT_TRAILER:
                raise RuntimeError(f'Wrong frame trailer {header}, expected {self.HIT_TRAILER}')

            # Trim the hit data and get rid of the header and trailer.
            hit_data = hit_data[self.HIT_HEADER_LENGTH:-self.HIT_TRAILER_LENGTH]
            # If necessary, reverse the bit order in the hit data.
            if reverse:
                hit_data = reverse_bit_order(hit_data)
            # Create a fully-fledged AstroPix4Hit object.
            hits.append(AstroPix4Hit(hit_data, self.timestamp))
            pos += self.HIT_LENGTH
        return hits

    def num_hits(self) -> int:
        """Return the number of hits in the readout.
        """
        return len(self) // self.HIT_LENGTH

    def __len__(self) -> int:
        """Return the length of the underlying data in bytes.
        """
        return len(self._data)

    def __str__(self) -> str:
        """String formatting.
        """
        return f'{self.__class__.__name__}({self.num_hits()} hits, {len(self)} bytes, timestamp = {self.timestamp} s)'


class FileHeader:

    """Class describing a file header.

    The content of the header can be literally anything that is json-serializable,
    i.e., the only request that we make is that ``json.dumps(self._content)``
    is not raising an exception.

    The basic contract is that when the ``write()`` method is called we write
    into the output binary file:

    * the header magic word (``%APXDF`` for AstroPix Data Format);
    * the length of the header content in bytes;
    * the actual header content.

    In the opposite direction, when the ``read()`` hook is called, we do:

    * read the first small chunk of the binary file and make sure the magic word is correct;
    * read the header length;
    * read and deserialize the header conten, returning a full fledges ``FileHeader`` object.

    Arguments
    ---------
    content : anything that is serializable
        The header content.
    """

    MAGIC_WORD = '%APXDF'
    _HEADER_LENGTH_FMT = 'I'
    ENCODING = 'utf-8'

    def __init__(self, content: typing.Any) -> None:
        """Constructor.
        """
        self._content = content

    def write(self, output_file: typing.BinaryIO) -> None:
        """Serialize the header structure to an output binary file.

        Arguments
        ---------
        output_file : BinaryIO
            A file object opened in "wb" mode.
        """
        output_file.write(self.MAGIC_WORD.encode(self.ENCODING))
        data = json.dumps(self._content).encode(self.ENCODING)
        output_file.write(struct.pack(self._HEADER_LENGTH_FMT, len(data)))
        output_file.write(data)

    @classmethod
    def read(cls, input_file: typing.BinaryIO) -> 'FileHeader':
        """De-serialize the header structure from an input binary file.

        Arguments
        ---------
        input_file : BinaryIO
            A file object opened in "rb" mode.
        """
        magic = input_file.read(len(cls.MAGIC_WORD)).decode(cls.ENCODING)
        if magic != cls.MAGIC_WORD:
            raise RuntimeError(f'Invalid magic word ({magic}), expected {cls.MAGIC_WORD}')
        header_length = input_file.read(struct.calcsize(cls._HEADER_LENGTH_FMT))
        header_length = struct.unpack(cls._HEADER_LENGTH_FMT, header_length)[0]
        content = json.loads(input_file.read(header_length).decode(cls.ENCODING))
        return cls(content)

    def __eq__(self, other: 'FileHeader') -> bool:
        """Comparison operator---this is useful in the unit tests in order to make
        sure that the serialization/deserialization roundtrips.
        """
        return self._content == other._content

    def __str__(self) -> str:
        """String representation.
        """
        return f'{self._content}'


class AstroPixBinaryFile:

    """Class describing a binary file containing packets.

    .. warning::

        At this point this only supports input files. Shall we consider extending
        the interface for writing output files as well?

    Arguments
    ---------
    hit_class : type
        The class representing the hit type encoded in the file, e.g., ``AstroPix4Hit``.
    """

    _EXTENSION = '.apx'

    def __init__(self, hit_class: type) -> None:
        """Constructor.
        """
        self._hit_class = hit_class
        self._input_file = None

    @contextmanager
    def open(self, file_path: str):
        """Open the file.

        Arguments
        ---------
        file_path : str
            Path to the file to be read.
        """
        if not file_path.endswith(self._EXTENSION):
            raise RuntimeError(f'Input file {file_path} has not the {self._EXTENSION} extension')
        logger.info(f'Opening input packet file {file_path}...')
        with open(file_path, 'rb') as input_file:
            self._input_file = input_file
            self.header = FileHeader.read(self._input_file)
            yield self
            self._input_file = None
        logger.info(f'Input file {file_path} closed.')

    def __iter__(self) -> 'AstroPixBinaryFile':
        """Return the iterator object (self).
        """
        return self

    def __next__(self) -> AstroPixHitBase:
        """Read the next packet in the buffer.
        """
        data = self._input_file.read(self._hit_class.SIZE)
        if not data:
            raise StopIteration
        return self._hit_class(data)


def _convert_apxdf(file_path: str, hit_class: type, converter: typing.Callable,
                   header: str = None, output_file_path: str = None, open_mode: str = 'w',
                   default_extension: str = None) -> str:
    """Generic conversion factory for AstroPixBinaryFile objects.
    """
    if output_file_path is None and default_extension is not None:
        output_file_path = file_path.replace('.apx', default_extension)
    with AstroPixBinaryFile(hit_class).open(file_path) as input_file, \
        open(output_file_path, open_mode) as output_file:
        if header is not None:
            output_file.write(header)
        for hit in input_file:
            output_file.write(converter(hit))
    return output_file_path


def apxdf_to_csv(file_path: str, hit_class: type = AstroPix4Hit,
                 output_file_path: str = None) -> str:
    """Convert an AstroPix binary file to csv.
    """
    header = f'# {AstroPix4Hit.text_header()}\n'
    return _convert_apxdf(file_path, hit_class, hit_class.to_csv, header, output_file_path, 'w', '.csv')
