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
import string
import threading
import datetime
import time
import Queue
import ctypes

# AAUSAT3 imports
import pycsp

def debug_hook(level, string):
    if debug_mcclog == None:
	return

    # Remove carriage return and newline
    string = string.replace("\r", "").replace("\n", "")
    
    if level == pycsp.CSP_INFO:
	debug_mcclog.info(string)
    elif level == pycsp.CSP_ERROR:
	debug_mcclog.error(string)
    elif level == pycsp.CSP_WARN:
	debug_mcclog.warning(string)
    else:
	debug_mcclog.debug(string)

    return

# Setup debug hook if available
debug_mcclog = None
try:
    hook = pycsp.DEBUG_FUNC(debug_hook)
    pycsp.csp_debug_hook_set(hook)
except:
    pass
    
class packet():
    def __init__(self, source, sport, dest, dport, data):
        self.source = source
        self.sport = sport
        self.dest = dest
        self.dport = dport
        self.data = data

        # Time stores microsecons after the epoch
        self.time = int(round(time.time()*1000000))

    def update_time(self, time):
        self.time = time

    def tostring(self):
        return "{0}:{1} {2}:{3} {4} {5}".format(self.source, self.sport, self.dest, self.dport , "".join(["{0:02x}".format(d) for d in self.data]), self.time)

    def debug(self):
        if not self.source == -1 and not self.sport == -1:
            return "src={0} sport={1} dst={2} dport={3} length={4}".format(self.source, self.sport, self.dest, self.dport, len(self.data))
        else:
            return "dst={0} dport={1} length={2}".format(self.dest, self.dport, len(self.data))
            
class csp():
    def __init__(self, mcclog, dbmanager, inqueue, outqueue, conf):
        global debug_mcclog
	self.mcclog = mcclog
        self.dbmanager = dbmanager
        self.inqueue = inqueue
        self.outqueue = outqueue
        self.csp_host = conf.csp_host
        self.ifc = conf.can_ifc
	debug_mcclog = mcclog
        
	# CAN configuration 
	can_conf = pycsp.can_socketcan_conf(ctypes.c_char_p(self.ifc))

        # Init CSP
        pycsp.csp_buffer_init(25, 320)
        pycsp.csp_init(self.csp_host)     
        pycsp.csp_can_init(1, ctypes.byref(can_conf), ctypes.sizeof(can_conf))
        pycsp.csp_route_set(pycsp.CSP_DEFAULT_ROUTE, pycsp.csp_if_can, pycsp.CSP_NODE_MAC)
        pycsp.csp_route_start_task(0, 1) # Args ignored on posix
        
        # Start processing threads
        self.writer = writer(self.mcclog, self, self.outqueue, self.dbmanager, conf)
        self.reader = reader(self.mcclog, self, self.inqueue, self.dbmanager)
        self.service = service(self.mcclog)
                
    def __del__(self):
        pass

    def stop(self):
        self.writer.stop()
        self.reader.stop()
        self.service.stop()
        self.writer.join()
        self.reader.join()
        self.service.join()
        
class service(threading.Thread):
    def __init__(self, mcclog):
        self.mcclog = mcclog

        # Create socket for incoming connections
        try:
            self.socket = pycsp.csp_socket(0)
        except:
            self.mcclog.error("Failed to create socket")

        try:
            pycsp.csp_bind(self.socket, pycsp.CSP_ANY)
        except:
            self.mcclog.error("Failed to bind CSP service handler")
            
        try:
            pycsp.csp_listen(self.socket, 10)
        except:
            self.mcclog.error("Failed to create connection backlog queue")
        
        # Start thread
        threading.Thread.__init__(self, None)
        
        # Set thread state - self.daemon is important!
        self.daemon = True
        self.running = True

        # Start thread
        self.start()
        
    def stop(self):
        self.running = False
    
    def run(self):
        while self.running:
            try:
                conn = pycsp.csp_accept(self.socket, 1000)
            except pycsp.NullPointerException:
                continue
            
            # Got a new connection
            try:
                packet = pycsp.csp_read(conn, 1000)
            except:
                # Ignore and let finally clause close
                pass
            else:
                pycsp.csp_service_handler(conn, packet)
            finally:
                pycsp.csp_close(conn)

class writer(threading.Thread):
    def __init__(self, mcclog, canhandle, outq, dbmanager, conf):
        self.mcclog = mcclog
        self.outq = outq
        self.db = dbmanager.get_connection()
        self.csp_host = conf.csp_host
        
        # Start thread
        threading.Thread.__init__(self, None)
        
        # Set thread state - self.daemon is important!
        self.daemon = True
        self.running = True

        # Start thread
        self.start()

    def stop(self):
        self.running = False
    
    def run(self):
        while self.running:
            try:
                # Read next outgoing CSP packet
                packet = self.outq.get(True, 0.1)
            except:
                pass
            else:
                self.mcclog.debug("Sending CSP packet: {0}".format(packet.debug()))
                
                # Get length of data
                plength = len(packet.data)
                
                # Get CSP buffer element
                try:
                    buf_packet = ctypes.cast(pycsp.csp_buffer_get(plength), ctypes.POINTER(pycsp.csp_packet_t))
                except pycsp.NullPointerException:
                    self.mcclog.warning("Failed to get CSP packet buffer")
                    continue
                
                buf_packet.contents.data = tuple(packet.data)
                buf_packet.contents.length = plength
                
                # Connect
                try:
                    conn = pycsp.csp_connect(pycsp.CSP_PRIO_NORM, packet.dest, packet.dport, 1000, 0)
                except pycsp.NullPointerException:
                    pycsp.csp_buffer_free(buf_packet)
                    self.mcclog.warning("Failed to connect to {0}:{1}".format(packet.dest, packet.dport))
                    continue
                
                # Send packet
                try:
                    pycsp.csp_send(conn, buf_packet, 1000)
                except:
                    pycsp.csp_buffer_free(buf_packet)
                    pycsp.csp_close(conn)
                    self.mcclog.warning("Timeout while sending to {0}:{1}".format(packet.dest, packet.dport))
                    continue
                    
                # Close connection
                pycsp.csp_close(conn)
                
                # Log frame to database
                try:
                    self.db.log_data(packet, 'OUT')
                except Exception as e:
                    self.mcclog.warning("Failed to log data: {0}".format(e))

class reader(threading.Thread):
    def __init__(self, mcclog, canhandle, inq, dbmanager):
        self.mcclog = mcclog
        self.inq = inq
        self.db = dbmanager.get_connection()

        # Enable CSP promiscuous mode
        pycsp.csp_promisc_enable(20)

        # Start thread
        threading.Thread.__init__(self, None)
        
        # Set thread state - self.daemon is important!
        self.daemon = True
        self.running = True

        # Start thread
        self.start()

    def stop(self):
        self.running = False
    
    def run(self):
        while self.running:
            # Read next incoming CSP packet
            try:
                ppacket = pycsp.csp_promisc_read(1000)
            except pycsp.NullPointerException:
                continue
            
            # Create new packet object  
            p = packet(ppacket.contents.id.src, 
                ppacket.contents.id.sport, 
                ppacket.contents.id.dst, 
                ppacket.contents.id.dport, 
                ppacket.contents.data[0:ppacket.contents.length])

            # Free buffer
            pycsp.csp_buffer_free(ppacket)
            
            # Log and add CSP packet to incoming queue
            self.inq.put(p)
            self.mcclog.debug("Received CSP packet: {0}".format(p.debug()))
            try:
                self.db.log_data(p, 'IN')
            except Exception as e:
                self.mcclog.warning("Failed to log data: {0}".format(e))

