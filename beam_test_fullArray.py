"""
Full-array running of AstroPix_v3

Author: Amanda Steinhebel, amanda.l.steinhebel@nasa.gov
"""

from astropix import astropixRun
import modules.hitplotter as hitplotter
import modules.postProcessing_streams as pps
import os
import binascii
import time
import logging
import argparse
from io import BytesIO

from modules.setup_logger import logger


# This sets the logger name.
logdir = "./runlogs/"
if os.path.exists(logdir) == False:
    os.mkdir(logdir)
logname = "./runlogs/AstropixRunlog_" + time.strftime("%Y%m%d-%H%M%S") + ".log"

#Initialize
def main(args):

    # Ensures output directory exists
    if os.path.exists(args.outdir) == False:
        os.mkdir(args.outdir)
        
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

    # Prepares the file paths 
    # Save final configuration to output file    
    ymlpathout=args.outdir +"/"+args.yaml+"_"+time.strftime("%Y%m%d-%H%M%S")+".yml"
    try:
        astro.write_conf_to_yaml(ymlpathout)
    except FileNotFoundError:
        ypath = args.yaml.split('/')
        ymlpathout=args.outdir+"/"+ypath[1]+"_"+time.strftime("%Y%m%d-%H%M%S")+".yml"
        astro.write_conf_to_yaml(ymlpathout)
    # Prepare output data file
    dataExt = '.bin' if args.binaryData else '.log'
    bitpath = args.outdir + '/' + fname + time.strftime("%Y%m%d-%H%M%S") + dataExt

    # textfiles are always saved so we open it up 
    openVar = 'wb' if args.binaryData else 'w'
    bitfile = open(bitpath,openVar)
    if not args.binaryData:
        # Writes all the config information to the file
        bitfile.write(astro.get_log_header())
        bitfile.write(str(args))
        bitfile.write("\n") 

    # Enables the hitplotter and uses logic on whether or not to save the images
    if args.showhits: plotter = hitplotter.HitPlotter(35, outdir=(args.outdir if args.plotsave else None))

    logger.info("Collecting data!")
    try: # By enclosing the main loop in try/except we are able to capture keyboard interupts cleanly
        while errors <= max_errors: # Loop continues 

            # This might be possible to do in the loop declaration, but its a lot easier to simply add in this logic
            if args.maxruns is not None:
                if i >= args.maxruns: break
            if args.maxtime is not None:
                if time.time() >= end_time: break
            
            # We aren't using timeit, just measuring the diffrence in ns
            if args.timeit: start = time.time_ns()
            readout = astro.get_readout()
            if args.timeit: print(f"Readout took {(time.time_ns()-start)*10**-9}s")

            if readout: #if there is data contained in the readout stream
                logger.debug(binascii.hexlify(readout))
                # Write raw data file
                if args.binaryData:
                    #Save full stream as binary
                    write_byte = BytesIO(readout)
                    bitfile.write(write_byte.getbuffer())
                else:
                    #Write full stream in hex
                    bitfile.write(f"{i}\t{str(binascii.hexlify(readout))}\n")
                i+=1
                logger_bool=True
            if i%100==0 and logger_bool: #prints out progress every 100 readouts, also prevents multiple prints per readout
                logger.info(f"{i} readout streams collected")
                logger_bool=False

    # Ends program cleanly when a keyboard interupt is sent.
    except KeyboardInterrupt:
        logger.info("Keyboard interupt. Program halt!")
    # Catches other exceptions
    except Exception as e:
        logger.exception(f"Encountered Unexpected Exception! \n{e}")
    finally:
        if args.inject is not None: astro.stop_injection()   
        bitfile.close() # Close open file        
        astro.close_connection() # Closes SPI
        logger.info("Program terminated successfully")

    #post-processing, if data was originally written to .txt and if any data was read off
    if not args.binaryData and i>0:
        #create PPS file
        bitpath_pps = bitpath[:-4]+"_PPS.log"
        postProcessing = pps.postProcessing_streams(bitpath)

        with open(bitpath_pps, 'w', encoding='utf-8') as f:
            f.write("EventNmb \t BadEvents \t Data \n")
            f.write('\n'.join(f'{tup[0]} \t {tup[1]} \t {tup[2]}' for tup in postProcessing.dump()))
            f.close()

        #create decoded CSV
        csvpath = bitpath[:-4]+".csv"
        postProcessing2 = pps.postProcessing_streams(bitpath_pps, dec=True)

        df_decoded = postProcessing2.decode()
        df_decoded.columns = [ 
            'readout',
            'Chip ID',
            'payload',
            'location',
            'isCol',
            'timestamp',
            'tot_msb',
            'tot_lsb',
            'tot_total',
            'tot_us'
        ]
        df_decoded.index.name = "dec_ord"
        df_decoded.to_csv(csvpath)      
    elif i==0:
        logger.warning("No data recorded - nothing to decode. Deleting empty file")
        if os.path.exists(bitpath):
            os.remove(bitpath)
        else:
            print(f"The file {bitpath} does not exist")

    # END OF PROGRAM
    
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
    
    parser.add_argument('-s', '--showhits', action='store_true', default=False, required=False,
                    help='Display hits in real time during data taking')
    
    parser.add_argument('-p', '--plotsave', action='store_true', default=False, required=False,
                    help='Save plots as image files. If set, will be saved in  same dir as data. Default: FALSE')
    
    parser.add_argument('-b', '--binaryData', action='store_true', default=False, required=False,
                    help='Save raw data as a binary .bin file. Does not filter railing/idle bytes. Default: FALSE')
    
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
    fh = logging.FileHandler(logname)
    fh.setFormatter(formatter)
    sh = logging.StreamHandler()
    sh.setFormatter(formatter)

    logging.getLogger().addHandler(sh) 
    logging.getLogger().addHandler(fh)
    logging.getLogger().setLevel(loglevel)

    logger = logging.getLogger(__name__)

    #If using v2, use injection created by injection card
    #If using v3, use injection created with integrated DACs on chip
    onchipBool = True if args.chipVer > 2 else False

    main(args)