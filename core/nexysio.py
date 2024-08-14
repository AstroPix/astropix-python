# -*- coding: utf-8 -*-
""""""
"""
Created on Fri Jun 25 16:10:45 2021

@author: Nicolas Striebig

"""
import ftd2xx as ftd
import sys
import time

import logging
import binascii

from core.spi import Spi
from modules.setup_logger import logger

READ_ADRESS     = 0x00
WRITE_ADRESS    = 0x01

SR_ASIC_ADRESS  = 0x00

SIN_ASIC        = 0x04
LD_ASIC         = 0x08
LD_TDAC_ASIC    = 0x40

SIN_GECCO       = 0x02
LD_GECCO        = 0x04

NEXYS_USB_DESC  = b'Digilent USB Device A'
NEXYS_USB_SER   = b'210276'

logger = logging.getLogger(__name__)


class Nexysio(Spi):
    """Interface to Nexys FTDI Chip"""

    def __init__(self, handle=0) -> None:
        super().__init__()
        self._handle = handle

    @classmethod
    def __addbytes(cls, value: bytearray, clkdiv: int) -> bytearray:
        """
        Clockdivider by writing bytes multiple times

        :param value: Bytearray to divide
        :param clkdiv: Clockdivider

        :returns: Device handle
        """

        data = bytearray()

        clkdiv = max(clkdiv, 1)

        for byte in value:
            data.extend([byte] * clkdiv)

        return data

    def debug_print(self, name: str, length: int, hbyte: int, lbyte: int, 
                    header: bytearray, value: bytearray):
        logger.debug(
            "\nWrite %s\n===============================\
            Length: %d hByte: %d lByte: %d\n\
            Header: 0x%s\
            Data (%d Bits): 0b%s\n",
            name, length, hbyte, lbyte, header.hex(), len(value), value.bin
        )

    def open(self, index: int):
        """
        Opens the FTDI device

        :param index: Device index

        :returns: Device handle
        """

        self._handle = ftd.open(index)

        devinfo = self._handle.getDeviceInfo()

        try:
            if 'description' in devinfo and devinfo['description'] == NEXYS_USB_DESC:
                print("\u001b[32mDigilent USB A opened\n \u001b[0m")
                logger.info("\u001b[32mDigilent USB A opened\n \u001b[0m")
            else:
                self.close()
                raise NameError

        except NameError:
            logger.error('Unknown Device with index %d', index)
            sys.exit(1)

        self.__setup()

        return self._handle

    def autoopen(self):
        """
        Auto-opens the FTDI device with NEXYS_USB description

        :returns: Device handle
        """
        # Get list with serialnumbers and descritions of all connected devices
        device_serial = ftd.listDevices(0)
        device_desc = ftd.listDevices(2)

        try:
            if device_serial is None:
                raise TypeError
        except TypeError:
            logger.error('No Devices found')
            sys.exit(1)

        # iterate through list and open device, if found
        for index, value in enumerate(device_desc):
            if value == NEXYS_USB_DESC:
                if device_serial[index].startswith(NEXYS_USB_SER):
                    self._handle = ftd.open(index)
                    self.__setup()

                    logger.info("\u001b[32mDigilent USB A opened\n \u001b[0m")
                    # Return handle
                    return self._handle

        logger.error('Nexys not found')
        return False

    def write(self, value: bytes) -> None:
        """
        Direct write to FTDI chip

        Use with caution!

        :param value: Bytestring to write
        """
        try:
            # split large vectors into multiple parts
            while len(value) > 64000:
                logger.debug("Split writevector in parts")
                self._handle.write(value[0:63999])
                value = value[64000:]

            self._handle.write(value)
        except AttributeError:
            logger.error('Nexys Write Error')

    def read(self, num: int) -> bytes:
        """
        Direct read from FTDI chip

        :param num: Number of Bytes to read
        """
        remaining = num
        bytes = bytearray()

        try:
            while remaining > 0:
                rbytes = self._handle.read(remaining)
                logger.debug("Reading %d bytes from FTDI", remaining)
                bytes.extend(rbytes)
                logger.debug("Read %d bytes from FTDI", len(rbytes))
                remaining -= len(rbytes)

            return bytes
        except AttributeError:
            logger.error('Nexys Read Error')
            return None

    def close(self) -> None:
        """Close connection"""

        self._handle.close()

    def __setup(self) -> None:
        """Set FTDI USB connection settings"""

        self._handle.setTimeouts(1000, 1000)  # Timeout RX,TX
        self._handle.setBitMode(0xFF, 0x00)  # Reset
        self._handle.setBitMode(0xFF, 0x40)  # Set Synchronous 245 FIFO Mode
        self._handle.setLatencyTimer(2)
        self._handle.setUSBParameters(64000, 64000)  # Set Usb frame
        # self._handle.setDivisor(2)           # 60 Mhz Clock divider

    def write_register(self, register: int, value: int,
                       flush: bool = False) -> bytes:
        """Write Bytes to Register

        :param register: FTDI Register to write
        :param value: Bytestring
        :param flush: Instant write

        :returns: Bytestring with write header and data
        """
        logger.debug("Write Register %d Value %s", register, hex(value))

        data = [WRITE_ADRESS, register, 0x00, 0x01, value]

        if flush:
            self.write(bytes(data))

        return bytes(data)

    def write_registers(self, register: int, value: bytearray,
                        flush: bool = False) -> bytes:
        """Write Single Byte to Register

        :param register: FTDI Register to write
        :param value: Bytestring
        :param flush: Instant write

        :returns: Bytestring with write header and 1 Byte data
        """

        length = len(value)

        hbyte = length >> 8
        lbyte = length % 256

        data = bytearray([WRITE_ADRESS, register, hbyte, lbyte])
        data.extend(value)

        if flush:
            self.write(bytes(data))

        logger.debug("Write Register %d Value %s Data: %s", register, value, binascii.hexlify(data))

        return data

    def read_register(self, register: int, num: int = 1) -> bytes:
        """
        Read Single Byte from Register

        :param register: FTDI Register to read from
        :param num: Number of bytes to read

        :returns: Register value
        """

        hbyte = num >> 8
        lbyte = num % 256

        self.write(bytes([READ_ADRESS, register, hbyte, lbyte]))
        answer = self.read(num)

        logger.debug("Read Register %d Value 0x%s", register, answer.hex())

        return answer

    def gen_gecco_pattern(self, address: int, value: bytearray, clkdiv: int = 16) -> bytes:
        """
        Generate GECCO SR write pattern from bitvector

        :param address: PCB register
        :param value: Bytearray vector
        :param clkdiv: Clockdivider 0-65535

        :returns: Bytearray with GECCO configvector Header+Data
        """

        # Number of Bytes to write
        length = (len(value) * 3 + 20) * clkdiv

        hbyte = length >> 8
        lbyte = length % 256

        header = bytearray([WRITE_ADRESS, address, hbyte, lbyte])

        self.debug_print("GECCO Config", length, hbyte, lbyte, header, value)

        data = bytearray()

        # data
        for bit in value:
            pattern = SIN_GECCO if bit == 1 else 0

            data.extend([pattern, pattern | 1, pattern])

        # Load signal
        data.extend([LD_GECCO, 0x00])

        # Add 8 clocks
        data.extend([0x01, 0x00] * 8)

        data.extend([LD_GECCO, 0x00])

        data = self.__addbytes(data, clkdiv)

        # concatenate header+dataasic
        return b''.join([header, data])

    def gen_asic_pattern_part(self, value: bytearray, wload: bool, 
                              clkdiv: int = 8, readback_mode = False) -> bytes:
        """
        Generate ASIC SR write pattern from bitvector

        :param value: Bytearray vector
        :param wload: Send load signal
        :param clkdiv: Clockdivider 0-65535

        :returns: Bytearray with ASIC configvector Header+Data
        """

        # Number of Bytes to write

        if not readback_mode:
            length = (len(value) * 5 + 30) * clkdiv
        else:
            length = ((len(value)+1) * 5) * clkdiv

        logger.debug('Bytes to write: %d\n', length)

        hbyte = length >> 8
        lbyte = length % 256

        header = bytearray([WRITE_ADRESS, SR_ASIC_ADRESS, hbyte, lbyte])

        self.debug_print("ASIC Config", length, hbyte, lbyte, header, value)

        data, load = bytearray(), bytearray()

        if not readback_mode:
        # data
            for bit in value:
                pattern = SIN_ASIC if bit == 1 else 0

                data.extend([pattern, pattern | 1, pattern, pattern | 2, pattern]) # Generate double clocked pattern

            # Load signal
            if wload:
                load.extend([0x00, LD_ASIC, 0x00])

            data = self.__addbytes(data, clkdiv)
            data.extend(self.__addbytes(load, clkdiv * 10))

        else:
            data.extend([4 | 32, 4 | 33, 4|32, 4 | 34, 4|32])
            for bit in value:
                #data.extend([4 | 32, 4 | 33, 4, 4 | 2, 4])
                data.extend([4 , 4 | 1, 4, 4 | 2, 4])
            data = self.__addbytes(data, clkdiv)

        # concatenate header+data
        return b''.join([header, data])

    def gen_asic_pattern(self, value: bytearray, wload: bool, clkdiv: int = 8, 
                         readback_mode = False) -> list:
        """
        Split asic data in parts

        :param value: Bytearray vector
        :param wload: Send load signal
        :param clkdiv: Clockdivider 0-65535

        :returns: List of Bytearrays with ASIC configvector Header+Data
        """

        data = []

        if not readback_mode:
            logger.debug('Bytes to write: %d', (len(value) * 5 + 30) * clkdiv)
            max_value = int((65534/clkdiv - 30)/5)
        else:
            logger.debug('Bytes to write: %d', ((len(value) + 1) * 5) * clkdiv)
            max_value = int((65534/clkdiv)/5)-1

        length = len(value)

        while length >= max_value:
            data.append(self.gen_asic_pattern_part(value[:max_value], False, clkdiv, readback_mode))
            value=value[max_value + 1:]
            length -= max_value
        else:
            data.append(self.gen_asic_pattern_part(value, wload, clkdiv, readback_mode))

        return data

    def gen_tdac_pattern(self, value: bytearray, wload: bool,
                         clkdiv: int = 8, readback_mode=False) -> bytes:
        """
        Generate TDAC SR write pattern from bitvector

        :param value: Bytearray vector
        :param wload: Send load signal
        :param clkdiv: Clockdivider 0-65535

        :returns: Bytearray with ASIC configvector Header+Data
        """

        # Number of Bytes to write

        if not readback_mode:
            length = (len(value) * 5 + 30) * clkdiv
        else:
            length = ((len(value) + 1) * 5) * clkdiv

        logger.debug('Bytes to write: %d\n', length)

        hbyte = length >> 8
        lbyte = length % 256

        header = bytearray([WRITE_ADRESS, SR_ASIC_ADRESS, hbyte, lbyte])

        self.debug_print("ASIC Config", length, hbyte, lbyte, header, value)

        data, load = bytearray(), bytearray()

        if not readback_mode:
            # data
            for bit in value:
                pattern = SIN_ASIC if bit == 1 else 0

                data.extend([pattern, pattern | 1, pattern, pattern | 2, pattern])  # Generate double clocked pattern

            # Load signal
            if wload:
                load.extend([0x00, LD_TDAC_ASIC, 0x00])

            data = self.__addbytes(data, clkdiv)
            data.extend(self.__addbytes(load, clkdiv * 10))

        """else:
            data.extend([4 | 32, 4 | 33, 4 | 32, 4 | 34, 4 | 32])
            for bit in value:
                # data.extend([4 | 32, 4 | 33, 4, 4 | 2, 4])
                data.extend([4, 4 | 1, 4, 4 | 2, 4])
            data = self.__addbytes(data, clkdiv) """

        # concatenate header+data
        return b''.join([header, data])

    def get_configregister(self):
        """
        Get SPI config register value

        :returns: SPI config register value
        """
        return int.from_bytes(self.read_register(0), 'big')


    def chip_reset(self) -> None:
        """
        Reset SPI
        Set res_n to 0 for 1s
        res_n is connected to FTDI Reg0: Bit: 4
        """
        # Set Reset bits 1
        configregister = self.set_bit(self.get_configregister(), 4)
        self.write_register(0, configregister, True)
        time.sleep(0.1)
        # Set Reset bits and readback bit 0
        configregister = self.clear_bit(self.get_configregister(), 4)
        self.write_register(0, configregister, True)
