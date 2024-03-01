import logging
import numpy as np
from scipy.optimize import curve_fit

from modules.setup_logger import logger


logger = logging.getLogger(__name__)


class Analysis:
    @staticmethod
    def scurve_fit(x: list[int], y: list[int], x_new: list[int], hightolow: bool = True, init: bool = False, **kwargs):

        x_0 = kwargs.get('x_0', np.median(x))
        print(x_0)

        # Init values
        if hightolow:
            p_0 = [y.max(), x_0, -100, y.min()]
        else:
            p_0 = [y.max(), x_0, 100, y.min()]

        print(f'p_0: {p_0}')
        if not init:
            popt, pcov = curve_fit(Analysis.sigmoid, x, y, p_0, method='dogbox')  # method='lm'
            logger.info('Fitting params: %s Std. fit error: %s ', popt, np.sqrt(np.diag(pcov)))
            return Analysis.sigmoid(x_new, *popt)
        else:
            return Analysis.sigmoid(x_new, *p_0)

    @staticmethod
    def sigmoid(x, L, x0, k, b):
        y = L / (1 + np.exp(-k * (x - x0))) + b
        return (y)