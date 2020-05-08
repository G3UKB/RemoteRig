#!/usr/bin/env python
#
# serial_client.py
#
# Python serial to UDP client
# 
# Copyright (C) 2020 by G3UKB Bob Cowdery
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#    
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#    
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#    
#  The author can be reached by email at:   
#     bob@bobcowdery.plus.com
#

"""
The Serial Server client runs on the local machine.
Its purpose is to -
    Initialise the remote system.
    Read data from the serial device and send to the romte device over UDP.
    Read responsers from the remote device and write to the serial device.
"""

import os, sys
import logging
import traceback
from time import sleep
import serial
import socket
import threading
import queue
import pickle
import configparser

"""
The client consists of two threads:
    The reader and writer threads.
        and a control class responsible for startup/shutdown.
"""

#=====================================================
# Reader thread
#===================================================== 
class ReaderThrd (threading.Thread):
    
    #-------------------------------------------------
    # Initialisation
    def __init__(self, server_ip, server_port, serial_port):
        """
        Constructor
        
        Arguments
            
        """

        super(ReaderThrd, self).__init__()
        
        self.__ser_port = serial_port
        
        self.__sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.__addr = (server_ip, server_port)
        self.__sock.settimeout(1)
        
        self.__terminate = False
    
    #-------------------------------------------------
    # Terminate thread
    def terminate(self):
        """ Terminate thread """
        
        self.__terminate = True
    
    #-------------------------------------------------
    # Thread entry point    
    def run(self):
        """ Listen for events """

        # Processing loop
        while not self.__terminate:
            self.__process()
            
        print ("Serial Client - Reader thread exiting...")

    #-------------------------------------------------
    # Process exchanges
    def __process(self):
        # We wait for 1 byte of data from the serial class instance
        # Send byte immediately to the server
        
        # Read 1 byte
        try:
            data = self.__ser_port.read(1)
            if data == b'':
                # Timeout seems to return an empty bytes object
                return 
        except serial.SerialTimeoutException:
            # I guess we could get a timeout as well
            return
        
        # Dispatch to server
        try:
            self.__sock.sendto(data, self.__addr)
        except socket.timeout:
            print ("Error sending UDP data!")
            return

#=====================================================
# Writer thread
#===================================================== 
class WriterThrd (threading.Thread):
    
    #-------------------------------------------------
    # Initialisation
    def __init__(self, local_ip, local_port, serial_port):
        """
        Constructor
        
        Arguments
            
        """

        super(WriterThrd, self).__init__()
        
        self.__ser_port = serial_port
        
        self.__sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.__addr = (local_ip, local_port)
        self.__sock.bind(self.__addr)
        self.__sock.settimeout(1)
        
        self.__terminate = False
    
    #-------------------------------------------------
    # Terminate thread
    def terminate(self):
        """ Terminate thread """
        
        self.__terminate = True
    
    #-------------------------------------------------
    # Thread entry point    
    def run(self):
        """ Listen for events """

        # Processing loop
        while not self.__terminate:
            self.__process()
            
        print ("Serial Client - Writer thread exiting...")

    #-------------------------------------------------
    # Process exchanges
    def __process(self):
        # We wait for data from the server
        # Write data immediately to the serial port
        
        # Wait for data from server
        try:
            data, self.__addr = self.__sock.recvfrom(10)
        except socket.timeout:
            # No response is not an error
            return
        except socket.error as err:
            print("Socket error: {0}".format(err))
            # Probably not connected
            return

        # Write data to serial port
        try:
            self.__ser_port.write(data) 
        except serial.SerialTimeoutException:
            # I guess we could get a timeout as well
            pass
        
#=====================================================
# Main server class
#===================================================== 
class SerialClient: 
    #-------------------------------------------------
    # Initialisation
    def __init__(self) :
        """
        Constructor
        
        Arguments
            
        """

    #-------------------------------------------------
    # Main
    def main(self) :
        """
        Constructor
        
        Arguments
            
        """
        
        # Get configuration data
        config = configparser.ConfigParser()
        params = config.read('serial.conf')
        if len(params) == 0:
            print ("Failed to read 'serial.conf', please create and try again!")
            return 0
        # Assemble params into logical structures
        self.__assemble_params(params)
        
        # Create local control socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        addr = (self.__net_p['serverip'], self.__net_p['controlport'])
        sock.settimeout(1)
        
        # Send initialisation data to server
        try:
            # Send connect data to the remote device
            sock.sendto(pickle.dumps({"rqst": "connect", "data": self.__svr_p)}, addr)
        except socket.timeout:
            print ("Error sending connect request!")
            return 0
        
        # Open local serial port
        if not self.__do_connect(self.__cli_p):
            print("Serial Client - Failed to connect to serial port!")
            return 0
        
        # Start the threads
        reader_thread = ReaderThrd(self.__net_p['serverip'], self.__net_p['serverport'], self.__ser)
        reader_thread.start()
        writer_thread = WriterThrd(self.__net_p['localip'], self.__net_p['localport'], self.__ser)
        writer_thread.start()
        
        print ("Serial Client running...")
        # Wait for exit
        while True:
            try:
                sleep(1)
            except KeyboardInterrupt:
                break
        
        # Uninitialiee the server
        try:
            # Send disconnect request to the remote device
            sock.sendto(pickle.dumps({"rqst": "disconnect", "data": []}), addr)
        except socket.timeout:
            print ("Error sending disconnect request!")
        
        # Close threads    
        reader_thread.terminate()
        reader_thread.join()
        writer_thread.terminate()
        writer_thread.join()
        
        print("Serial Client exiting...")
        return 0

    #-------------------------------------------------
    # Connect to serial port    
    def __assemble_params(self, c) {
        
        # Check we have the required sections
        if not 'network' c.sections:
            print "Missing 'network' section in configuration!"
            return False
        if not 'serialports' c.sections:
            print "Missing 'serialports' section in configuration!"
            return False
        if not 'cliparams' c.sections:
            print "Missing 'cliparams' section in configuration!"
            return False
        if not 'svrparams' c.sections:
            print "Missing 'svrparams' section in configuration!"
            return False
        
        # Assemble parameters into dictionaries
        self.__net_p = {}
        self.__cli_p = {}
        self.__svr_p = {}
        
        # Ref to the config sections
        s1 = c['network']
        s2 = c['serialports']
        s3 = c['cliparams']
        s4 = c['svrparams']
        
        # Collect params into dictionaries
        try:
            # Network
            self.__net_p['serverip'] = s1['server']
            self.__net_p['controlport'] = int(s1['controlport'])
            self.__net_p['serverport'] = int(s1['remoteport'])                                            
            self.__net_p['localport'] = int(s1['localport'])
            self.__net_p['localip'] = socket.gethostbyname(socket.gethostname)
            # Serial
            self.__cli_p['port'] = s2['client']
            self.__svr_p['port'] = s2['server']
            self.__cli_p['baud'] = s3['baudrate']
            self.__svr_p['baud'] = s4['baudrate']
            self.__cli_p['databits'] = s3['databits']
            self.__svr_p['databits'] = s4['databits']
            self.__cli_p['parity'] = s3['parity']
            self.__svr_p['parity'] = s4['parity']
            self.__cli_p['stopbits'] = s3['stopbits']
            self.__svr_p['stopbits'] = s4['stopbits']
            self.__cli_p['readimeout'] = s3['readimeout']
            self.__svr_p['readimeout'] = s4['readimeout']
            self.__cli_p['readimeout'] = s3['readimeout']
            self.__svr_p['readimeout'] = s4['readimeout']
            self.__cli_p['writetimeout'] = s3['writetimeout']
            self.__svr_p['writetimeout'] = s4['writetimeout']
            self.__cli_p['xonxoff'] = s3['xonxoff']
            self.__svr_p['xonxoff'] = s4['xonxoff']
            self.__cli_p['rtscts'] = s3['rtscts']
            self.__svr_p['rtscts'] = s4['rtscts']
        except KeyError as k:
            print ("Missing: %s from configuration!" % k)
            return False
        return True
    }

    #-------------------------------------------------
    # Connect to serial port    
    def __do_connect(self, p):
        # Connect data p:
        try:
            self.__ser = serial.Serial( port=p["port"],
                                        baudrate=p["baud"],
                                        bytesize=p["data_bits"],
                                        parity=p["parity"],
                                        stopbits=p["stopbits"],
                                        timeout=p["readtimeout"],
                                        xonxoff=p["xonxoff"],
                                        rtscts=p["rtscts"],
                                        write_timeout=p["writetimeout"]
        except serial.SerialException:
            print("Failed to open device! ", p["port"])
            return False
        return True    
    
#=====================================================
# Entry point
#=====================================================

#-------------------------------------------------
# Start processing and wait for user to exit the application
def main():
    try:
        app = SerialClient()
        sys.exit(app.main())
        
    except Exception as e:
        print ('Exception from main SerialServer code','Exception [%s][%s]' % (str(e), traceback.format_exc()))

#-------------------------------------------------
# Enter here when run as script        
if __name__ == '__main__':
    main()