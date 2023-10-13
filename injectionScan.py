"""
Script to loop through injection voltage values enabling a single pixel. Test all injection values on one pixel

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
def main(args, injv, fpgaCon:bool=True, fpgaDiscon:bool=True):

    # Ensures output directory exists
    if os.path.exists(args.outdir) == False:
        os.mkdir(args.outdir)

    if fpgaCon:
        # Prepare everything, create the object
        global astro 
        logger.info('Initiate FPGA connection')
        astro = astropixRun(chipversion=args.chipVer, inject=args.inject) #initialize with always enabling injections (args.inject is always true)

    astro.init_voltages(vthreshold=args.threshold) 

    #Define YAML path variables
    pathdelim=os.path.sep #determine if Mac or Windows separators in path name

    #Initiate asic with pixel mask as defined in yaml 
    astro.asic_init(yaml=config, analog_col=args.inject[1])

    #enable injection
    astro.enable_pixel(args.inject[1],args.inject[0])    
    astro.init_injection(inj_voltage=injv, onchip=onchipBool)

    astro.enable_spi() 
    logger.info("Chip configured")
    astro.dump_fpga()
    astro.start_injection()

    i = 0
    if args.maxtime is not None: 
        end_time=time.time()+(args.maxtime*60.)
    strPix = "r"+str(args.inject[0])+"c"+str(args.inject[1])+"_"+str(injv/1000.)+"VInj_"
    fname=strPix if not args.name else args.name+strPix+"_"

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
    ymlpathout=args.outdir+pathdelim+config+"_"+fname+time.strftime("%Y%m%d-%H%M%S")+".yml"
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
                print(binascii.hexlify(readout))
                hits = astro.decode_readout(readout, i, printer = True)
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
        astro.stop_injection()
        if args.saveascsv: 
            csvframe.index.name = "dec_order"
            csvframe.to_csv(csvpath) 
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

    parser.add_argument('-c', '--saveascsv', action='store_true', 
                    default=False, required=False, 
                    help='save output files as CSV. If False, save as txt. Default: FALSE')
    
    parser.add_argument('-t', '--threshold', type = float, action='store', default=80,
                    help = 'Threshold voltage for digital ToT (in mV). DEFAULT 80mV')

    parser.add_argument('-M', '--maxtime', type=float, action='store', default=None,
                    help = 'Maximum run time (in minutes) at each point')

    parser.add_argument('-i', '--inject', action='store', default=[0,0], type=int, nargs=2,
                    help =  'Scan through injections in the given row and column. Default: 0 0')
    
    parser.add_argument('-I', '--injectRange', action='store', default=[100,1000], type=int, nargs=2,
                    help =  'Range of injection voltages to scan through in mV. Default: 100 1000')
    
    parser.add_argument('-s', '--injectStep', action='store', default=100, type=float,
                    help =  'Step used for scanning through injections in mV. Default: 100')

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

    #If using v2, use injection created by injection card
    #If using v3, use injection created with integrated DACs on chip
    onchipBool = True if args.chipVer > 2 else False

    #If using v2, use config_none
    #If using v3, use config_v3_none
    config = 'config_v3_none' if args.chipVer > 2 else 'config_none'

    injs = [args.injectRange[0]+(args.injectStep*x) for x in range(int((args.injectRange[1]-args.injectRange[0])/args.injectStep) + 1)]
    for i in injs:
        #loop through injection array with single pixel enabled, analog automatically enabled in whatever column is being injected into
        if i==args.injectRange[0]:#first injection - connect to FPGA but leave open
            main(args, float(i), fpgaDiscon=False)
        elif i==args.injectRange[1]: #final injection - disconnect from FPGA upon completion
            main(args, float(i), fpgaCon=False)
        else: #for bulk of pixels, FPGA is already open. Do not reconnect and do not disconnect when completed, leave it open for the next injection
            main(args, float(i), fpgaCon=False, fpgaDiscon=False)
            