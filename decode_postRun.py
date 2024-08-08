"""
Decode raw data (bitstreams) after data-taking, save decoded information in CSV format identical to when running beam_test.py with option -c

Author: Amanda Steinhebel
amanda.l.steinhebel@nasa.gov
"""

from astropix import astropixRun
import glob
import binascii
import pandas as pd
import numpy as np
import logging
import argparse
import re
from core.asic import Asic

from modules.setup_logger import logger

#Initialize
def main(args):
        
    #Allow only -f or -d to be evoked - not both
    if args.fileInput and args.dirInput:
        logger.error("Input a single file with -f OR a single directory with -d... not both! Try running again")
        exit()

    #Define boolean for args.fileInput
    f_in = True if args.fileInput is not None else False

    #Create objet
    astro = astropixRun(offline=True)
    #astro.asic_init()

    #Define output file path
    if args.outDir is not None:
        outpath = args.outDir
    elif f_in:
        try: #Mac path
            dirInd = args.fileInput.rindex('/')
        except ValueError: #Windows path
            dirInd = args.fileInput.rindex('\\')
        outpath = args.fileInput[:dirInd+1] #add 1 to keep final delimiter in path
    elif args.dirInput is not None:
        outpath = args.dirInput
    
    #Symmetrize structure
    inputFiles = [args.fileInput] if f_in else glob.glob(f'{args.dirInput}*.log')

    #Run over all input files
    for infile in inputFiles:

        #Define output file name
        csvname = re.split(r'\\|/',infile)[-1][:-4] #split Mac or OS path; identify file name and eliminate '.log'
        csvpath = outpath + csvname + '_offline.csv'

        #Setup CSV structure
        if args.chipVer==4:
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
        else:
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

        #Import data file           
        if args.chipVer==4: 
            f=np.loadtxt(infile, skiprows=7, dtype=str)
        else:
            f=np.loadtxt(infile, skiprows=6, dtype=str)

        #isolate only bitstream without b'...' structure 
        strings = [a[2:-1] for a in f[:,1]]

        for i,s in enumerate(strings):
            #convert hex to binary and decode
            rawdata = list(binascii.unhexlify(s))
            try:
                hits = astro.decode_readout(rawdata, i, printer = args.printDecode, chip_version=args.chipVer)
                #Lose hittime - computed during decoding so this info is lost when decoding offline (don't even get relative times because they are processed in offline decoding at machine speed)
                hits['hittime']=0.0
                #Populate csv
                csvframe = pd.concat([csvframe, hits])
            except IndexError: #cannot decode empty bitstream so skip it
                continue

        #Save csv
        csvframe.index.name = "dec_order"
        logger.info(f"Saving to {csvpath}")
        csvframe.to_csv(csvpath)
    

if __name__ == "__main__":

    parser = argparse.ArgumentParser(description='Post-run decoding')
    parser.add_argument('-f', '--fileInput', default=None, required=False,
                    help='Input data file to decode')

    parser.add_argument('-d', '--dirInput', default=None, required=False,
                    help='Input directory of data files to decode')

    parser.add_argument('-o', '--outDir', default=None, required=False,
                    help='Output Directory for all decoded datafiles. Defaults to directory raw data is saved in')

    parser.add_argument('-L', '--loglevel', type=str, choices = ['D', 'I', 'E', 'W', 'C'], action="store", default='I',
                    help='Set loglevel used. Options: D - debug, I - info, E - error, W - warning, C - critical. DEFAULT: D')

    parser.add_argument('-p', '--printDecode', action='store_true', default=False, required=False,
                    help='Print decoded info into terminal. Default: False')
    
    parser.add_argument('-V', '--chipVer', default=3, required=False, type=int,
                    help='Chip version - provide an int')

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
    
    # Logging - print to terminal only
    formatter = logging.Formatter('%(asctime)s:%(msecs)d.%(name)s.%(levelname)s:%(message)s')
    sh = logging.StreamHandler()
    sh.setFormatter(formatter)

    logging.getLogger().addHandler(sh) 
    logging.getLogger().setLevel(loglevel)

    logger = logging.getLogger(__name__)

    
    main(args)