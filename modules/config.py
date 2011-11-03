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

# Read commandline parameters and default 

# Python imports
import ConfigParser
import re
try:
    import argparse
except ImportError:
    print "Error loading argparse module. Please install from http://code.google.com/p/argparse/"
    sys.exit(1)

def config(version):
    # Parse commandline
    cli_parser = argparse.ArgumentParser(description="This is the AAUSAT3 Mission Control Center server version {0}.\n\nThe program allows forwarding of CSP packets using a PEAK-System PCAN dongle\nrunning with the Linux SocketCAN drivers.\n\nThe program is released under a two-clause BSD license. Refer to the LICENSE\nfile for more information.\n\nPlease direct questions and feature requests to <jledet@space.aau.dk>\nComplaints should go to /dev/null :)\n\nThe default configuration is located in default.conf".format(version), formatter_class=argparse.RawTextHelpFormatter)
    
    cli_parser.add_argument("-c", action="store_false", dest="color", default=True, help="Disable colored logging output to stdout")
    cli_parser.add_argument("-f", dest="configfile", default="default.conf", metavar="FILE", help="configuration file (default: %(default)s)")
    cli_parser.add_argument("-o", dest="logfile", default=None, metavar="FILE", help="enable logging output to FILE.")
    cli_parser.add_argument("-v", action="store_true", dest="verbose", default=False, help="enable verbose debug output to stdout/logfile")
    
    conf = cli_parser.parse_args()
    
    # Parse config file
    file_parser = ConfigParser.RawConfigParser()
    file_parser.readfp(open(conf.configfile))
    
    conf.listen_port    = file_parser.getint("general", "port")
    conf.max_users      = file_parser.getint("general", "maxusers")
    conf.daemon         = file_parser.getboolean("general", "daemon")
    conf.pidfile        = file_parser.get("general", "pidfile")
    conf.certfile       = file_parser.get("general", "certfile")
    conf.use_tls        = file_parser.getboolean("general", "tls")

    conf.db_type        = file_parser.get("database", "type")
    conf.db_host        = file_parser.get("database", "host")
    conf.db_name        = file_parser.get("database", "name")
    conf.db_user        = file_parser.get("database", "user")
    conf.db_pass        = file_parser.get("database", "password")
    conf.db_file        = file_parser.get("database", "file")
    
    conf.csp_enable     = file_parser.getboolean("csp", "enable")
    conf.csp_host       = file_parser.getint("csp", "address")
    conf.can_ifc        = file_parser.get("csp", "interface")
    
    conf.track_enable   = file_parser.getboolean("tracking", "enable")
    conf.tleurl         = file_parser.get("tracking", "tleurl")
    conf.tleupdate      = file_parser.getint("tracking", "tleupdate")
    conf.spacecraft     = file_parser.get("tracking", "spacecraft")
    conf.doppler        = file_parser.get("tracking", "doppler")
    conf.frequency      = file_parser.getfloat("tracking", "frequency")
    conf.radioaddress   = file_parser.getint("tracking", "radioaddress")
    conf.radioport      = file_parser.getint("tracking", "radioport")
    conf.gslat          = file_parser.get("tracking", "gslat")
    conf.gslong         = file_parser.get("tracking", "gslong")
    conf.gselv          = file_parser.getint("tracking", "gselv")
    conf.minelv         = file_parser.getfloat("tracking", "minelv")
    conf.rotortype      = file_parser.get("tracking", "rotortype")
    conf.rotorport      = file_parser.get("tracking", "rotorport")
    conf.rotorspeed     = file_parser.getint("tracking", "rotorspeed")

    conf.web_enable        = file_parser.getboolean("web", "enable")
    conf.web_port        = file_parser.getint("web", "port")
    conf.web_auth        = file_parser.getboolean("web", "auth")    
    conf.web_https        = file_parser.getboolean("web", "https")
    conf.web_certfile    = file_parser.get("web", "certfile")

    return conf
