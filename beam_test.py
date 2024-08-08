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

    # Prepares the file paths 
    if args.saveascsv and args.chipVer == 4:
        csvpath = args.outdir +'/' + fname + time.strftime("%Y%m%d-%H%M%S") + '.csv'
        csvframe =pd.DataFrame(columns = [
            'id',
            'payload',
            'row',
            'col',
            'ts1',
            'tsfine1',
            'ts2',
            'tsfine2',
            'tsneg1',
            'tsneg2',
            'tstdc1',
            'tstdc2',
            'ts_dec1',
            'ts_dec2',
            'tot_us'
        ])
    elif args.saveascsv: # Here for csv
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
    ymlpathout=args.outdir +"/"+args.yaml+"_"+time.strftime("%Y%m%d-%H%M%S")+".yml"
    try:
        astro.write_conf_to_yaml(ymlpathout)
    except FileNotFoundError:
        ypath = args.yaml.split('/')
        ymlpathout=args.outdir+"/"+ypath[1]+"_"+time.strftime("%Y%m%d-%H%M%S")+".yml"
        astro.write_conf_to_yaml(ymlpathout)
    # Prepare text files/logs
    bitpath = args.outdir + '/' + fname + time.strftime("%Y%m%d-%H%M%S") + '.log'
    # textfiles are always saved so we open it up 
    bitfile = open(bitpath,'w')
    # Writes all the config information to the file
    bitfile.write(astro.get_log_header())
    bitfile.write(str(args))
    bitfile.write("\n")

    # Enables the hitplotter and uses logic on whether or not to save the images
    if args.showhits: plotter = hitplotter.HitPlotter(35, outdir=(args.outdir if args.plotsave else None))


    astro.dump_fpga()

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
                # Writes the hex version to hits
                bitfile.write(f"{i}\t{str(binascii.hexlify(readout))}\n")
                bitfile.flush() #make it simulate streaming
                #print(binascii.hexlify(readout))
                string_readout=str(binascii.hexlify(readout))[2:-1]

                decoding_bool=True
                if args.newfilter and args.chipVer == 4:
                    string_list=[i for i in string_readout.replace('ff','bc').split('bc') if i!='']
                    for event in string_list:
                        if event[0:2]!='e0':
                            decoding_bool=False

                if decoding_bool:
                    # Added fault tolerance for decoding, the limits of which are set through arguments
                    try:
                        hits = astro.decode_readout(readout, i, args.chipVer, printer = True)
                    except IndexError:
                        errors += 1
                        logger.warning(f"Decoding failed. Failure {errors} of {max_errors} on readout {i}")
                        # We write out the failed decode dataframe
                        hits = decode_fail_frame
                        hits.readout = i
                        hits.hittime = time.time()

                        # This loggs the end of it all 
                        if errors > max_errors:
                            logger.warning(f"Decoding failed {errors} times on an index error. Terminating Progam...")
                    finally:
                        i+=1
                        # If we are saving a csv this will write it out. 
                        if i==1 and args.chipVer==4 and args.saveascsv:
                            csvframe=hits
                            csvframe.columns=['id',
                                                'payload',
                                                'row',
                                                'col',
                                                'ts1',
                                                'tsfine1',
                                                'ts2',
                                                'tsfine2',
                                                'tsneg1',
                                                'tsneg2',
                                                'tstdc1',
                                                'tstdc2',
                                                'ts_dec1',
                                                'ts_dec2',
                                                'tot_us']
                        elif args.saveascsv:
                            csvframe = pd.concat([csvframe, hits])

                        # This handles the hitplotting. Code by Henrike and Amanda
                        if args.showhits:
                            # This ensures we aren't plotting NaN values. I don't know if this would break or not but better 
                            # safe than sorry
                            if pd.isnull(hits.tot_msb.loc(0)):
                                pass
                            elif len(hits)>0:#safeguard against bad readouts without recorded decodable hits
                                #Isolate row and column information from array returned from decoder
                                rows = hits.location[~hits.isCol]
                                columns = hits.location[hits.isCol]
                                plotter.plot_event( rows, columns, i)

                        # If we are logging runtime, this does it!
                        if args.timeit:
                            print(f"Read and decode took {(time.time_ns()-start)*10**-9}s")

    # Ends program cleanly when a keyboard interupt is sent.
    except KeyboardInterrupt:
        logger.info("Keyboard interupt. Program halt!")
    # Catches other exceptions
    except Exception as e:
        logger.exception(f"Encountered Unexpected Exception! \n{e}")
    finally:
        if args.saveascsv: 
            csvframe.index.name = "dec_ord"
            csvframe.to_csv(csvpath) 
        if args.inject is not None: astro.stop_injection()   
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
