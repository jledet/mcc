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
import threading
import socket
import select
import os
import ssl
import re

# AAUSAT3 imports
import connection

TYPE_SECURE = 1
TYPE_INSECURE = 2

# Socket placeholder used for non-TLS encrypted connections
class socket_adapter():
    def __init__(self, socket, type):
        self.socket = socket
        self.type = type

    def write(self, data):
        if self.type == TYPE_SECURE:
            self.socket.write(data)
        elif self.type == TYPE_INSECURE:
            self.socket.send(data)

    def read(self, nbytes):
        if self.type == TYPE_SECURE:
            return self.socket.read(nbytes)
        elif self.type == TYPE_INSECURE:
            return self.socket.recv(nbytes)

    def get_socket(self):
        return self.socket

    def close(self):
        self.socket.close()

class connectionmanager(threading.Thread):
    def __init__(self, mcclog, db, connlist, outqueue, conf):
        threading.Thread.__init__(self, None)
        self.mcclog = mcclog
        self.connlist = connlist
        self.outqueue = outqueue
        self.db = db
        self.port = conf.listen_port
        self.max_users = conf.max_users
        self.usetls = conf.use_tls
        self.cert = os.path.abspath(conf.certfile)
        
        # Setup server socket with IPv6 support
        self.serversocket = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
        
        # Go ahead and reuse the socket if in wait state
        self.serversocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        # Allow mapped IPv4 connections
        self.serversocket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)

        # Bind to any network interface
        self.serversocket.bind(('', self.port))
        self.serversocket.listen(5)

        # Set thread state - self.daemon is important!
        self.daemon = True
        self.running = True

        # Start thread
        self.start()
    
    def __del__(self):
        self.serversocket.close()

    def stop(self):
        self.running = False

    def run(self):
        while self.running:
            try:
                (rtr, rtw, err) = select.select([self.serversocket], [], [], 1)
            except:
                self.stop()
            else:
                if not len(rtr) == 0:
                    (csocket, caddress) = self.serversocket.accept()

                    # Set address depending on IPv4 or Ipv6
                    if caddress[0].startswith("::ffff:"):
                        address = caddress[0].replace("::ffff:", "")
                    else:
                        address = caddress[0]
                    
                    # Wrap socket in TLS if required
                    if self.usetls:
                        try:
                            sslsocket = ssl.wrap_socket(csocket, server_side=True, certfile=self.cert, ssl_version=ssl.PROTOCOL_TLSv1)
                        except Exception as e:
                            self.mcclog.warning("SSL handshake failed for {0} ({1})".format(address, str(e)))
                            csocket.close()
                            continue

                        s = socket_adapter(sslsocket, TYPE_SECURE)
                    else:
                        s = socket_adapter(csocket, TYPE_INSECURE)
                    
                    # If connection and handshake succeeded
                    if self.max_users > 0 and len(self.connlist)+1 > self.max_users:
                        s.write("Too many users connected. Try again later\n")
                        self.mcclog.info("Failed to accept connection from {0} - too many users connected".format(address))
                        s.close()
                        continue

                    conn = connection.connection(self.mcclog, s, address, self.db, self.connlist, self.outqueue)
                    self.connlist.append(conn)
                    self.mcclog.info("Accepted connection from {0} - {1} {2} connected".format(address, len(self.connlist), "user" if len(self.connlist) == 1 else "users"))
                    if self.usetls:
                        self.mcclog.debug("Connection encrypted using {1} with {0} ciphers".format(sslsocket.cipher()[0], sslsocket.cipher()[1]))
