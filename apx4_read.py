"""
Updated version of beam_test.py using the astropix.py module

Author: Autumn Bauman 
Maintained by: Amanda Steinhebel, amanda.l.steinhebel@nasa.gov
"""

#from msilib.schema import File
#from http.client import SWITCHING_PROTOCOLS
from astropix import astropixRun
import modules.hitplotter as hitplotter
import os
import binascii
import time
import logging
import argparse

from core.fmt import AstroPixReadout, FileHeader, AstroPixBinaryFile, AstroPix4Hit

from modules.setup_logger import logger



  

def main(args):

    time_at_start=time.strftime("%Y%m%d_%H%M%S")
    output_folder = os.path.join(args.outdir, time_at_start)
    logger.info(f'Creating output folder {output_folder}...')
    os.makedirs(output_folder)

    # Prepare everything, create the object
    astro = astropixRun(chipversion=args.chipVer, inject=args.inject) 

    #Initiate asic with pixel mask as defined in yaml and analog pixel in row0 defined with input argument -a
    astro.asic_init(yaml=args.yaml, analog_col = args.analog)

    astro.init_voltages(vthreshold=args.threshold)     

    #If injection, ensure injection pixel is enabled and initialize
    if args.inject is not None:
        astro.enable_pixel(args.inject[1],args.inject[0])    
        astro.init_injection(inj_voltage=args.vinj, onchip=onchipBool)

    #Enable final configuration
    astro.enable_spi() 
    astro.asic_configure()


    if args.chipVer==4:
        astro.update_asic_tdac_row(0)
    logger.info("Chip configured")
    astro.dump_fpga()

    if args.inject is not None:
        astro.start_injection()

    max_errors = args.errormax
    i = 0
    errors = 0 # Sets the threshold 
    if args.maxtime is not None: 
        end_time=time.time()+(args.maxtime*60.)
    fname="" if not args.name else args.name+"_"

    # Save final configuration to output file    
    ymlpathout=args.outdir +"/"+args.yaml+"_"+time_at_start+".yml"
    try:
        astro.write_conf_to_yaml(ymlpathout)
    except FileNotFoundError:
        ypath = args.yaml.split('/')
        ymlpathout=args.outdir+"/"+ypath[1]+"_"+time_at_start+".yml"
        astro.write_conf_to_yaml(ymlpathout)

    astro.dump_fpga()

    data_file_name = f'{time_at_start}_data.apx'
    data_file_path = os.path.join(output_folder, data_file_name)
    logger.info(f'Opening binary file {data_file_path}...')

    output_file = open(data_file_path, 'wb')
    header_data = {}
    header_data['conf'] = astro.get_header_data()
    header_data['args'] = args.__dict__
    header = FileHeader(header_data)
    header.write(output_file)
    
    try: # By enclosing the main loop in try/except we are able to capture keyboard interupts cleanly
        while errors <= max_errors: # Loop continues 

            # This might be possible to do in the loop declaration, but its a lot easier to simply add in this logic
            if args.maxruns is not None:
                if i >= args.maxruns: break
            if args.maxtime is not None:
                if time.time() >= end_time: break
        
            readout_data = astro.get_readout()

            if readout_data:
                readout = AstroPixReadout(readout_data, time.time())
                logger.info(readout)
                for hit in readout.hits:
                    logger.info(hit)
                    hit.write(output_file)

    # Ends program cleanly when a keyboard interupt is sent.
    except KeyboardInterrupt:
        logger.info("Keyboard interupt. Program halt!")
    # Catches other exceptions
    except Exception as e:
        logger.exception(f"Encountered Unexpected Exception! \n{e}")
    finally:
        output_file.close()
        logger.info('Output file closed.')
        if args.inject is not None: astro.stop_injection()   
        astro.close_connection() # Closes SPI
        logger.info("Program terminated successfully")
    # END OF PROGRAM

    # Test: playback the file.
    with AstroPixBinaryFile(AstroPix4Hit).open(data_file_path) as input_file:
        print('\n\n')
        print('File header:', input_file.header)
        for hit in input_file:
            print(hit.tot_us)


    
if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='Astropix Driver Code')
    parser.add_argument('-n', '--name', default='', required=False,
                    help='Option to give additional name to output files upon running')

    parser.add_argument('-o', '--outdir', default='.', required=False,
                    help='Output Directory for all datafiles')

    parser.add_argument('-y', '--yaml', action='store', required=False, type=str, default = 'testconfig',
                    help = 'filepath (in config/ directory) .yml file containing chip configuration. Default: config/testconfig.yml (All pixels off)')

    parser.add_argument('-V', '--chipVer', default=2, required=False, type=int,
                    help='Chip version - provide an int')
    
    parser.add_argument('-s', '--showhits', action='store_true',
                    default=False, required=False,
                    help='Display hits in real time during data taking')
    
    parser.add_argument('-p', '--plotsave', action='store_true', default=False, required=False,
                    help='Save plots as image files. If set, will be saved in  same dir as data. Default: FALSE')
    
    parser.add_argument('-c', '--saveascsv', action='store_true', 
                    default=False, required=False, 
                    help='save output files as CSV. If False, save as txt. Default: FALSE')
    
    parser.add_argument('-f', '--newfilter', action='store_true', 
                    default=False, required=False, 
                    help='Turns on filtering of strings looking for header of e0 in V4. If False, no filtering. Default: FALSE')
    
    parser.add_argument('-i', '--inject', action='store', default=None, type=int, nargs=2,
                    help =  'Turn on injection in the given row and column. Default: No injection')

    parser.add_argument('-v','--vinj', action='store', default = None, type=float,
                    help = 'Specify injection voltage (in mV). DEFAULT None (uses value in yml)')

    parser.add_argument('-a', '--analog', action='store', required=False, type=int, default = 0,
                    help = 'Turn on analog output in the given column. Default: Column 0.')

    parser.add_argument('-t', '--threshold', type = float, action='store', default=None,
                    help = 'Threshold voltage for digital ToT (in mV). DEFAULT value in yml OR 100mV if voltagecard not in yml')
    
    parser.add_argument('-E', '--errormax', action='store', type=int, default='100', 
                    help='Maximum index errors allowed during decoding. DEFAULT 100')

    parser.add_argument('-r', '--maxruns', type=int, action='store', default=None,
                    help = 'Maximum number of readouts')

    parser.add_argument('-M', '--maxtime', type=float, action='store', default=None,
                    help = 'Maximum run time (in minutes)')

    parser.add_argument('--timeit', action="store_true", default=False,
                    help='Prints runtime from seeing a hit to finishing the decode to terminal')

    parser.add_argument('-L', '--loglevel', type=str, choices = ['D', 'I', 'E', 'W', 'C'], action="store", default='I',
                    help='Set loglevel used. Options: D - debug, I - info, E - error, W - warning, C - critical. DEFAULT: I')

    parser.add_argument
    args = parser.parse_args()

    # Sets the loglevel
    ll = args.loglevel
    if ll == 'D':
        loglevel = logging.DEBUG
    elif ll == 'I':
        loglevel = logging.INFO
    elif ll == 'E':
        loglevel = logging.ERROR
    elif ll == 'W':
        loglevel = logging.WARNING
    elif ll == 'C':
        loglevel = logging.CRITICAL
    
    # Logging 
    formatter = logging.Formatter('%(asctime)s:%(msecs)d.%(name)s.%(levelname)s:%(message)s')
    #fh = logging.FileHandler(logname)
    #fh.setFormatter(formatter)
    sh = logging.StreamHandler()
    sh.setFormatter(formatter)

    logging.getLogger().addHandler(sh) 
    #logging.getLogger().addHandler(fh)
    logging.getLogger().setLevel(loglevel)

    logger = logging.getLogger(__name__)

    #If using v2, use injection created by injection card
    #If using v3, use injection created with integrated DACs on chip
    onchipBool = True if args.chipVer > 2 else False

    main(args)
