# -*- coding: utf-8 -*-
""""""
"""
Created on Tue Jul 12 20:07:13 2021

@author: Nicolas Striebig
"""
from time import sleep

SPI_SR_CMD = 0x30

SPI_SR_SIN = 0x80
SPI_SR_LD = 0xff

SPI_CONFIG = 0x15
SPI_CLKDIV = 0x16

SPI_WRITE_REG = 23
SPI_READ_REG = 24


class Spi:
    """
    Nexys SPI Communication

    Registers:
    | SPI_Config Register 21 (0x15)
        | 0 Write FIFO reset
        | 1	Write FIFO empty flag (read-only)
        | 2	Write FIFO full flag (read-only)
        | 3	Read FIFO reset
        | 4	Read FIFO empty flag (read-only)
        | 5	Read FIFO full flag (read-only)
        | 6	SPI Readback Enable
        | 7	SPI module reset
    | SPI_CLKDIV Register 22
    | SPI_Write Register 23
    | SPI_Read Register 24
    """
    def __init__(self):
        self._spi_clkdiv = 16

    def readout(self):
        pass

    @staticmethod
    def set_bit(value, bit):
        return value | (1 << bit)

    @staticmethod
    def clear_bit(value, bit):
        return value & ~(1 << bit)

    @staticmethod
    def asic_spi_vector(value: bytearray, load: int) -> bytes:
        """
        Write ASIC config via SPI

        :param value: Bytearray vector
        :param load: Load signal

        :returns: SPI ASIC config pattern
        """

        # Number of Bytes to write
        length = len(value) * 5 + 4

        print("\n SPI Write Asic Config\n===============================")
        print(f"Length: {length}\n")
        print(f"Data ({len(value)} Bits): {value}\n")

        # Write SPI SR Command to set MUX
        data = bytearray([SPI_SR_CMD])

        # data
        for bit in value:
            sin = SPI_SR_SIN if bit == 1 else 0

            data.extend([sin])

        # Load signal
        i = 0
        if load:
            while i < 4:
                data.extend([SPI_SR_LD])
                i += 1

        return data

    @property
    def spi_clkdiv(self):
        """SPI Clockdivider"""

        return self._spi_clkdiv

    @spi_clkdiv.setter
    def spi_clkdiv(self, clkdiv: int):

        if 0 <= clkdiv <= 65535:
            self._spi_clkdiv = clkdiv
            self.write_register(SPI_CLKDIV, clkdiv, True)

    def spi_enable(self, enable: bool = True):
        """
        Enable SPI by setting reset bits low

        Set SPI Reset bits to 0
        """
        configregister = int.from_bytes(self.read_register(SPI_CONFIG), 'big')

        # Set Reset bits 1
        if enable:
            configregister = self.clear_bit(configregister, 7)
        else:
            configregister = self.set_bit(configregister, 7)

        print(f'Configregister: {hex(configregister)}')
        self.write_register(SPI_CONFIG, configregister, True)

    def spi_reset(self):
        """
        Reset SPI by setting reset bits low

        Set SPI Reset bits to 0
        """

        reset_bits = [0, 3]

        for bit in reset_bits:

            configregister = int.from_bytes(self.read_register(SPI_CONFIG), 'big')

            # Set Reset bits 1
            configregister = self.set_bit(configregister, bit)
            self.write_register(SPI_CONFIG, configregister, True)

            configregister = int.from_bytes(self.read_register(SPI_CONFIG), 'big')

            # Set Reset bits and readback bit 0
            configregister = self.clear_bit(configregister, bit)
            self.write_register(SPI_CONFIG, configregister, True)

    def direct_write_spi(self, data: bytes) -> None:
        """
        Direct write to SPI Write Register

        :param data: Data
        """
        self.write_registers(SPI_WRITE_REG, data, True)

    def read_spi(self, num: int):

        return self.read_register(SPI_READ_REG, num)

    def write_spi(self, data: bytearray, buffersize=1023) -> None:
        """
        Write to Nexys SPI Write FIFO

        :param data: Bytearray vector
        :param buffersize: BUffersize
        """
        waiting = True
        i = 0
        writebuffer = bytearray()
        counter = buffersize / 3

        # WrFIFO bit positons in spi_config register 0x21
        compare_empty = 2
        compare_full = 4

        # Check if WrFIFO is Empty
        while waiting:

            # Convert Hex string to int
            result = int.from_bytes(self.read_register(SPI_CONFIG), 'big')

            # Wait until WrFIFO empty
            if result & compare_empty:
                waiting = False
            else:
                sleep(0.005)

        while i < len(data):

            if counter > 0:
                # print(f'print data[i]:{data[i]}\n')

                writebuffer += bytearray([data[i]])

                i += 1
                counter -= 1
                if (i % 5) == 4:
                    print(f'Writebuffer: {writebuffer}\n')
                    self.direct_write_spi(bytes(writebuffer))
                    writebuffer = bytearray()

            else:
                result = int.from_bytes(self.read_register(SPI_CONFIG), 'big')

                if result & compare_empty:
                    counter = buffersize / 3
                elif not result & compare_full:
                    counter = 1