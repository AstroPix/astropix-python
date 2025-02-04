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


"""Unit tests for the fmt.py module.
"""

import binascii
import os
import tempfile
import time

import pytest

from core.decode import Decode
from core.fmt import BitPattern, AstroPix4Hit, AstroPixReadout, FileHeader, \
    AstroPixBinaryFile, apxdf_to_csv


# Mock data from a small test run with AstroPix4---the bytearray below should
# be exactly what might come out from a NEXYS board with the AstroPix 4 firmware.
# (For completeness, data were taken on 2024, December 19, and the array if
# taken verbatim from the log file. The readout contains exactly 2 hits.)
sample_readout_data = bytearray.fromhex('bcbce08056e80da85403bcbcbcbcbcbcbcbce080d26f04ca3005bcbcbcbcbcbcffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff')

# And here are the corresponding decoded quantities from the cvs file.
decoded_header = 'dec_ord,id,payload,row,col,ts1,tsfine1,ts2,tsfine2,tsneg1,tsneg2,tstdc1,tstdc2,ts_dec1,ts_dec2,tot_us'
decoded_data0 = (0,7,0,5,5167,3,5418,6,1,0,0,0,49581,52836,162.75)
decoded_data1 = (0,7,0,5,6124,2,4876,5,0,1,0,0,54716,61369,332.65)


def original_decode(readout_data: bytearray):
    """Original decoding function copied verbatim from beam_test.py.

    This, along with the code in decode.py, was used as a guide for the new code
    in fmt.py.
    """
    # Convert the bytearray object from the board into a string
    string_readout = str(binascii.hexlify(readout_data))

    # When we get here, string_readout is a string looking like "b'.....'"
    # First thing first, we do remove the leading "b'" and the trailing "'"
    string_readout = string_readout[2:-1]

    # Now we split the thing into the single events.  This goes as follows:
    # * replace all the ff with bc
    # * split by bc
    # This leaves a loong list of strings, among which most are just empty, and the
    # ones that are not are the representations of our event.
    string_list = [i for i in string_readout.replace('ff','bc').split('bc') if i!='']

    # Flag to catch potential deciding errors. This should remain True unless
    # something goes wrong.
    decoding_bool = True

    # Loop over the events.
    for event in string_list:
        # e0 is apparently the event header---if we do have a mismatch we signal
        # a decoding error.
        if event[0:2] != 'e0':
            decoding_bool = False

    assert decoding_bool == True

    # A couple of hard-coded variables, straight from asic.py
    sampleclockperiod = 5
    num_chips = 1
    decode = Decode(sampleclockperiod, nchips=num_chips, bytesperhit=8)

    list_hits = decode.hits_from_readoutstream(readout_data)
    df = decode.decode_astropix4_hits(list_hits, printer=True)
    return df


def test_bit_pattern():
    """Small test fucntion for the BitPattern class.
    """
    data = bytes.fromhex('bcff')
    pattern = BitPattern(data)
    print(pattern)
    # Test the text representation---note the class inherits the comparison operators
    # from the str class.
    assert pattern == '1011110011111111'
    # Same for __len__().
    assert len(pattern) == 16
    # Test slicing within the byte boundaries.
    assert pattern[0:4] == 11
    assert pattern[4:8] == 12
    assert pattern[8:12] == 15
    assert pattern[12:16] == 15
    # Test slicing across bytes.
    assert pattern[6:10] == 3


def test_original_decoding():
    """Test that our poor-man copy of the original decode returns the same thing
    we found into the csv file.
    """
    df = original_decode(sample_readout_data)
    print(df)
    assert tuple(df.iloc[0]) == decoded_data0
    assert tuple(df.iloc[1]) == decoded_data1


def test_new_decoding():
    """Test the new decoding stuff.
    """
    readout = AstroPixReadout(sample_readout_data, timestamp=time.time())
    print(readout)
    assert readout.num_hits() == 2
    for hit in readout.hits:
        print(hit)
    hit0, hit1 = readout.hits
    # Compare the hit objects with the conten of the csv files---note we are
    # assuming that if the TOT value in us is ok, then all the intermediate timestamp
    # fields are ok, as well.
    assert (hit0.chip_id, hit0.payload, hit0.row, hit0.column) == decoded_data0[0:4]
    assert hit0.tot_us == decoded_data0[-1]
    assert (hit1.chip_id, hit1.payload, hit1.row, hit1.column) == decoded_data1[0:4]
    assert hit1.tot_us == decoded_data1[-1]


def test_file_header():
    """Test the file header.
    """
    # Create a dummy header.
    header = FileHeader(dict(version=1, content='hits'))
    print(header)

    # Write the header to an output file.
    kwargs = dict(suffix=AstroPixBinaryFile._EXTENSION, delete_on_close=False, delete=True)
    with tempfile.NamedTemporaryFile('wb', **kwargs) as output_file:
        print(f'Writing header to {output_file.name}...')
        header.write(output_file)
        output_file.close()

        # Read back the header from the output file.
        print(f'Reading header from {output_file.name}...')
        with open(output_file.name, 'rb') as input_file:
            twin = FileHeader.read(input_file)
        print(twin)

    # Make sure that the whole thing roundtrips.
    assert twin == header


def test_file():
    """Try writing and reading a fully-fledged output file.
    """
    # Create a dummy header.
    header = FileHeader(dict(version=1, content='hits'))
    print(header)
    # Grab our test AstroPix4 hits.
    readout = AstroPixReadout(sample_readout_data, timestamp=time.time())

    # Write the output file.
    kwargs = dict(suffix=AstroPixBinaryFile._EXTENSION, delete_on_close=False, delete=True)
    with tempfile.NamedTemporaryFile('wb', **kwargs) as output_file:
        print(f'Writing data to {output_file.name}...')
        header.write(output_file)
        for hit in readout.hits:
            hit.write(output_file)
        output_file.close()

        # Read back the input file---note this is done in the context of the first
        # with, so that tempfile can cleanup after the fact.
        print(f'Reading data from {output_file.name}...')
        with AstroPixBinaryFile(AstroPix4Hit).open(output_file.name) as input_file:
            print(input_file.header)
            for i, hit in enumerate(input_file):
                print(hit)
                assert hit == readout.hits[i]


@pytest.mark.skip
def test_csv_convert():
    """Read a sample .apx file and convert it to csv.
    """
    file_path = os.path.join(os.path.dirname(__file__), 'data', '20250204_144725_data.apx')
    file_path = apxdf_to_csv(file_path, AstroPix4Hit)
    assert isinstance(file_path, str)
