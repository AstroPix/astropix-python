# -*- coding: utf-8 -*-
""""""
"""
Created on Fri Jun 25 16:10:45 2021

@author: Nicolas Striebig

"""
import ftd2xx as ftd
import sys

from modules.spi import Spi

READ_ADRESS = 0x00
WRITE_ADRESS = 0x01

SR_ASIC_ADRESS = 0x00

SIN_ASIC = 0x04
LD_ASIC = 0x08

SIN_GECCO = 0x02
LD_GECCO = 0x04

NEXYS_USB_DESC = b'Digilent USB Device A'
NEXYS_USB_SER = b'210276'


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
            data.extend(bytearray([byte]) * clkdiv)

        return data

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

            else:
                self.close()
                raise NameError

        except NameError:
            print(f'Unknown Device with index {index}')
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
            print('No Devices found')
            sys.exit(1)

        # iterate through list and open device, if found
        for index, value in enumerate(device_desc):
            if value == NEXYS_USB_DESC:
                if device_serial[index].startswith(NEXYS_USB_SER):
                    self._handle = ftd.open(index)
                    self.__setup()

                    print("\u001b[32mDigilent USB A opened\n \u001b[0m")

                    # Return handle
                    return self._handle

        print('Nexys not found')
        return False

    def write(self, value: bytes) -> None:
        """
        Direct write to FTDI chip

        Use with caution!

        :param value: Bytestring to write
        """
        try:
            # split large vectors into multiple parts
            while (len(value) > 64000):
                print("Split writevector in parts")
                self._handle.write(value[0:63999])
                value = value [64000:]

            self._handle.write(value)
        except AttributeError:
            print('Nexys Write Error')

    def read(self, num: int) -> bytes:
        """
        Direct read from FTDI chip

        :param num: Number of Bytes to read
        """
        try:
            return self._handle.read(num)
        except AttributeError:
            print('Nexys Read Error')

    def close(self) -> None:
        """Close connection"""

        self._handle.close()

    def __setup(self) -> None:
        """Set FTDI USB connection settings"""

        self._handle.setTimeouts(1000, 500)  # Timeout RX,TX
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
        # print(f"Write Register {register} Value {hex(value)}")

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
        # print(f"Write Register {register} Value {hex(value)}")
        length = len(value)

        hbyte = length >> 8
        lbyte = length % 256

        data = bytearray([WRITE_ADRESS, register, hbyte, lbyte]) + value

        if flush:
            self.write(bytes(data))

        print(f'Write Registers: {data}\n')
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
        print(f"Read Register {register} Value 0x{answer.hex()}")

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

        print("\nWrite GECCO Config\n===============================")
        print(f"Length: {length} hByte: {hbyte} lByte: {lbyte}\n")
        print(f"Header: 0x{header.hex()}")
        print(f"Data ({len(value)} Bits): 0b{value.bin}\n")

        bit, data = 0, bytearray()

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

    def gen_asic_pattern(self, value: bytearray, wload: bool, clkdiv: int = 8) -> bytes:
        """
        Generate ASIC SR write pattern from bitvector

        :param value: Bytearray vector
        :param wload: Send load signal
        :param clkdiv: Clockdivider 0-65535

        :returns: Bytearray with ASIC configvector Header+Data
        """

        # Number of Bytes to write
        length = (len(value) * 5 + 30) * clkdiv

        print(f'Bytes to write: {length}\n')

        hbyte = length >> 8
        lbyte = length % 256

        header = bytearray([WRITE_ADRESS, SR_ASIC_ADRESS, hbyte, lbyte])

        print("\nWrite Asic Config\n===============================")
        print(f"Length: {length} hByte: {hbyte} lByte: {lbyte}\n")
        print(f"Header: 0x{header.hex()}")
        print(f"Data ({len(value)} Bits): 0b{value.bin}\n")

        bit, data, load = 0, bytearray(), bytearray()

        # data
        for bit in value:
            pattern = SIN_ASIC if bit == 1 else 0

            # Generate double clocked pattern
            data.extend([pattern, pattern | 1, pattern, pattern | 2, pattern])

        # Load signal
        if wload:
            load.extend([0x00, LD_ASIC, 0x00])

        data = self.__addbytes(data, clkdiv)
        data.extend(self.__addbytes(load, clkdiv * 10))

        # concatenate header+data
        return b''.join([header, data])
