# Copyright (c) 2011 Jeppe Ledet-Pedersen
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

# Adjust radio frequency

# This library still lacks implementation
# Requires well defined interface to COM config over CSP 

# Python imports
import struct

# AAUSAT3 imports
import csp

class radio():
    def __init__(self, mcclog, outqueue, conf):
        self.mcclog = mcclog
        self.outqueue = outqueue
        self.frequency = conf.frequency
        self.radioaddress = conf.radioaddress
        self.radioport = conf.radioport
        self.set_frequency(437475000)
        
    def set_frequency(self, frequency):
        if (frequency < self.frequency - 1000000 or frequency > self.frequency + 1000000):
            raise Exception("Invalid frequency {0}".format(frequency))
        else:
            # Create CSP packet
            magic_word = 0x12345678
            packet = csp.packet(-1, -1, self.radioaddress, self.radioport, [struct.unpack("<B", i)[0] for i in tuple(struct.pack("<II", frequency, magic_word))])
            try:
                self.outqueue.put(packet, True, 1)
            except Queue.Full:
                self.mcclog.warning("Failed to set radio frequency to {0} Hz".format(frequency))
            else:
                self.mcclog.info("Setting radio frequency to {0} Hz".format(frequency))
            
            
