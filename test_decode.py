
import sys
import time
import modules.postProcessing_streams as pps
import pandas


t0 = time.time()
print(f"Starting at {t0}")
bitpath = sys.argv[1]
csvpath = bitpath[:-8] + '.csv'
print(csvpath)
columns = [
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

postProcessing = pps.postProcessing_streams(bitpath, dec=True)

df_decoded = postProcessing.decode()
df_decoded.columns = columns
df_decoded.index.name = "dec_ord"
df_decoded.to_csv(csvpath) 
ttot = time.time() - t0
print(f"Took {ttot}s ({ttot/60.:.3f}min) to run")
        


