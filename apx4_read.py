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


from astropix import astropixRun
import os
import time
import logging
import argparse

from core.fmt import AstroPixReadout, FileHeader, AstroPixBinaryFile, AstroPix4Hit



def setup_logger(level: str, file_path: str = None):
    """Setup the logger.

    .. warning::

        This should probably be factored out in a module that all the scripts
        ca use, rather than coding the same thing over and over again.

    Arguments
    ---------
    level : str
        The logging level (D, I, W, E, C)

    file_path : str (optional)
        The path to the output log file.
    """
    _logging_dict = {'D': logging.DEBUG, 'I': logging.INFO, 'W': logging.WARNING,
                     'E': logging.ERROR, 'C': logging.CRITICAL}

    try:
        level = _logging_dict[level]
    except KeyError:
        raise RuntimeError(f'Unrecognized logging level "{level}"')

    formatter = logging.Formatter('%(asctime)s:%(msecs)d.%(name)s.%(levelname)s:%(message)s')
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logging.getLogger().addHandler(stream_handler)
    if file_path is not None:
        file_handler = logging.FileHandler(file_path)
        file_handler.setFormatter(formatter)
        logging.getLogger().addHandler(file_handler)

    logging.getLogger().setLevel(level)
    logger = logging.getLogger(__name__)
    return logger


def playback_file(file_path: str, num_hits: int = 10) -> None:
    """Small test code to playback a file.
    """
    with AstroPixBinaryFile(AstroPix4Hit).open(file_path) as input_file:
        print(f'\nStarting playback of binary file {file_path}...')
        print(f'File header: {input_file.header}')
        for i, hit in enumerate(input_file):
            if i < num_hits:
                print(hit)
            elif hit == num_hits:
                print('...')
        print(f'{i} hits found')


def main(args):
    """Configure and run an AstroPix 4 chip.
    """
    # A couple of hard-coded parameters---this is currently only supporting AstroPix v4!
    chip_version = 4
    ci_on_chip = True

    # Latch the start date and time---this will be used for naming the output products.
    start_datetime = time.strftime("%Y%m%d_%H%M%S")

    # Create the output folder.
    output_folder = os.path.join(args.outdir, start_datetime)
    os.makedirs(output_folder)

    # Setup the logger.
    log_file_name = f'{start_datetime}.log'
    log_file_path = os.path.join(output_folder, log_file_name)
    logger = setup_logger(args.loglevel, log_file_path)

    # Setup the data acquisition.
    logger.info('Configuring the chip...')
    astro = astropixRun(chipversion=args.chipVer, inject=args.inject)
    astro.asic_init(yaml=args.yaml, analog_col=args.analog)
    astro.init_voltages(vthreshold=args.threshold)

    # If injection, ensure injection pixel is enabled and initialize.
    if args.inject is not None:
        astro.enable_pixel(args.inject[1], args.inject[0])
        astro.init_injection(inj_voltage=args.vinj, onchip=ci_on_chip)

    # Enable final configuration.
    astro.enable_spi()
    astro.asic_configure()
    if chip_version == 4:
        astro.update_asic_tdac_row(0)
    logger.info('Chip fully configured!')

    # What is this doing?
    astro.dump_fpga()

    if args.inject is not None:
        astro.start_injection()

    # Save final configuration to output file
    ymlpathout=args.outdir +"/"+args.yaml+"_"+start_datetime+".yml"
    try:
        astro.write_conf_to_yaml(ymlpathout)
    except FileNotFoundError:
        ypath = args.yaml.split('/')
        ymlpathout=args.outdir+"/"+ypath[1]+"_"+start_datetime+".yml"
        astro.write_conf_to_yaml(ymlpathout)

    # Do we really need a second call to this?
    astro.dump_fpga()

    # Setup exit conditions
    if args.maxtime is not None:
        stop_time = time.time() + args.maxtime * 60.
    else:
        stop_time = None
    if args.maxruns is not None:
        max_num_readouts = args.maxruns
    else:
        max_num_readouts = None

    # Preparation of the file header. Note we can put literally anything that is
    # serializable in the header, and for the time being we are just grabbing
    # anything that used to end up in the original log (i.e., data) file.
    # This is an area where we might want to put some thought as to what the most
    # sensible way to handle things is.
    header_data = {}
    header_data['conf'] = astro.get_header_data()
    header_data['args'] = args.__dict__
    header = FileHeader(header_data)

    # Open the output file and write the header.
    data_file_name = f'{start_datetime}_data.apx'
    data_file_path = os.path.join(output_folder, data_file_name)
    logger.info(f'Opening binary file {data_file_path}...')
    output_file = open(data_file_path, 'wb')
    header.write(output_file)

    # Start the event loop.
    # By enclosing the main loop in try/except we are able to capture keyboard interupts cleanly
    num_readouts = 0
    try:
        while 1:
            # Check the stop conditions.
            if stop_time is not None and time.time() >= stop_time:
                break
            if max_num_readouts is not None and num_readouts >= max_num_readouts:
                break
            # Go ahead and readout data.
            readout_data = astro.get_readout()
            if readout_data:
                readout = AstroPixReadout(readout_data, time.time())
                logger.debug(readout)
                for hit in readout.hits:
                    logger.debug(hit)
                    hit.write(output_file)
                num_readouts += 1

    # Ends program cleanly when a keyboard interupt is sent.
    except KeyboardInterrupt:
        logger.info('Keyboard interupt, exiting...')

    output_file.close()
    logger.info('Output file closed.')

    # Teardown the hardware.
    if args.inject is not None:
        astro.stop_injection()
    astro.close_connection()
    logger.info("Program terminated successfully!")

    playback_file(data_file_path)




if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='Astropix 4 simple run control')
    parser.add_argument('-o', '--outdir', default='.', required=False,
                    help='Output Directory for all data files')
    parser.add_argument('-y', '--yaml', action='store', required=False, type=str, default = 'testconfig',
                    help = 'filepath (in config/ directory) .yml file containing chip configuration. Default: config/testconfig.yml (All pixels off)')
    parser.add_argument('-i', '--inject', action='store', default=None, type=int, nargs=2,
                    help =  'Turn on injection in the given row and column. Default: No injection')
    parser.add_argument('-v','--vinj', action='store', default = None, type=float,
                    help = 'Specify injection voltage (in mV). DEFAULT None (uses value in yml)')
    parser.add_argument('-a', '--analog', action='store', required=False, type=int, default = 0,
                    help = 'Turn on analog output in the given column. Default: Column 0.')
    parser.add_argument('-t', '--threshold', type = float, action='store', default=None,
                    help = 'Threshold voltage for digital ToT (in mV). DEFAULT value in yml OR 100mV if voltagecard not in yml')
    parser.add_argument('-r', '--maxruns', type=int, action='store', default=None,
                    help = 'Maximum number of readouts')
    parser.add_argument('-M', '--maxtime', type=float, action='store', default=None,
                    help = 'Maximum run time (in minutes)')
    parser.add_argument('-L', '--loglevel', type=str, choices = ['D', 'I', 'E', 'W', 'C'], action="store", default='I',
                    help='Set loglevel used. Options: D - debug, I - info, E - error, W - warning, C - critical. DEFAULT: I')

    parser.add_argument
    args = parser.parse_args()

    main(args)
