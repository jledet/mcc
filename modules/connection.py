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
import socket
import threading
import string
import time
import Queue
import hashlib
import re
import sys
import select

# AAUSAT3 imports
import server
import database
import csp

class reader(threading.Thread):
    def __init__(self, mcclog, queue, socket, address, csem):
        threading.Thread.__init__(self, None)
        self.mcclog = mcclog
        self.queue = queue
        self.socket = socket
        self.address = address
        self.csem = csem

        # Start thread
        self.running = True
        self.start()
    
    def stop(self):
        self.running = False

    def run(self):
        while self.running:
            try:
                packet = self.queue.get(True, 0.1)
                self.csem.acquire()
                self.socket.write("PACKET {0}\n".format(packet.tostring()))
                self.csem.release()
            except Queue.Empty:
                pass
            except socket.error:
                self.mcclog.error("Failed to send packet to {0}".format(self.address))
            finally:
                self.csem.release()

class connection(threading.Thread):
    def __init__ (self, mcclog, socket, address, dbmanager, connlist, outqueue):
        threading.Thread.__init__(self, None)
        self.mcclog = mcclog
        self.socket = socket
        self.address = address
        self.dbmanager = dbmanager
        self.connlist = connlist
        self.outqueue = outqueue
        self.queue = Queue.Queue()

        # Get database connection
        self.db = self.dbmanager.get_connection()

        # Connection semaphore
        self.csem = threading.Semaphore()

        self.authorized = False
        self.enabled = False
        self.user = "unknown"

        # Failed login attempts
        self.failed = 0
        self.max_failed = 3

        # Start threads
        self.reader = reader(self.mcclog, self.queue, self.socket, self.address, self.csem)

        self.running = True
        self.start()

    def stop(self):
        self.reader.stop()
        self.reader.join()
        self.running = False

    def run(self):
        # Wait for connection to appear in list
        while not self.connlist.count(self):
            pass 

        users = len(self.connlist)
        self.socket.write("* OK AAUSAT3 MCC Server {0} ready ({1} {2} connected)\n".format(server.VERSION, users, "user" if users == 1 else "users")) 

        while self.running:
            # Read messages and split on newline
            error = False
            messages = ""
            while not messages.endswith("\n"):
                # Wait for data to be available
                (rtr, rtw, err) = select.select([self.socket.get_socket()], [], [], 1)
                
                # Check if thread was stopped while waiting
                if not self.running:
                    error = True
                    break

                # Check if select timed out
                if len(rtr) == 0:
                    continue
                
                # Try to read data
                try:
                    data = self.socket.read(2048)
                except socket.error as e:
                    self.mcclog.debug("Socket error on connection with {0} ({1})".format(self.address, str(e)))
                    error = True
                    break
                
                if not data:
                    error = True
                    break
                else:
                    messages += data

            if error:
                self.stop()
                break

            messages = messages.strip().split("\n")
            
            # Iterate through received messages
            for msg in messages:
        
                # If no data was received, close the connection
                if not msg:
                    self.stop()
                    break

                # Split to fields
                msg = msg.strip().split()

                # Acquire connection semaphore
                self.csem.acquire()
        
                # Extract command
                cmd = msg[0].upper()

                if cmd == "USER":
                    if len(msg) == 3:
                        if self.db.validate_user(msg[1], hashlib.sha1(msg[2]).hexdigest()):
                            self.authorized = True
                            self.user = msg[1]
                            self.socket.write("USER OK Welcome {0}\n".format(msg[1]))
                            self.mcclog.debug("Successfully authorized {0}@{1}".format(msg[1], self.address))
                        else:
                            time.sleep(1)
                            self.socket.write("USER FAIL Invalid username or password\n")
                            self.mcclog.debug("Failed to authorize {0}@{1}".format(msg[1], self.address))
                            self.failed += 1
                            if self.failed >= self.max_failed:
                                self.mcclog.warning("Too many failed login attempts for {0}@{1} - closing connection".format(self.user, self.address))
                                self.socket.write("* FAIL Too many failed login attempts\n")
                                self.csem.release()
                                self.stop()
                                break
                    else:
                        self.socket.write("USER FAIL Invalid format\n")
                        self.mcclog.debug("Received invalid USER command from {0}@{1}".format(self.user, self.address))

                elif cmd == "SEND":
                    if self.authorized:
                        if len(msg) == 3 and re.search("^(3[01]|[0-2]?[0-9]):(6[0-3]|[0-5]?[0-9])$", msg[1]) and re.search("^([0-9a-f]{2}){1,256}$", msg[2]):
                            id = msg[1].split(":")
                            # Add packet to outgoing buffer
                            # Source host and port is added by CSP implementation
                            packet = csp.packet(-1, -1, int(id[0]), int(id[1]), tuple([int(d, 16) for d in re.findall("[0-9a-f]{2}", msg[2])]))
                            try:
                                self.outqueue.put(packet, True, 1)
                            except Queue.Full:
                                self.socket.write("SEND FAIL Unable to add packet to outgoing queue\n")
                                self.mcclog.debug("Packet queue full for {0}@{1}".format(self.user, self.address))
                            else:
                                self.socket.write("SEND OK Packet sent\n")
                                self.mcclog.debug("Added CSP packet from {0}@{1} to outgoing queue: {2}".format(self.user, self.address, packet.debug()))
                        else:
                            self.socket.write("SEND FAIL Invalid format\n")
                            self.mcclog.debug("Received invalid SEND command from {0}@{1}".format(self.user, self.address))
                    else:
                        self.socket.write("SEND FAIL Please login first\n")
                        self.mcclog.debug("User not authorized to SEND")

                elif cmd == "REPLAY":
                    if self.authorized:
                        if len(msg) == 2 and re.search("^[0-9]+$", msg[1]):
                            num = msg[1]
                            lst = self.db.replay(num)
                            self.socket.write("REPLAY OK Replaying {0} packets\n".format(len(lst)))
                            self.mcclog.debug("Replaying {0} packets to {1}@{2}".format(len(lst), self.user, self.address))
                            for p in lst:
                                self.queue.put(p)
                        else:
                            self.socket.write("REPLAY FAIL Invalid format\n")
                            self.mcclog.debug("Received invalid REPLAY command from {0}@{1}".format(self.user, self.address))
                    else:
                        self.socket.write("REPLAY FAIL Please login first\n")
                        self.mcclog.debug("Received unauthorized REPLAY request from {0}".format(self.address))

                elif cmd == "START":
                    if self.authorized:
                        self.enabled = True
                        self.socket.write("START OK Packet forwarding started\n")
                        self.mcclog.debug("Starting packet forwarding to {0}@{1}".format(self.user, self.address))
                    else:
                        self.socket.write("START FAIL Please login first\n")
                        self.mcclog.debug("Received unauthorized START request from {0}".format(self.address))

                elif cmd == "STOP":
                    if self.authorized:
                        self.enabled = False
                        self.socket.write("STOP OK Packet forwarding stopped\n")
                        self.mcclog.debug("Stopping packet forwarding to {0}@{1}".format(self.user, self.address))
                    else:
                        self.socket.write("STOP FAIL Please login first\n")
                        self.mcclog.debug("Received unauthorized STOP request from {0}".format(self.address))

                elif cmd == "QUIT":
                    self.socket.write("QUIT OK Closing connection\n")
                    self.csem.release()
                    self.stop()
                    break

                else:
                    self.socket.write("* FAIL Invalid command '{0}'\n".format(cmd))
                    self.mcclog.debug("Received unknown command {0} from {1}".format(cmd, self.address))

                # Release connection semaphore
                self.csem.release()

        self.socket.get_socket().close()
        self.connlist.remove(self)
        self.mcclog.info("Closed connection from {0}@{1} - {2} {3} connected".format(self.user, self.address, len(self.connlist), "user" if users-1 == 1 else "users"))
        self.stop()
