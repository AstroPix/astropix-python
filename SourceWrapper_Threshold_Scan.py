import argparse
import logging
import beam_test
import os
import numpy as np
import time
from astropix import astropixRun


def change_all_TuneDACs(file,TuneDAC):
    with open(file, 'r') as stream:
        data=stream.readlines()

    for i,line in enumerate(data):
         if 'row' in line and len(line)>50:
            for column in range(16):
                line=line[:35+6*column]+bin(TuneDAC)[2:].zfill(3)[::-1]+line[38+6*column:]
            data[i]=line

    with open(file,'w') as stream:
          stream.writelines(data)


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
logname = "./runlogs/AstropixRunlog_" + time.strftime("%Y%m%d-%H%M%S") + ".log"

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

threshold_array=np.arange(50,301,10)


for TuneDAC in [0,1,2,3,4,5,6,7]:
    change_all_TuneDACs(f'config/{args.yaml}.yml', TuneDAC)
    time.sleep(1)
    ### outdir is currently specific to the machine used to run at goddard, change before running
    args.outdir=f'test_gs/New_Cadmium109_Threshold_Scan/TuneDAC_{TuneDAC}'
    for threshold in threshold_array:
            args.name=f'threshold_{threshold}mV'
            print(f'{args.name}')
            args.threshold=float(threshold)
            success_bool=False
            # beam_test.main(args)
            while success_bool==False:
                    try:
                        beam_test.main(args)
                        success_bool=True
                    except:
                        print(f'An error occured on threshold {threshold}mV')
                        success_bool=False
                        time.sleep(0.5)