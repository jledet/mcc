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

# Rotor control using Hamlib (hamlib.org)

# Python imports
import Hamlib
import os.path

class rotor():
    def __init__(self, mcclog, conf):
        self.mcclog = mcclog
        self.rotortype = conf.rotortype
        self.rotorport = conf.rotorport
        self.rotorspeed = conf.rotorspeed
        
        # Disable all debug output from Hamlib
        Hamlib.rig_set_debug (Hamlib.RIG_DEBUG_NONE)

        # Validate rotor model
        if self.rotortype.lower() == "easycomm1":
            model = Hamlib.ROT_MODEL_EASYCOMM1
        elif self.rotortype.lower() == "easycomm2":
            model = Hamlib.ROT_MODEL_EASYCOMM2
        elif self.rotortype.lower() == "gs232":
            model = Hamlib.ROT_MODEL_GS232
        elif self.rotortype.lower() == "gs232a":
            model = Hamlib.ROT_MODEL_GS232A
        elif self.rotortype.lower() == "gs232b":
            model = Hamlib.ROT_MODEL_GS232B
        else:
            raise Exception("Unknown rotor model: {0}".format(self.rotortype))
            
        # Validate device file
        if not os.path.exists(self.rotorport):
            raise Exception("Device {0} does not exist".format(self.rotorport))
        
        # Validate serial speed
        if not self.rotorspeed in [300, 1200, 2400, 4800, 9600, 19200, 38400, 57600, 115200]:
            raise Exception("Serial speed {0} bps is not supported".format(self.rotorspeed))
        
        # Create rotor object
        self.rot = Hamlib.Rot(model)

        # Setup serial port
        self.rot.set_conf("rot_pathname", self.rotorport)
        self.rot.set_conf("serial_speed", str(self.rotorspeed))
        
        # Open rotor
        # The Python bindings for Hamlib does not return anything
        # so we have no knowledge if this was actually successful...
        self.rot.open()

        self.mcclog.info("Rotor initiated to {0} on port {1}, speed={2}".format(self.rotortype, self.rotorport, self.rotorspeed))
        
    def set_position(self, az, elv):
        if (az < 0 or az > 360):
            raise Exception("Invalid azimuth or elevation")
        else:
            self.mcclog.info("Setting rotor to AZ={0:.1f} EL={1:.1f}".format(az, elv))
            self.rot.set_position(az, elv)
