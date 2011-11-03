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

# Python imports
import sys
import os
import Queue
import threading
import time
import signal
import logging
import atexit

# AAUSAT3 imports
import config
import daemon
import connection
import database
import connmanager
import csp
import tracker
import web

VERSION = "0.8.0"

# Color output to terminal
class ColorFormatter(logging.Formatter) :
    _level_colors  = {
      "DEBUG": "\033[01;32m", "INFO": "\033[01;34m",
      "WARNING": "\033[01;35m", "ERROR": "\033[01;31m",
      "CRITICAL": "\033[01;31m"
     };    

    def format(self, record):
        if(ColorFormatter._level_colors.has_key(record.levelname)):
            record.levelname = "{0}{1}\033[0;0m".format(ColorFormatter._level_colors[record.levelname], record.levelname)
        record.name = "\033[37m\033[1m{0}\033[0;0m".format(record.name)
        return logging.Formatter.format(self, record)    

class server():

    def __init__(self):
        # Thread handles
        self.csp = None
        self.connman = None
        self.tracker = None
        self.web = None

        # Message queues
        self.inq = Queue.Queue()
        self.outq = Queue.Queue()

        # Connection list
        self.connlist = []

        # Register signal handlers
        signal.signal(signal.SIGTERM, self.sig_handler)
        signal.signal(signal.SIGHUP, self.sig_handler)

    def map_signal(self, signum):
        try:
            return (dict((k, v) for v, k in signal.__dict__.iteritems() if v.startswith('SIG') and not v.startswith('SIG_')))[signum]
        except:
            signum
        
    def sig_handler(self, signum, frame):
        self.mcclog.info("Received {0}".format(self.map_signal(signum)))
        sys.exit(1)
        
    def cleanup(self):
        # Close CSP
        if not self.csp == None:
            self.mcclog.debug("Closing CSP interface")
            self.csp.stop()
            self.csp = None
            self.mcclog.debug("CSP closed")

        # Close connection manager
        if not self.connman == None:
            self.mcclog.debug("Stopping Connection Manager")
            self.connman.stop()
            self.connman.join()
            self.connman = None
            self.mcclog.debug("Connection Manager stopped")

        # Close tracker
        if not self.tracker == None:
            self.mcclog.debug("Closing tracker")
            self.tracker.stop()
            self.tracker.join()
            self.tracker = None
            self.mcclog.debug("Tracker closed")

        if not self.web == None:
            self.mcclog.debug("Closing Web Interface")
            self.web.stop()
            self.web = None
            self.mcclog.debug("Web Inteface closed")

        self.mcclog.info("Waiting for {0} connection{1} to close".format(len(self.connlist), ("" if len(self.connlist) == 1 else "s")))

        # Close all connections...
        for conn in self.connlist:
            conn.stop()
            conn.join(5)

        # ...wait for connections to close
        if not len(self.connlist) == 0:
            self.mcclog.error("{0} connection{1} failed to close gracefully\n".format(len(self.connlist), ("" if len(self.connlist) == 1 else "s")))
        else:
            self.mcclog.debug("All connections successfully closed")

    def server(self):
        # Parse configuration
        conf = config.config(VERSION)

        # Register cleanup function
        atexit.register(self.cleanup)

        # Get logging instance
        self.mcclog = logging.getLogger("self.mcclog")
        self.mcclog.setLevel(logging.DEBUG)
        logformatter = logging.Formatter("[%(levelname)7s] %(asctime)s %(module)s: %(message)s")
        colorformatter = ColorFormatter("[%(levelname)21s] %(asctime)s %(module)s: %(message)s")
        if conf.verbose:
            loglvl = logging.DEBUG
        else:
            loglvl = logging.INFO

        if conf.daemon:
            # Daemonize
            try:
                daemon.daemonize()
            except Exception as e:
                sys.exit(1)
        else:
            # Enable logging to stdout
            streamhandler = logging.StreamHandler()
            if conf.color:
                streamhandler.setFormatter(colorformatter)
            else:
                streamhandler.setFormatter(logformatter)
            streamhandler.setLevel(loglvl)
            self.mcclog.addHandler(streamhandler)

        # Check if logging to file is enabled
        if not conf.logfile == None:
            filehandler = logging.FileHandler(conf.logfile)
            filehandler.setFormatter(logformatter)
            filehandler.setLevel(loglvl)
            self.mcclog.addHandler(filehandler)

        # Start the program
        self.mcclog.info("AAUSAT3 MCC Server {0}".format(VERSION))
        self.mcclog.info("Copyright (c) 2009-2011 Jeppe Ledet-Pedersen <jledet@space.aau.dk>")
        uname = os.uname()
        self.mcclog.info("Running on {0} {1} {2}".format(uname[0], uname[2], uname[4]))

        # Print process info
        self.mcclog.info("pid={0}, ppid={1}, pgrp={2}, sid={3}, uid={4}, euid={5}, gid={6}, egid={7}".format(os.getpid(), os.getppid(), os.getpgrp(), os.getsid(0), os.getuid(), os.geteuid(), os.getgid(), os.getegid()))

        # Test if HP is running the program as root
        if os.geteuid() == 0:
            self.mcclog.warning("Running the MCC as root is both unnecessary and a very bad idea")

        # Validate interface arguments
        if not conf.csp_enable:
            self.mcclog.warning("CSP interface disabled. Replay only mode.")
        
        # Connect to Database
        if conf.db_type == "postgresql":
            try:
                self.dbconn = database.postgresqlmanager(self.mcclog, conf)
                self.dbconn.test()
            except Exception as e:
                self.mcclog.error("Failed to start PostgreSQL Database Manager with host={0}, db={1}, user={2} ({3})".format(conf.db_host, conf.db_name, conf.db_user, str(e).replace("\n\t", " ").replace("\n", "")))
                sys.exit(1)
            self.mcclog.info("Started PostgreSQL Database Manager with host={0}, db={1}, user={2}".format(conf.db_host, conf.db_name, conf.db_user))
        elif conf.db_type == "mysql":
            try:
                self.dbconn = database.mysqlmanager(self.mcclog, conf)
                self.dbconn.test()        
            except Exception as e:
                self.mcclog.error("Failed to start MySQL Database Manager with host={0}, db={1}, user={2} ({3})".format(conf.db_host, conf.db_name, conf.db_user, str(e).replace("\n\t", " ").replace("\n", "")))
                sys.exit(1)
            self.mcclog.info("Started MySQL database manager with host={0}, db={1}, user={2}".format(conf.db_host, conf.db_name, conf.db_user))
        elif conf.db_type == "sqlite":
            try:
                self.dbconn = database.sqlitemanager(self.mcclog, conf)
                self.dbconn.test()        
            except Exception as e:
                self.mcclog.error("Failed to start SQLite Database Manager for {0} ({1})".format(conf.db_file, e))
                sys.exit(1)
            self.mcclog.info("Started SQLite database manager for {0}".format(conf.db_file))
        else:
            self.mcclog.error("{0} is not a valid database type. Use either postgresql, mysql or sqlite".format(conf.db_type))
            sys.exit(1) 

        # Initialize CSP
        if conf.csp_enable:
            try:
                self.csp = csp.csp(self.mcclog, self.dbconn, self.inq, self.outq, conf)
            except Exception as e:
                self.mcclog.error("Failed to initialize CSP ({0})".format(e))
                sys.exit(1)
            self.mcclog.info("Initialized CSP for address {0}".format(conf.csp_host))
            
        # Initialize Tracking
        if conf.track_enable:
            try:
                self.tracker = tracker.tracker(self.mcclog, self.outq, conf)
            except Exception as e:
                self.mcclog.error("Failed to initialize Tracker ({0})".format(e))
                sys.exit(1)
            self.mcclog.info("Initialized Tracker")

        # Initialize Web Interface
        if conf.web_enable:
            try:
                self.web = web.web(conf.web_port, conf.web_auth, conf.web_https, conf.web_certfile)
            except Exception as e:
                self.mcclog.error("Failed to initialize Web Interface ({0})".format(e))
                sys.exit(1)
            self.mcclog.info("Initialized Web Interface on port {0}".format(conf.web_port))

        # Initialize Connection Manager
        try:
            self.connman = connmanager.connectionmanager(self.mcclog, self.dbconn, self.connlist, self.outq, conf)
        except Exception as e:
            self.mcclog.error("Failed to initialize Connection Manager on port {0}, {1} ({2})".format(
                conf.listen_port, "connection limit: {0}".format(conf.max_users if int(conf.max_users) > 0 else "none"), e
                ))
            sys.exit(1)

        self.mcclog.info("Initialized Connection Manager on port {0}, {1}".format(
            conf.listen_port, "connection limit: {0}".format(conf.max_users if int(conf.max_users) > 0 else "none")
            ))

        if not conf.use_tls:
            self.mcclog.warning("TLS encryption is disabled! Eve can read your data...")

        self.mcclog.info("Startup sequence completed - Listening for incoming connections")

        # Enter main loop
        rx_packets = 0
        tx_packets = 0
        while True:
            try:
                packet = self.inq.get(True, 30)
            except Queue.Empty:
                pass
            except KeyboardInterrupt:
                print ""
                self.mcclog.info("Closing AAUSAT3 MCC Server")
                sys.exit(0)
            except Exception as e:
                self.mcclog.error("Caught exception ({0})".format(e))
                sys.exit(1)
            else:
                if packet.source == conf.csp_host and packet.sport >= 17:
                    tx_packets += 1
                else:
                    rx_packets += 1
                self.mcclog.debug("Distributing packet: {0}".format(packet.debug()))
                self.mcclog.debug("Packets transmitted: {0}, Packets received: {1}".format(tx_packets, rx_packets))
                # Add packet to packet queues
                for conn in self.connlist:
                    if conn.enabled and conn.authorized:
                        conn.queue.put(packet)
        print "STOPPED unexpect"
