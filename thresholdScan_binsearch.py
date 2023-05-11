"""
Script to loop through pixels enabling one at a time, using astropix.py. 
For a variety of threshold values, loop over full array and only record the number of times 
the comparator would have fired. 
Based off beam_test.py and example_loop.py

Author: Amanda Steinhebel

Edit: Added binary search algorithm to decrease runtime from O(n) to O(log(n))
Author: Nicolas Striebig
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

global astro 
logger.info('Initiate FPGA connection')
astro = astropixRun() #initialize without enabling injections

#Init 
def main(args,row,col, fpgaCon:bool=True, fpgaDiscon:bool=True):

    # Ensures output directory exists
    if os.path.exists(args.outdir) == False:
        os.mkdir(args.outdir)

    astro.init_voltages(vthreshold=args.threshold, vsupply=2.796) 

    #Define YAML path variables
    pathdelim=os.path.sep #determine if Mac or Windows separators in path name

    #Initiate asic with pixel mask as defined in yaml 
    astro.asic_init(yaml=args.yaml)

    #Enable single pixel in (col,row)
    #Updates asic by default
    astro.enable_pixel(col,row)


    astro.enable_spi() 
    logger.info("Chip configured")
    astro.dump_fpga()

    i = 0
    if args.maxtime is not None: 
        end_time=time.time()+(args.maxtime*60.)
    strPix = "_"+str(args.threshold)[:-2]+"mVThresh_col"+str(col)+"_row"+str(row)+"_"
    fname=strPix if not args.name else args.name+strPix+"_"

    # Prepares the file paths 
    # Save final configuration to output file    
    ymlpathout=outdir+pathdelim+args.yaml+"_"+fname+time.strftime("%Y%m%d-%H%M%S")+".yml"
    astro.write_conf_to_yaml(ymlpathout)
    # And here for the text files/logs
    bitpath = outdir + pathdelim + fname + time.strftime("%Y%m%d-%H%M%S") + '.log'
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
            
            if astro.hits_present(): # Checks if hits are present
    
                time.sleep(.001) # this is probably not needed, will ask Nicolas

                readout = astro.get_readout(3) # Gets the bytearray from the chip

                # Writes the hex version to hits
                bitfile.write(f"{i}\t{str(binascii.hexlify(readout))}\n")
                #print(binascii.hexlify(readout))
                i += 1
                astro.asic_update() #must be done after every interrupt check

            # If no hits are present this waits for some to accumulate
            else: time.sleep(.001)
    # Ends program cleanly when a keyboard interupt is sent.
    except KeyboardInterrupt:
        logger.info("Keyboard interupt. Program halt!")
    # Catches other exceptions
    except Exception as e:
        logger.exception(f"Encountered Unexpected Exception! \n{e}")
    finally:  
        interrfile = open(interrpath,'a+')
        interrfile.write(f"{r} \t {i} \t {args.threshold} \n")
        interrfile.close()
        bitfile.close() # Close open file       
        if fpgaDiscon:
            astro.close_connection() # Closes SPI
            logger.info('FPGA Connection ended')
        logger.info("Program terminated successfully")

    return i # return number of hits
    # END OF PROGRAM


    

if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='Astropix Driver Code')
    parser.add_argument('-n', '--name', default='', required=False,
                    help='Option to give additional name to output files upon running')

    parser.add_argument('-o', '--outdir', default='.', required=False,
                    help='Output Directory for all datafiles')

    parser.add_argument('-y', '--yaml', action='store', required=False, type=str, default = 'testconfig',
                    help = 'filepath (in config/ directory) .yml file containing chip configuration. Default: config/testconfig.yml (All pixels off)')

    parser.add_argument('-t', '--threshold', type = float, action='store', default=None,
                    help = 'Threshold voltage for digital ToT (in mV). DEFAULT 100mV')

    parser.add_argument('-M', '--maxtime', type=float, action='store', default=None,
                    help = 'Maximum run time (in minutes)')

    parser.add_argument('-C', '--colrange', action='store', default=[0,34], type=int, nargs=2,
                    help =  'Loop over given range of columns. Default: 0 34')

    parser.add_argument('-R', '--rowrange', action='store', default=[0,34], type=int, nargs=2,
                    help =  'Loop over given range of rows. Default: 0 34')

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

    outdir = args.outdir 
    if os.path.exists(outdir) == False:
        os.mkdir(outdir)
     
    #loop over full array by default, unless bounds are given as argument
    for c in range(args.colrange[0],args.colrange[1]+1,1):
        interrpath = outdir + '/counts_' + str(args.threshold)[:-2] + 'mVThresh_' + args.name +'_col' + str(c) + "_"+ time.strftime("%Y%m%d-%H%M%S") + '.txt'
        interrfile = open(interrpath,'a+')
        interrfile.write(f"Row \t Counts \t Threshold \n")
        interrfile.close()
        for r in range(args.rowrange[0],args.rowrange[1]+1,1):
            vth_start = 1.
            vth_stop = 400.
            while(True):
                vth_val = np.round((vth_start + vth_stop)/2)
                print(f"Vth value: {vth_val}")

                args.threshold = vth_val
                cnt_hits = main(args, r, c, fpgaDiscon=False)
                print(cnt_hits)

                if(cnt_hits > 10):
                    vth_start = vth_val
                else:
                    vth_stop = vth_val

                if(vth_stop - vth_start <= 1.):
                    break
