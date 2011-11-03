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

# Fetch TLE from Celestrak

# Python imports
import urllib2
import time
import threading
import re

class tle(threading.Thread):
    def __init__(self, mcclog, conf):
        threading.Thread.__init__(self, None)
        self.mcclog = mcclog
        self.url = conf.tleurl
        self.interval = conf.tleupdate
        self.spacecraft = conf.spacecraft
        
        # Create event object
        self.event = threading.Event()
        
        # Reset TLE lines
        self.line1 = None
        self.line2 = None
        self.line3 = None
        
    def get(self):
        if not self.line1 == None and not self.line2 == None and not self.line3 == None:
            return (self.line1, self.line2, self.line3)
        else:
            raise Exception("TLE not available")
            
    def update(self):
        self.mcclog.info("Updating TLE for {0}".format(self.spacecraft))
            
        # Fetch TLE from Celestrak
        try:
            f = urllib2.urlopen(self.url)
            match = re.search("({0}.*)\r\n(.+)\r\n(.+)\r\n".format(self.spacecraft), f.read())
            if match:
                (self.line1, self.line2, self.line3) = match.groups()
                self.mcclog.debug(self.line1)
                self.mcclog.debug(self.line2)
                self.mcclog.debug(self.line3)
            else:
                raise Exception("No match found for {0}".format(self.spacecraft))
        except Exception as e:
            self.mcclog.warning("Failed to update TLE: {0}".format(e))
            raise
            
    def auto_enable(self):
        # Set thread state - self.daemon is important!
        self.daemon = True
        self.running = True

        # Start thread
        self.start()
        
    def stop(self):
        self.running = False
        self.event.set()

    def run(self):
        while self.running:
            # Wait for next update
            self.event.wait(self.interval * 3600)
            if self.event.is_set():
                continue
            
            # Update TLE
            self.update()
