#import matplotlib.pyplot as plt
#import os
import re

class postProcessing_streams:
    """
    Manage raw data streams post data collection
        Remove railing from streams
        Save compressed *.log file
        Decode raw hits and save decoded info in compressed csv
    """
    
    def __init__(self,filepath):
        with open(filepath,"r") as f:
            self.lines = f.readlines()[6:]
    
    def dump(self):
        """
        Returns data structure: Index, # Removed Bad Events, Hit List
        """
        return [regex_filter(i) for i in self.lines]
    
    def hits(self):
        """
        Returns Hit List
        """
        return [hit for data in self.dump() for hit in data[2]]
    
def regex_filter(li):
    """Function for filtering raw data .logs with regex and
       returns hits of correct length (10 bytes)

       input:  line of AstroPix_V3 XXX.log file
       output: datastring index {int}, # dropped hits {int}, good hits {string list}
    """

    #regular expression handling to separate data hits
    regex = [("\tb'"," "),
             ("'\n" ,""),
             (r"(ff){2,}",""),
             (r"(bc){2,}"," ")]

    out = [li := re.sub(raw, clean, li) for raw, clean in regex][-1].split()
    dat = [o for o in out[1:]] #return all bytes that aren't railing or an idle byte, array entries indicate data packets in raw stream

    #return datastring index, #bad hits cleaned, and hits
    return int(out[0]), len(out[1:])-len(dat), dat