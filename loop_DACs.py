"""
Simple script to loop through DAC settings, enabling one single pixel at a time using astropix.py
Based off beam_test.py

Author: Amanda Steinhebel
"""

#from msilib.schema import File
#from http.client import SWITCHING_PROTOCOLS
from astropix import astropixRun
import modules.hitplotter as hitplotter
import os
import binascii
import pandas as pd
import numpy as np
import time
import logging
import argparse

from modules.setup_logger import logger


# This sets the logger name.
logdir = "./runlogs/"
if os.path.exists(logdir) == False:
    os.mkdir(logdir)
logname = "./runlogs/AstropixRunlog_" + time.strftime("%Y%m%d-%H%M%S") + ".log"


# This is the dataframe which is written to the csv if the decoding fails
decode_fail_frame = pd.DataFrame({
                'readout': np.nan,
                'Chip ID': np.nan,
                'payload': np.nan,
                'location': np.nan,
                'isCol': np.nan,
                'timestamp': np.nan,
                'tot_msb': np.nan,
                'tot_lsb': np.nan,
                'tot_total': np.nan,
                'tot_us': np.nan,
                'hittime': np.nan
                }, index=[0]
)

  

#Init 
def main(args,dac):

    # Ensures output directory exists
    if os.path.exists(args.outdir) == False:
        os.mkdir(args.outdir)

    # Prepare everything, create the object
    if args.inject:
        astro = astropixRun(inject=args.pixel) #enable injections
    else:
        astro = astropixRun() #initialize without enabling injections

    astro.init_voltages(vthreshold=args.threshold)

    #Define YAML path variables
    pathdelim=os.path.sep #determine if Mac or Windows separators in path name
    ymlpath="config"+pathdelim+args.yaml+".yml"

    # Initialie asic - blank array, no pixels enabled, analog enabled for defined pixel or (0,0) by default
    if args.DAC!="":
        astro.asic_init(yaml=ymlpath, dac_setup={args.DAC: dac},analog_col = args.analog)
    else:
        astro.asic_init(yaml=ymlpath, analog_col = args.analog)
 
    #Enable single pixel from argument, or (0,0) if no pixel given
    astro.enable_pixel(args.pixel[1],args.pixel[0])

    # If injection is on initalize the board
    if args.inject:
        astro.init_injection(inj_voltage=args.vinj)
    astro.enable_spi() 
    logger.info("Chip configured")
    astro.dump_fpga()

    if args.inject:
        astro.start_injection()

    i = 0
    if args.maxtime is not None: 
        end_time=time.time()+(args.maxtime*60.)
    strDac = args.DAC+"_"+str(dac)+"_"
    fname=strDac if not args.name else args.name+"_"+strDac

    # Prepares the file paths 
    if args.saveascsv: # Here for csv
        csvpath = args.outdir +'/' + fname + time.strftime("%Y%m%d-%H%M%S") + '.csv'
        csvframe =pd.DataFrame(columns = [
                'readout',
                'Chip ID',
                'payload',
                'location',
                'isCol',
                'timestamp',
                'tot_msb',
                'tot_lsb',
                'tot_total',
                'tot_us',
                'hittime'
        ])

    # Save final configuration to output file    
    ymlpathout=args.outdir+pathdelim+args.yaml+"_"+time.strftime("%Y%m%d-%H%M%S")+".yml"
    astro.write_conf_to_yaml(ymlpathout)
    # And here for the text files/logs
    bitpath = args.outdir + '/' + fname + time.strftime("%Y%m%d-%H%M%S") + '.log'
    # textfiles are always saved so we open it up 
    bitfile = open(bitpath,'w')
    # Writes all the config information to the file
    bitfile.write(astro.get_log_header())
    bitfile.write(str(args))
    bitfile.write("\n")

    try: # By enclosing the main loop in try/except we are able to capture keyboard interupts cleanly
        
        while (True): # Loop continues 

            # Break conditions
            if args.maxruns is not None:
                if i >= args.maxruns: break
            if args.maxtime is not None:
                if time.time() >= end_time: break
            readout = astro.get_readout()
            
            
            if readout: # Checks if hits are present
                # Writes the hex version to hits
                bitfile.write(f"{i}\t{str(binascii.hexlify(readout))}\n")
                print(binascii.hexlify(readout))

                # Added fault tolerance for decoding, the limits of which are set through arguments
                try:
                    hits = astro.decode_readout(readout, i, printer = True)

                except IndexError:
                    # We write out the failed decode dataframe
                    hits = decode_fail_frame
                    hits.readout = i
                    hits.hittime = time.time()

                finally:
                    i += 1

                    # If we are saving a csv this will write it out. 
                    if args.saveascsv:
                        csvframe = pd.concat([csvframe, hits])

            # If no hits are present this waits for some to accumulate
            else: time.sleep(.001)


    # Ends program cleanly when a keyboard interupt is sent.
    except KeyboardInterrupt:
        logger.info("Keyboard interupt. Program halt!")
    # Catches other exceptions
    except Exception as e:
        logger.exception(f"Encountered Unexpected Exception! \n{e}")
    finally:
        if args.saveascsv: 
            csvframe.index.name = "dec_order"
            csvframe.to_csv(csvpath) 
        if args.inject: astro.stop_injection()   
        bitfile.close() # Close open file       
        astro.close_connection() # Closes SPI
        logger.info("Program terminated successfully")
    # END OF PROGRAM


    

if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='Astropix Driver Code')
    parser.add_argument('-n', '--name', default='', required=False,
                    help='Option to give additional name to output files upon running')

    parser.add_argument('-o', '--outdir', default='.', required=False,
                    help='Output Directory for all datafiles')

    parser.add_argument('-y', '--yaml', action='store', required=False, type=str, default = 'testconfig',
                    help = 'filepath (in config/ directory) .yml file containing chip configuration. Default: config/testconfig.yml (All pixels off)')

    
    parser.add_argument('-c', '--saveascsv', action='store_true', 
                    default=False, required=False, 
                    help='save output files as CSV. If False, save as txt')
    
    parser.add_argument('-i', '--inject', action='store_true', default=False, required=False,
                    help =  'Turn on injection. Default: No injection')

    parser.add_argument('-v','--vinj', action='store', default = None, type=float,
                    help = 'Specify injection voltage (in mV). DEFAULT 400 mV')

    parser.add_argument('-a', '--analog', action='store', required=False, type=int, default = 0,
                    help = 'Turn on analog output in the given column. Default: Column 0. Set to None to turn off analog output.')

    parser.add_argument('-t', '--threshold', type = float, action='store', default=100,
                    help = 'Threshold voltage for digital ToT (in mV). DEFAULT 100mV')

    parser.add_argument('-r', '--maxruns', type=int, action='store', default=None,
                    help = 'Maximum number of readouts')

    parser.add_argument('-M', '--maxtime', type=float, action='store', default=None,
                    help = 'Maximum run time (in minutes)')

    parser.add_argument('-p', '--pixel', action='store', default=[0,0], type=int, nargs=2,
                    help =  'Single enabled pixel (row col). Default: 0 0')

    parser.add_argument('-D', '--DAC', default='', required=False,
                    help =  'DAC value over which to scan. Default: None')

    parser.add_argument('-d', '--dacrange', action='store', default=[0,60,5], type=int, nargs=3,
                    help =  'Range to scan over DAC value and increment. Default: 0 60 5')

    parser.add_argument
    args = parser.parse_args()
    
    # Logging stuff!
    loglevel = logging.INFO
    formatter = logging.Formatter('%(asctime)s:%(msecs)d.%(name)s.%(levelname)s:%(message)s')
    fh = logging.FileHandler(logname)
    fh.setFormatter(formatter)
    sh = logging.StreamHandler()
    sh.setFormatter(formatter)

    logging.getLogger().addHandler(sh) 
    logging.getLogger().addHandler(fh)
    logging.getLogger().setLevel(loglevel)

    logger = logging.getLogger(__name__)

    #loop over full array by default, unless bounds are given as argument
    for d in range(args.dacrange[0],args.dacrange[1],args.dacrange[2]):
        main(args,d)
        time.sleep(5) # to avoid loss of connection to Nexys