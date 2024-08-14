"""
Script to loop through pixels enabling one at a time, using astropix.py. 
Loop over full array and record from each pixel individually. 
Based off beam_test.py and example_loop.py

Author: Amanda Steinhebel
"""

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



#Init 
def main(args,row,col, fpgaCon:bool=True, fpgaDiscon:bool=True):

    # Ensures output directory exists
    if os.path.exists(args.outdir) == False:
        os.mkdir(args.outdir)

    if fpgaCon:
        # Prepare everything, create the object
        global astro 
        logger.info('Initiate FPGA connection')
        if boolInj:
            astro = astropixRun(chipversion=args.chipVer, inject=[row,col]) 
        else:        
            astro = astropixRun(chipversion=args.chipVer)

    astro.init_voltages(vthreshold=args.threshold) 

    #Define YAML path variables
    pathdelim=os.path.sep #determine if Mac or Windows separators in path name

    #Initiate asic with pixel mask as defined in yaml 
    #Updates injection pixel
    astro.asic_init(yaml=args.yaml, analog_col=col)

    #Enable single pixel in (col,row)
    #Updates asic by default
    astro.enable_pixel(col,row)

    #If injection, ensure injection pixel is enabled and initialize
    if boolInj:
        astro.enable_injection(col,row)
        astro.init_injection(inj_voltage=args.vinj)

    astro.enable_spi() 
    logger.info("Chip configured")
    astro.dump_fpga()

    if boolInj:
        astro.start_injection()

    i=0
    if args.maxtime is not None: 
        end_time=time.time()+(args.maxtime*60.)
    strPix = "_col"+str(col)+"_row"+str(row)+"_"
    fname=strPix if not args.name else args.name+strPix

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

    # Prepares the file paths 
    # Save final configuration to output file    
    ymlpathout=args.outdir+pathdelim+args.yaml+"_"+fname+time.strftime("%Y%m%d-%H%M%S")+".yml"
    astro.write_conf_to_yaml(ymlpathout)
    # And here for the text files/logs
    bitpath = args.outdir + pathdelim + fname + time.strftime("%Y%m%d-%H%M%S") + '.log'
    bitfile = open(bitpath,'w')
    # Writes all the config information to the file
    bitfile.write(astro.get_log_header())
    bitfile.write(str(args))
    bitfile.write("\n")

    try: # By enclosing the main loop in try/except we are able to capture keyboard interupts cleanly    
        while (True): # Loop continues 
            # Break conditions
            if args.maxtime is not None:
                if time.time() >= end_time: break
            readout = astro.get_readout()
            
            if readout: # Checks if hits are present
                    # Writes the hex version to hits
                bitfile.write(f"{i}\t{str(binascii.hexlify(readout))}\n")
                #print(binascii.hexlify(readout))

                # Added fault tolerance for decoding, the limits of which are set through arguments
                try:
                    hits = astro.decode_readout(readout, i, printer = True)
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
        if boolInj: astro.stop_injection() 
        bitfile.close() # Close open file       
        if fpgaDiscon:
            astro.close_connection() # Closes SPI
            logger.info('FPGA Connection ended')
        logger.info("Program terminated successfully")
    # END OF PROGRAM


    

if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='Astropix Driver Code')
    parser.add_argument('-n', '--name', default='', required=False,
                    help='Option to give additional name to output files upon running')

    parser.add_argument('-o', '--outdir', default='.', required=False,
                    help='Output Directory for all datafiles')
    
    parser.add_argument('-V', '--chipVer', default=2, required=False, type=int,
                    help='Chip version - provide an int')

    parser.add_argument('-y', '--yaml', action='store', required=False, type=str, default = 'testconfig',
                    help = 'filepath (in config/ directory) .yml file containing chip configuration. Default: config/testconfig.yml (All pixels off)')

    parser.add_argument('-t', '--threshold', type = float, action='store', default=100,
                    help = 'Threshold voltage for digital ToT (in mV). DEFAULT 100mV')

    parser.add_argument('-M', '--maxtime', type=float, action='store', default=None,
                    help = 'Maximum run time (in minutes)')

    parser.add_argument('-C', '--colrange', action='store', default=[0,34], type=int, nargs=2,
                    help =  'Loop over given range of columns. Default: 0 34')

    parser.add_argument('-R', '--rowrange', action='store', default=[0,34], type=int, nargs=2,
                    help =  'Loop over given range of rows. Default: 0 34')
                    
    parser.add_argument('-v','--vinj', action='store', default = 300, type=float,
                    help = 'Specify injection voltage (in mV) to turn on injection. If argument not used, injection not enabled. DEFAULT None')
  
    parser.add_argument('-c', '--saveascsv', action='store_true', default=False, required=False, 
                    help='save output files as CSV. If False, save as txt. Default: FALSE')
    

    parser.add_argument
    args = parser.parse_args()
    
    # Logging
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

    boolInj = True if args.vinj is not None else False

    #loop over full array by default, unless bounds are given as argument
    for c in range(args.colrange[0],args.colrange[1]+1,1):
        for r in range(args.rowrange[0],args.rowrange[1]+1,1):
            if r==args.rowrange[0] and c==args.colrange[0]:#first pixel probed - connect to FPGA but leave open
                main(args,r,c, fpgaDiscon=False)
            elif r==args.rowrange[1] and c==args.colrange[1]: #final pixel probed - disconnect from FPGA upon completion
                main(args,r,c, fpgaCon=False)
            else: #for bulk of pixels, FPGA is already open. Do not reconnect and do not disconnect when completed, leave it open for the next pixel
                main(args,r,c, fpgaCon=False, fpgaDiscon=False)
            