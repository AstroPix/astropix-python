# -*- coding: utf-8 -*-
""""""
"""
Created on Tue Jul 12 20:07:13 2021

@author: Nicolas Striebig
"""
import logging
from bitstring import BitArray
from modules.setup_logger import logger


# SR
SPI_SR_BROADCAST    = 0x7E
SPI_SR_BIT0         = 0x00
SPI_SR_BIT1         = 0x01
SPI_SR_LOAD         = 0x03
SPI_EMPTY_BYTE      = 0x00

# Registers
SPI_CONFIG_REG      = 0x15
SPI_CLKDIV_REG      = 0x16
SPI_WRITE_REG       = 0x17
SPI_READ_REG        = 0x18
SPI_READBACK_REG    = 0x3C
SPI_READBACK_REG_CONF = 0x3D

# Daisychain 3bit Header + 5bit ID
SPI_HEADER_EMPTY    = 0b001 << 5
SPI_HEADER_ROUTING  = 0b010 << 5
SPI_HEADER_SR       = 0b011 << 5

# SPI configreg
SPI_WRITE_FIFO_RESET = 0b1 << 0
SPI_WRITE_FIFO_EMPTY = 0b1 << 1
SPI_WRITE_FIFO_FULL  = 0b1 << 2
SPI_READ_FIFO_RESET  = 0b1 << 3
SPI_READ_FIFO_EMPTY  = 0b1 << 4
SPI_READ_FIFO_FULL   = 0b1 << 5
SPI_READBACK_ENABLE  = 0b1 << 6
SPI_MODULE_RESET     = 0b1 << 7

logger = logging.getLogger(__name__)


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

    @staticmethod
    def set_bit(value, bit):
        return value | (1 << bit)

    @staticmethod
    def clear_bit(value, bit):
        return value & ~(1 << bit)

    def get_spi_config(self) -> int:
        return int.from_bytes(self.read_register(SPI_CONFIG_REG), 'big')

    def get_sr_readback_config(self) -> int:
        return int.from_bytes(self.read_register(SPI_READBACK_REG_CONF), 'big')

    def asic_spi_vector(self, value: bytearray, load: bool, n_load: int = 10, broadcast: bool = True, chipid: int = 0) -> bytearray:
        """
        Write ASIC config via SPI

        :param value: Bytearray vector
        :param load: Load signal
        :param n_load: Length of load signal

        :param broadcast: Enable Broadcast
        :param chipid: Set chipid if !broadcast

        :returns: SPI ASIC config pattern
        """

        # Number of Bytes to write
        length = len(value) * 5 + 4

        logger.info("SPI Write Asic Config\n")
        logger.debug("Length: %d\n Data (%db): %s\n", length, len(value), value)

        # Write SPI SR Command to set MUX
        if broadcast:
            data = bytearray([SPI_SR_BROADCAST])
        else:
            data = bytearray([SPI_HEADER_SR | chipid])

        # data
        for bit in value:

            sin = SPI_SR_BIT1 if bit == 1 else SPI_SR_BIT0

            data.append(sin)

        # Append Load signal and empty bytes
        if load:

            data.extend([SPI_SR_LOAD] * n_load)

            data.extend([SPI_EMPTY_BYTE] * n_load)

        return data

    @property
    def spi_clkdiv(self):
        """SPI Clockdivider"""

        return self._spi_clkdiv

    @spi_clkdiv.setter
    def spi_clkdiv(self, clkdiv: int):

        if 0 <= clkdiv <= 65535:
            self._spi_clkdiv = clkdiv
            self.write_register(SPI_CLKDIV_REG, clkdiv, True)

    def spi_enable(self, enable: bool = True) -> None:
        """
        Enable or disable SPI

        Set SPI Reset bit to 0/1 active-low
        :param enable: Enable
        """
        configregister = self.get_spi_config()

        # Set Reset bits 1
        configregister = self.clear_bit(configregister, 7) if enable else self.set_bit(configregister, 7)

        logger.debug('Configregister: %s', hex(configregister))
        self.write_register(SPI_CONFIG_REG, configregister, True)

    def spi_reset(self) -> None:
        """
        OBSOLETE: Reset SPI
        Resets SPI module and FIFOs
        """
        
        logger.warning("spi_reset() is obsolete, use spi_reset_fpga() instead")
        self.spi_reset_fpga_readout()

    def spi_reset_fpga_readout(self) -> None:
        """
        Reset SPI

        Resets SPI module and FIFOs
        """

        reset_bits = [0, 3]

        for bit in reset_bits:

            configregister = self.get_spi_config()

            # Set Reset bits 1
            configregister = self.set_bit(configregister, bit)
            self.write_register(SPI_CONFIG_REG, configregister, True)

            configregister = self.get_spi_config()

            # Set Reset bits and readback bit 0
            configregister = self.clear_bit(configregister, bit)
            self.write_register(SPI_CONFIG_REG, configregister, True)

    def sr_readback_reset(self) -> None:
        """
        Reset SPI

        Resets SPI module and FIFOs
        """

        reset_bits = [0]

        for bit in reset_bits:

            configregister = self.get_sr_readback_config()

            # Set Reset bits 1
            configregister = self.set_bit(configregister, bit)
            self.write_register(SPI_READBACK_REG_CONF, configregister, True)

            configregister = self.get_sr_readback_config()

            # Set Reset bits and readback bit 0
            configregister = self.clear_bit(configregister, bit)
            self.write_register(SPI_READBACK_REG_CONF, configregister, True)

    def direct_write_spi(self, data: bytes) -> None:
        """
        Direct write to SPI Write Register

        :param data: Data
        """
        self.write_registers(SPI_WRITE_REG, data, True)

    def read_spi(self, num: int):
        """
        Direct Read from SPI Read Register

        :param num: Number of Bytes

        :returns: SPI Read data
        """

        return self.read_register(SPI_READ_REG, num)

    def read_spi_readback(self, num: int):
        """
        Direct Read from SPI Read Register

        :param num: Number of Bytes

        :returns: SPI Read data
        """

        return self.read_register(SPI_READBACK_REG, num)

    def read_spi_readoutmode(self):
        """ Continous readout """
        pass

    def read_spi_fifo(self, max_reads: int = 1) -> bytearray:
        """ Read Data from SPI FIFO until empty
        :param max_reads: Max read cycles
        :returns: SPI read stream
        """
        read_stream = bytearray()
        readcount = 0

        while not (self.get_spi_config() & SPI_READ_FIFO_EMPTY) and readcount<max_reads:
            #readbuffer = self.read_spi(4096)
            readbuffer = self.read_spi(2048)
            read_stream.extend(readbuffer)
            readcount += 1

        return read_stream

    def read_spi_fifo_readback(self) -> bytearray:
        """ Read Data from SPI FIFO until empty """

        read_stream = bytearray()

        while not self.get_sr_readback_config() & 16:
            readbuffer = self.read_spi_readback(8)

            read_stream.extend(readbuffer)

            sleep(0.01)

        return read_stream

    def write_spi_bytes(self, n_bytes: int) -> None:
        """
        Write to SPI for readout

        :param n_bytes: Number of Bytes
        """

        if n_bytes > 64000:
            #n_bytes = 64000
            logger.warning("Cannot write more than 64000 Bytes")

        logger.info("SPI: Write %d Bytes", 8 * n_bytes + 4)
        self.write_spi(bytearray([SPI_HEADER_EMPTY] * n_bytes * 8), False, 8191)

    def send_routing_cmd(self) -> None:
        """
        Send routing cmd

        """
        logger.info("SPI: Send routing cmd")
        self.write_spi(bytearray([SPI_HEADER_EMPTY, 0, 0, 0, 0, 0, 0, 0]), False)

    def write_spi(self, data: bytearray, MSBfirst: bool = True) -> None:
        """
        Write to Nexys SPI Write FIFO

        :param data: Bytearray vector
        :param MSBfirst: SPI MSB first
        :param buffersize: Buffersize
        """

        if not MSBfirst:
           for index in range(len(data)):
                data[index] = int(format(data[index], '08b')[::-1], 2)

        logger.debug('SPIdata: %s', data)

        i = 0
        # Wait until WrFIFO is Empty
        while not self.get_spi_config() & SPI_WRITE_FIFO_EMPTY:
            continue

        while i < len(data):
            if not self.get_spi_config() & SPI_WRITE_FIFO_FULL:
                self.direct_write_spi(bytes(bytearray(data[i:(i + 16)])))
                logger.debug('Write SPI bytes %d:%d', i, i + 16)
                i += 16