# -*- coding: utf-8 -*-
""""""
"""
Created on Sun Jun 27 21:03:43 2021

@author: Nicolas Striebig
"""

import logging

from core.nexysio import Nexysio
from modules.setup_logger import logger

PG_RESET    = 2
PG_SUSPEND  = 3
PG_WRITE    = 4
PG_OUTPUT   = 5
PG_ADDRESS  = 6
PG_DATA     = 7


logger = logging.getLogger(__name__)

class Injectionboard(Nexysio):
    """Sets injection setting for GECCO Injectionboard"""

    def __init__(self, handle, onchip=False) -> None:

        self._handle = handle

        self._period = 0
        self._cycle = 0
        self._clkdiv = 0
        self._initdelay = 0
        self._pulsesperset = 0
        self._onchip = onchip

    def __patgenreset(self, reset: bool) -> bytes:
        return self.write_register(PG_RESET, reset)

    def __patgensuspend(self, suspend: bool) -> bytes:
        return self.write_register(PG_SUSPEND, suspend)

    @property
    def period(self) -> int:
        """Injection period"""

        return self._period

    @period.setter
    def period(self, period: int) -> None:
        if 0 <= period <= 255:
            self._period = period

    @property
    def cycle(self) -> int:
        """Injection #pulses"""

        return self._cycle

    @cycle.setter
    def cycle(self, cycle: int) -> None:
        if 0 <= cycle <= 65535:
            self._cycle = cycle

    @property
    def clkdiv(self) -> int:
        """Injection clockdivider"""

        return self._clkdiv

    @clkdiv.setter
    def clkdiv(self, clkdiv: int) -> None:
        if 0 <= clkdiv <= 65535:
            self._clkdiv = clkdiv

    @property
    def initdelay(self) -> int:
        """Injection initdelay"""

        return self._initdelay

    @initdelay.setter
    def initdelay(self, initdelay: int) -> None:
        if 0 <= initdelay <= 65535:
            self._initdelay = initdelay

    @property
    def pulsesperset(self) -> int:
        """Injection pulses/set"""

        return self._pulsesperset

    @pulsesperset.setter
    def pulsesperset(self, pulsesperset: int) -> None:
        if 0 <= pulsesperset <= 255:
            self._pulsesperset = pulsesperset

    def __patgen(
            self, period: int,
            cycle: int,
            clkdiv: int,
            delay: int) -> bytearray:
        """Generate vector for injectionpattern

        :param period: Set injection period 0-255
        :param cycle: Set injection cycle 0-65535
        :param clkdiv: Set injection clockdivider 0-65535
        :param delay: Set injection pulse delay 0-65535

        :returns: patgen vector
        """

        data = bytearray()
        timestamps = [1, 3, 0, 0, 0, 0, 0, 0]

        for i, val in enumerate(timestamps):
            data.extend(self.__patgenwrite(i, val))

        # Set period
        data.extend(self.__patgenwrite(8, period))

        # Set flags
        data.extend(self.__patgenwrite(9, 0b010100))

        # Set runlength
        data.extend(self.__patgenwrite(10, cycle >> 8))
        data.extend(self.__patgenwrite(11, cycle % 256))

        # Set initial delay
        data.extend(self.__patgenwrite(12, delay >> 8))
        data.extend(self.__patgenwrite(13, delay % 256))

        # Set clkdiv
        data.extend(self.__patgenwrite(14, clkdiv >> 8))
        data.extend(self.__patgenwrite(15, clkdiv % 256))

        return data

    def __patgenwrite(self, address: int, value: int) -> bytearray:
        """Subfunction of patgen()

        :param address: Register address
        :param value: Value to append to writebuffer
        """

        data = bytearray()

        data.extend(self.write_register(PG_ADDRESS, address))
        data.extend(self.write_register(PG_DATA, value))
        data.extend(self.write_register(PG_WRITE, 1))
        data.extend(self.write_register(PG_WRITE, 0))

        return data

    def __configureinjection(self) -> bytes:
        """
        Generate injection vector for set output, pattern and pulses/set

        :returns: config vector
        """

        logger.info("\nWrite Injection Config\n===============================")

        if(self._onchip):
            output = self.write_register(PG_OUTPUT, 2)
        else:
            output = self.write_register(PG_OUTPUT, 1)
            
        patgenconfig = self.__patgen(self.period, self.cycle, self.clkdiv, self.initdelay)
        pulses = self.__patgenwrite(7, self.pulsesperset)

        data = output + patgenconfig + pulses
        logger.debug(f"Injection vector({len(data)} Bytes): 0x{data.hex()}\n")

        return bytes(data)

    def __start(self) -> bytes:
        """
        Start injection

        :returns: start vector
        """

        data = bytearray()

        data.extend(self.__patgensuspend(True))
        data.extend(self.__patgenreset(True))
        data.extend(self.__patgenreset(False))
        data.extend(self.__patgensuspend(False))

        logger.debug(f"Start inj({len(data)} Bytes): 0x{data.hex()}\n")

        return bytes(data)

    def __stop(self) -> bytes:
        """
        Stop injection

        :returns: stop vector
        """

        data = bytearray()

        data.extend(self.__patgensuspend(True))
        data.extend(self.__patgenreset(True))

        logger.debug(f"Stop inj({len(data)} Bytes): 0x{data.hex()}\n")

        return bytes(data)

    def update_inj(self) -> None:
        """Update injectionboard"""

        # Stop injection
        self.write(self.__stop())

        # Configure injection
        self.write(self.__configureinjection())

    def start(self) -> None:
        """Start injection"""

        # Stop injection
        self.write(self.__stop())

        # update inj
        self.update_inj()

        # Start Injection
        self.write(self.__start())

        logger.info("Start injection")

    def stop(self) -> None:
        """Stop injection"""

        self.write(self.__stop())

        logger.info("Stop injection")
