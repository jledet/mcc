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

# Web interface

# Python imports
import threading
import ssl
import BaseHTTPServer

page = """<html>
<head>
<title>AAUSAT3 Mission Control Center</title>
</head>
<body>
<p><b>Welcome to the AAUSAT3 Mission Control Center</b></p>
<p>Your token is: {0}</p>
</body>
</html>"""

errpage = """<html>
<head>
<title>Error</title>
</head>
<body>
<p><b>The requested page could not be found</b></p>
</body>
</html>"""

class webhandler(BaseHTTPServer.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_GET(self):
        if self.path == "/":
            try:
                r = open("/dev/urandom")
                token = r.read(20)
                r.close()
            except:
                self.send_response(400)
                self.send_header("Content-type", "text/html")
                self.end_headers()
            else:
                self.send_response(200)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                self.wfile.write(page.format("".join(["{0:02x}".format(ord(i)) for i in token])))
            return
        else:
            self.send_response(404)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(errpage)

class web(threading.Thread):
    def __init__(self, port, auth, https, cert):
        threading.Thread.__init__(self, None)
        self.port = port
        self.auth = auth
        self.https = https
        self.cert = cert

        self.httpd = BaseHTTPServer.HTTPServer(("localhost", self.port), webhandler)
        self.httpd.socket = ssl.wrap_socket(self.httpd.socket, certfile=self.cert, server_side=True)
        
        self.daemon = True
        self.start()

    def stop(self):
        self.httpd.shutdown()

    def run(self):
        self.httpd.serve_forever()
