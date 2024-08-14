import time
from tqdm.auto import tqdm
import numpy as np
import logging
import binascii
import pandas as pd

from modules.asic import Asic
from modules.nexysio import Nexysio
from modules.decode import Decode
from modules.setup_logger import logger

logger = logging.getLogger(__name__)


class Scan(Asic, Nexysio):

    def __init__(self, handle=0) -> None:
        self._handle = handle

    @staticmethod
    def inj_scan_old(asic, vboard, injboard, nexys, file, **kwargs):

        noise_run = kwargs.get('noise_run', False)
        vinj_start = kwargs.get('vinj_start', 0.1)
        vinj_stop = kwargs.get('vinj_stop', 1.0)
        stepsize = kwargs.get('stepsize', 0.01)
        steps = kwargs.get('steps', 10)
        counts = kwargs.get('counts', 5)
        up = kwargs.get('up', True)
        th_up = kwargs.get('th_up', 1)
        th_down = kwargs.get('th_down', 10)
        vboard_Vth = kwargs.get('vth', 1.1)
        vboard_BL = kwargs.get('vboard_BL', 1)
        vboard_VCasc2 = kwargs.get('vboard_VCasc2', 1.1)
        vboard_Vminus = kwargs.get('vboard_Vminus', 1)
        set_col = kwargs.get('col')
        set_row = kwargs.get('row')

        decode = Decode()

        vboard.dacvalues = (8, [0, 0, vboard_VCasc2, vboard_BL, 0, 0, vboard_Vminus, vboard_Vth])
        vboard.update_vb()

        df = pd.DataFrame(columns=['scan_col', 'scan_row', 'run', 'step', 'vinj', 'id',
                                   'payload', 'location', 'col', 'timestamp', 'tot_total'])

        for col in tqdm(range(asic.num_cols), position=0, leave=False, desc='Column'):

            if 'col' in kwargs and set_col != col:
                continue

            asic.reset_recconfig()
            asic.enable_ampout_col(col)  # enable ampout for current col

            if not noise_run:
                asic.enable_inj_col(col)

            for row in tqdm(range(asic.num_rows), position=1, leave=False, desc='Row   '):

                if 'row' in kwargs and set_row != row:
                    continue

                if not noise_run:
                    asic.enable_inj_row(row)

                asic.enable_pixel(col, row)
                asic.update_asic()

                average_per_step = np.zeros(steps)

                for step in tqdm(range(steps), position=2, leave=False, desc='Step  '):

                    if up:
                        injboard.amplitude = vinj_start + stepsize * step
                    else:
                        injboard.amplitude = vinj_stop - stepsize * step

                    injboard.update_inj_amplitude()

                    nexys.spi_reset()
                    if asic.chipversion == 2:
                        nexys.chip_reset()
                    time.sleep(0.1)

                    hit_per_iter = np.zeros(counts)

                    for count in tqdm(range(counts), position=3, leave=False, desc='Count '):
                        if up:
                            tqdm.write(f"Pixel Col: {col} Row: {row} Vinj: {vinj_start+stepsize*step} Run: {count}")
                            logger.info("Pixel Col: %d Row: %d Vth: %f Run: %d", col, row,
                                        vinj_start + stepsize * step, count)
                        else:
                            tqdm.write(f"Pixel Col: {col} Row: {row} Vinj: {vinj_stop-stepsize*step} Run: {count}")
                            logger.info("Pixel Col: %d Row: %d Vth: %f Run: %d", col, row,
                                        vinj_stop - stepsize * step, count)

                        if not (noise_run):
                            injboard.start()
                            time.sleep(2)
                            injboard.stop()

                        readout = nexys.read_spi_fifo(20)
                        nexys.spi_reset()

                        logger.debug('%s', binascii.hexlify(readout))

                        # Decode
                        list_hits = decode.hits_from_readoutstream(readout)
                        decoded = decode.decode_astropix2_hits(list_hits)
                        print(decoded.to_string())
                        decoded = decoded.assign(scan_row=row, scan_col=col,
                                                 run=count, step=step, vinj=injboard.amplitude)
                        print(decoded.to_string())

                        df = pd.concat([df, decoded], axis=0, ignore_index=True)[df.columns]

                        tqdm.write('\x1b[0;31;40m{} Hits found!\x1b[0m'.format((len(list_hits))))
                        logger.info("%d Hits found!", len(list_hits))

                        hit_per_iter[count] = len(list_hits)

                    mean_hits_per_iter = np.mean(hit_per_iter)

                    logger.debug("average: %f", mean_hits_per_iter)
                    average_per_step[step] = mean_hits_per_iter

                    if mean_hits_per_iter <= th_up and up:
                        logger.debug("Break: avg. hits 0")
                        # break
                    elif mean_hits_per_iter >= th_down and not up:
                        logger.debug("Break: avg. hits > %f", th_down)
                        # break

                asic.disable_pixel(col, row)
                logger.info("avg. Hits per step %f", average_per_step)

                asic.disable_pixel(col, row)

        df.index.name = 'index'
        df.to_csv(file, mode='a')

    @staticmethod
    def scan_binsearch(asic, vboard, inj, nexys, file, **kwargs):

        scan_method = kwargs.get('scan_method', 'injection')
        noise_run = kwargs.get('noise_run', False)
        precision = kwargs.get('precision', 0.01)
        v_start = kwargs.get('v_start', 0)
        v_stop = kwargs.get('v_stop', 0.6)
        vinj_thscan = kwargs.get('vinj_thscan', 0.3)
        counts = kwargs.get('counts', 5)
        vboard_Vth = kwargs.get('vth', 1.15)
        vboard_Vthpmos = kwargs.get('vthpmos', 1.15)
        vboard_BL = kwargs.get('vboard_BL', 1)
        vboard_VCasc2 = kwargs.get('vboard_VCasc2', 1.1)
        vboard_Vminus = kwargs.get('vboard_Vminus', 0.7)
        set_col = kwargs.get('col')
        set_row = kwargs.get('row')
        inj_pulses = kwargs.get('inj_pulses', 100)
        v_vdda = kwargs.get('v_vdda', 1.8)
        v_vdd33 = kwargs.get('v_vdd33', 2.8)

        inj.pulsesperset = inj_pulses
        inj.cycle = 1
        inj.amplitude = vinj_thscan

        decode = Decode()

        if inj.onchip:
            asic.set_internal_vdac('thpix', vboard_Vth, v_vdda)
            asic.set_internal_vdac('thpmos', vboard_Vthpmos, v_vdda)
            asic.set_internal_vdac('vinj', vinj_thscan, v_vdda)
        else:
            vboard.dacvalues = (8, [vboard_Vthpmos, 0, vboard_VCasc2, vboard_BL, 0, 0, vboard_Vminus, vboard_Vth])
            vboard.vsupply = v_vdd33
            vboard.update_vb()

        readout = bytearray()

        df = pd.DataFrame(columns=['scan_col', 'scan_row', 'run', 'step', 'vinj', 'vth',
                                   'id', 'payload', 'location', 'col', 'timestamp', 'tot_total'])

        for col in tqdm(range(asic.num_cols), position=0, leave=False, desc='Column'):
            if 'col' in kwargs and set_col != col and set_col is not None:
                continue

            for row in tqdm(range(asic.num_rows), position=1, leave=False, desc='Row   '):
                if 'row' in kwargs and set_row != row and set_row is not None:
                    continue

                asic.reset_recconfig()

                if not noise_run:
                    asic.set_inj_row(row, True)
                    asic.set_inj_col(col, True)

                asic.enable_ampout_col(col)  # enable ampout for current col
                asic.set_pixel_comparator(col, row, True)
                asic.update_asic()

                step = 1

                start_temp = v_start
                stop_temp = v_stop

                measure_at_zero = True

                while (stop_temp - start_temp) >= precision:

                    if measure_at_zero:
                        if scan_method == 'injection':
                            v_bin = 0.0  # Additional point at min
                        elif scan_method == 'threshold':
                            v_bin = v_stop  # Additional point at max
                    else:
                        v_bin = np.round((start_temp + stop_temp) / 2, 4)

                    if scan_method == 'injection':
                        if inj.onchip:
                            asic.set_internal_vdac('vinj', v_bin, v_vdda)
                        else:
                            inj.amplitude = v_bin
                    elif scan_method == 'threshold':
                        if inj.onchip:
                            asic.set_internal_vdac('thpix', v_bin + vboard_BL, v_vdda)
                            asic.set_internal_vdac('thpmos', v_bin + vboard_BL, v_vdda)
                            asic.update()
                        else:
                            vboard.dacvalues = (8, [v_bin + vboard_BL,
                                                    0,
                                                    vboard_VCasc2,
                                                    vboard_BL,
                                                    0,
                                                    0,
                                                    vboard_Vminus,
                                                    v_bin + vboard_BL])
                            vboard.update_vb()

                    inj.stop()
                    nexys.spi_reset_fpga_readout()

                    hit_per_iter = np.zeros(counts)

                    for count in tqdm(range(counts), position=2, leave=False, desc='Count '):
                        tqdm.write(f"Pixel({col}, {row}) Vinj: {inj.amplitude} Vth: {vboard.dacvalues[7]} Run: {count}")
                        logger.info("Pixel Col: %d Row: %d Vinj: %f Vth: %f Run: %d",
                                    col, row, inj.amplitude, vboard.dacvalues[7], count)

                        if not noise_run:
                            inj.start()

                        time.sleep(6)  # TODO: adapt to injection settings

                        readout = nexys.read_spi_fifo(100)

                        logger.debug('%s', binascii.hexlify(readout))

                        # Decode
                        list_hits = decode.hits_from_readoutstream(readout)
                        decoded = decode.decode_astropix2_hits(list_hits)
                        decoded = decoded.assign(scan_row=row, scan_col=col,
                                                 run=count, step=step, vinj=inj.amplitude, vth=vboard.dacvalues[7])
                        print(decoded.to_string())

                        df = pd.concat([df, decoded], axis=0, ignore_index=True)[df.columns]

                        tqdm.write('\x1b[0;31;40m{} Hits found!\x1b[0m'.format((len(list_hits))))
                        logger.info("%d Hits found!", len(list_hits))

                        hit_per_iter[count] = len(list_hits)

                    mean_hits_per_iter = np.mean(hit_per_iter)
                    tqdm.write('\x1b[0;31;40m{} Average Hits found!\x1b[0m'.format(mean_hits_per_iter))

                    logger.debug("average: %f", mean_hits_per_iter)

                    # bin search
                    if not measure_at_zero:
                        if scan_method == 'injection':
                            if mean_hits_per_iter / 2 < inj_pulses / 2:
                                start_temp = v_bin
                            else:
                                stop_temp = v_bin
                        elif scan_method == 'threshold':
                            if mean_hits_per_iter / 2 > inj_pulses / 2:
                                start_temp = v_bin
                            else:
                                stop_temp = v_bin

                    measure_at_zero = False

                    step += 1

        df.index.name = 'index'
        df.to_csv(file, mode='a')