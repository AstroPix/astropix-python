
import sys
import modules.postProcessing_streams as pps
import time

t0 = time.time()
print(f"Starting at {t0}")
bitpath = sys.argv[1]
bitpath_pps = bitpath[:-4]+"_PPS.log"
postProcessing = pps.postProcessing_streams(bitpath)
with open(bitpath_pps, 'w', encoding='utf-8') as f:
    f.write("EventNmb \t BadEvents \t Data \n")
    f.write('\n'.join(f'{tup[0]} \t {tup[1]} \t {tup[2]}' for tup in postProcessing.dump()))
    f.close()

ttot = time.time() - t0
print(f"Took {ttot}s ({ttot/60.:.3f}min) to run")