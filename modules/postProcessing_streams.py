#import matplotlib.pyplot as plt
#import os
from asyncio import DatagramProtocol
import re
import pandas as pd

class postProcessing_streams:
    """
    Manage raw data streams post data collection
        Remove railing from streams
        Save compressed *.log file
        Decode raw hits and save decoded info in compressed csv
    """
    
    def __init__(self,filepath, dec:bool=False):

        beginRead = 1 if dec else 6 #eliminate header if inputting raw data file (.log)
        with open(filepath,"r") as f:
            self.lines = f.readlines()[beginRead:]
    
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

    def decode(self):
        """
        Returns all decoded hits as DataFrame, structure: readout, Chip ID, payload, location, isCol, timestamp, tot_msb, tot_lsb, tot_total, tot_us
        """
        data = [hit_decoder(i) for i in self.lines]
        data_df = pd.concat(data)

        return data_df
    
def readstream(stream):
    """Simple function to read a bytestream from a binary file and
    return the read as a series of bytes
    Input: bytes (List)
    Output: """
    bytes = [stream[i:i+2] for i in range(0,len(stream),2)]
    return bytes

def readbyte(byte):
    """Simple function to read 1 byte from a binary file and
    return the byte as a binary type
    Input: Byte (string)
    Output: Byte (binary)"""

    byte = ''.join(byte)
    binary = bytearray(bin(int(byte,16))[2:].zfill(8), encoding='utf8')
    return binary

def regex_filter(li):
    """Function for filtering raw data .logs with regex and
       returns data packet of any length

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

def hit_decoder(li):
    """Function for decoding hit data

       input:  line of AstroPix_V3 XXX_PPS.log file (generated with this class's regex_filter)
       output: list of strings containing decoded data 
    """
    bytesPerHit = 5
    sampleclock_period_ns = 5
    
    #Grab data from lines in 
    readout = int(li.split()[0])
    #print(readout)
    data = li.split()[2][1:-1] #split into three columns and strip []
    if not data: #no hits
        return
    data = data.split(',')
    data = [d[1:-1] for d in data] #remove ""

    #separates string into bytes
    bytes_data = [readstream(d) for d in data]

    # converts to binary strings, reverses strings (individually reverse bytes)
    bin_output = [[readbyte(s)[::-1] for s in a]  for a in bytes_data]

    hit_list = [[packet[i:i + bytesPerHit] for i in range(0, len(packet), bytesPerHit)] for packet in bin_output][0] 

    decoded_hits = []
    #define decoding scheme
    for hit in hit_list:
        # Generates the values from the bitstream
        try:
            id          = int(hit[0][0:4])
            payload     = int(hit[0],2) & 0b111
            location    = int(hit[1],2)  & 0b111111
            col         = 1 if (int(hit[1][0])) & 1 else 0
            timestamp   = int(hit[2],2)
            tot_msb     = int(hit[3],2) & 0b1111
            tot_lsb     = int(hit[4],2)   
            tot_total   = (tot_msb << 8) + tot_lsb
        except IndexError: #hit cut off at end of stream
            id, payload, location, col = -1, -1, -1, -1
            timestamp, tot_msb, tot_lsb, tot_total = -1, -1, -1, -1
        #Calculate ToT in us
        tot_us = (tot_total * sampleclock_period_ns)/1000.0
        
        hits = [readout,id,payload,location,col,timestamp,tot_msb,tot_lsb,tot_total,tot_us] 
        decoded_hits.append(hits)

    return pd.DataFrame(decoded_hits)