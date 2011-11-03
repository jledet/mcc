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
import time
import re

# AAUSAT3 imports
import csp

# This could be ported to SQLalchemy

# Database connection base class
class dbconn():
    conn = None

    def __init__(self, mcclog, placeholder):
        self.mcclog = mcclog
        self.placeholder = placeholder

    def __del__(self):
        if not self.conn == None:
            self.conn.close()

    def validate_user(self, user, password):
        self.cur.execute("select * from users where username={0} and password={0}".format(self.placeholder), (user, password))
        self.conn.commit()
        if len(self.cur.fetchall()) == 1:
            return True
        else:
            return False

    def log_data(self, packet, dir):
        query = "insert into data (time,dir,source,dest,sport,dport,data) values ({0},{0},{0},{0},{0},{0},{0})".format(self.placeholder)
        fields = (packet.time, dir, packet.source, packet.dest, packet.sport, packet.dport, "".join(["{0:02x}".format(p) for p in packet.data])) 
        self.cur.execute(query, fields)
        self.conn.commit()

    def replay(self, num):
        lst = []
        query = "select * from (select * from data where dir='IN' order by time desc limit {0}) as tmp order by time asc;".format(self.placeholder)
        self.cur.execute(query, (num,))
        self.conn.commit()
        for row in self.cur.fetchall():
            (pid, time, dir, source, sport, dest, dport, data) = row
            if data == "":
                t = ()
            else:
                t = tuple([int(d, 16) for d in re.findall("[0-9a-f]{2}", data)])
            packet = csp.packet(source, sport, dest, dport, t)
            packet.update_time(time)
            lst.append(packet)
        return lst

# SQLite database class
class sqlitedb(dbconn):

    def __init__(self, mcclog, conf):
        # Delayed import as sqlite3 should not be required if SQLite is not used
        import sqlite3

        dbconn.__init__(self, mcclog, "?")
        self.conn = sqlite3.connect(conf.db_file, check_same_thread=False)
        self.cur = self.conn.cursor()

# MySQL database class
class mysqldb(dbconn):

    def __init__(self, mcclog, conf):
        # Delayed import as MySQLdb should not be required if MySQL is not used
        import MySQLdb

        dbconn.__init__(self, mcclog, "%s")
        self.conn = MySQLdb.connect(host=conf.db_host, user=conf.db_user, passwd=conf.db_pass, db=conf.db_name)
        self.cur = self.conn.cursor()

# PostgreSQL database class
class postgresqldb(dbconn):

    def __init__(self, mcclog, conf):
        # Delayed import as psycopg2 should not be required if PostgreSQL is not used
        import psycopg2
        import psycopg2.extras
        
        dbconn.__init__(self, mcclog, "%s")
        self.conn = psycopg2.connect("dbname='{0}' user='{1}' host='{2}' password='{3}' sslmode='require'".format(conf.db_name, conf.db_user, conf.db_host, conf.db_pass))
        self.cur = self.conn.cursor()

# Database manager base class
class dbmanager():

    def __init__(self, mcclog, conf):
        self.mcclog = mcclog
        self.conf = conf
    
    def test(self):
        # Test connection and structure
        c = self.get_connection()
        conn = c.conn
        cur = conn.cursor()
        try:
            cur.execute("select uid,username,password from users limit 1;")
            cur.execute("select pid,time,dir,source,dest,sport,dport,data from data limit 1;")
            conn.commit()
        except Exception as e:
            raise Exception("Incorrect database structure: {0}".format(e))

# SQLite database manager
class sqlitemanager(dbmanager):

    def get_connection(self):
        return sqlitedb(self.mcclog, self.conf)

# MySQL database manager
class mysqlmanager(dbmanager):

    def get_connection(self):
        return mysqldb(self.mcclog, self.conf)

# PostgreSQL manager
class postgresqlmanager(dbmanager):

    def get_connection(self):
        return postgresqldb(self.mcclog, self.conf)

