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

# Track spacecraft

# Python imports
import time
import datetime
import threading
import re
import math


def doppler_shift(frequency, velocity):
    c = 299792458.0
    return (-velocity * frequency)/c 

class tracker(threading.Thread):
    def __init__(self, mcclog, outqueue, conf):
        # Delayed import as ephem should not be required if tracking is not used
	import ephem
	import tle
	import rotor
	import radio
        #import ephem        

        threading.Thread.__init__(self, None)
        self.mcclog = mcclog
        self.outqueue = outqueue
        self.spacecraft = conf.spacecraft
        self.frequency = conf.frequency
        
        # Create observer
        self.obs = ephem.Observer()
        self.obs.lat = conf.gslat
        self.obs.long = conf.gslong
        self.obs.elevation = conf.gselv
        self.obs.date = ephem.now()
        self.obs.pressure = 0
        self.obs.horizon = math.radians(0.0)
        self.minelv = math.radians(conf.minelv)
        
        # Create event object
        self.event = threading.Event()
        
        # Update TLE
        self.tle = tle.tle(self.mcclog, conf)
        self.tle.update()

        # Create rotor
        self.rotor = rotor.rotor(self.mcclog, conf)

        # Create radio
        self.radio = radio.radio(self.mcclog, self.outqueue, conf)
        
        # Start TLE auto updater
        self.tle.auto_enable()
        
        # Set thread state - self.daemon is important!
        self.daemon = True
        self.running = True

        # Start thread
        self.start()
                
    def stop(self):
        self.tle.stop()
        self.tle.join()
        self.running = False
        self.event.set()

    def run(self):
        # Wait for initialization to settle
        time.sleep(0.25)

        while self.running:
            # Find time of upcoming pass
            try:
                # Read most recent TLE
                tle = self.tle.get()
            except:
                # TLE not available
                self.event.wait(60)
                continue
            else:
                # Compute current spacecraft position
                sc = ephem.readtle(tle[0].strip(), tle[1], tle[2])
                sc.compute(self.obs)
                start = ephem.now()
                self.obs.date = ephem.now()                

                # Check pass minimum elevation
                while self.obs.date < ephem.Date(start + 24.0 * ephem.hour):
                    try:
                        # Find next pass
                        tr, azr, tt, altt, ts, azs = self.obs.next_pass(sc)
                    except:
                        # No pass found in near future
                        self.obs.date = ephem.Date(self.obs.date + ephem.hour)
                        continue
                    else:
                        # Test if pass meets minimum elevation requirement
                        if altt > self.minelv and tr < ts:
                            self.mcclog.info("Next pass for {0} (Orbit {1})".format(self.spacecraft, sc._orbit))
                            self.mcclog.info("AOS: {0}".format(ephem.localtime(tr).strftime("%Y-%m-%d %H:%M:%S")))
                            self.mcclog.info("Transit: {0}".format(ephem.localtime(tt).strftime("%Y-%m-%d %H:%M:%S")))
                            self.mcclog.info("LOS: {0}".format(ephem.localtime(ts).strftime("%Y-%m-%d %H:%M:%S")))
                            self.mcclog.info("Pass length: {0}".format(ephem.localtime(ts) - ephem.localtime(tr)))
                            self.mcclog.info("Maximum elevation: {0:.1f} degrees".format(math.degrees(altt)))
                            self.mcclog.debug("""---------------------------------------------------------------------""")
                            self.mcclog.debug("""      Date/Time        Elev/Azim    Alt     Range     RVel    FreqAdj""")
                            self.mcclog.debug("""---------------------------------------------------------------------""")
                            self.obs.date = tr
                            while self.obs.date <= ts:
                                sc.compute(self.obs)
                                self.mcclog.debug("{0} | {1:4.1f} {2:5.1f} | {3:5.1f} | {4:6.1f} | {5:+7.1f} | {6:+7.1f}".format(
                                    ephem.localtime(self.obs.date).strftime("%Y-%m-%d %H:%M:%S"),
                                    math.degrees(sc.alt),
                                    math.degrees(sc.az),
                                    sc.elevation/1000.,
                                    sc.range/1000.,
                                    sc.range_velocity,
                                    doppler_shift(self.frequency, sc.range_velocity)))
                                self.obs.date = ephem.Date(self.obs.date + ephem.minute)
                            break
                        else:
                            self.obs.date = ephem.Date(self.obs.date + ephem.hour)
                            continue

                else:
                    self.mcclog.warning("No passes found for {0}!".format(self.spacecraft))
                    # Wait for next try
                    self.event.wait(3600)
                    continue

                # Wait for next pass
                delta = ephem.localtime(tr) - datetime.datetime.today()
                sec = delta.seconds + 24 * 60 * delta.days
                self.mcclog.info("Waiting {0} seconds for AOS".format(sec))
                self.event.wait(sec)
                
                # Exit if event was set
                if self.event.is_set():
                    continue

                # Handle pass
                self.mcclog.info("AOS for {0}".format(self.spacecraft))
                self.obs.date = ephem.now()
                while self.obs.date <= ts:
                    # Calculate spacecraft position
                    sc.compute(self.obs)
                    
                    # Adjust rotor position
                    self.rotor.set_position(math.degrees(sc.az), math.degrees(sc.alt))
                    
                    # Adjust radio frequency                    
                    self.radio.set_frequency(self.frequency + doppler_shift(self.frequency, sc.range_velocity))

                    # Wait for next update
                    self.obs.date = ephem.Date(self.obs.date + 2 * ephem.second)
                    self.event.wait(2)
                    
                    # Exit if event was set
                    if self.event.is_set():
                        return
                    
                self.mcclog.info("LOS for {0}".format(self.spacecraft))
