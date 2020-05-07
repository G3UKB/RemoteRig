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
    def __init__(self, port):
        """
        Constructor
        
        Arguments
            
        """

        super(ReaderThrd, self).__init__()
        
        self.__ser_port = port
        
        self.__sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        #self.__remote_ip = '192.168.1.110'
        self.__remote_ip = 'localhost'
        self.__remote_port = 10001
        self.__addr = (self.__remote_ip, self.__remote_port)
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
    def __init__(self, port):
        """
        Constructor
        
        Arguments
            
        """

        super(WriterThrd, self).__init__()
        
        self.__ser_port = port
        
        self.__sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        #self.__remote_ip = '192.168.1.110'
        self.__remote_ip = 'localhost'
        self.__remote_port = 10002
        self.__addr = (self.__remote_ip, self.__remote_port)
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
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        #self.__remote_ip = '192.168.1.110'
        remote_ip = 'localhost'
        remote_port = 10000
        addr = (remote_ip, remote_port)
        sock.settimeout(1)
        
        # Send initialisation data
        # Temp connect data
        server_connect_data = {"port": "COM4", "baud": 9600, "data_bits": 8, "parity": "N", "stop_bits": 2}
        try:
            # Send connect data to the remote device
            sock.sendto(pickle.dumps({"rqst": "connect", "data": server_connect_data}), addr)
        except socket.timeout:
            print ("Error sending connect request!")
            return 0
        
        # Open local port
        # Temp connect data
        client_connect_data = {"port": "COM3", "baud": 9600, "data_bits": 8, "parity": "N", "stop_bits": 2}
        if not self.__do_connect(client_connect_data):
            print("Serial Client - Failed to connect to serial port!")
            return 0
        
        # Start the threads
        reader_thread = ReaderThrd(self.__ser)
        reader_thread.start()
        writer_thread = WriterThrd(self.__ser)
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
    def __do_connect(self, data):
        # Connect data:
        # {"port": d, "baud": b, "data_bits": b, "parity": p, "stop_bits": s}
        try:
            self.__ser = serial.Serial( port=data["port"],
                                        baudrate=data["baud"],
                                        bytesize=data["data_bits"],
                                        parity=data["parity"],
                                        stopbits=data["stop_bits"],
                                        timeout=0.05,
                                        xonxoff=0,
                                        rtscts=0,
                                        write_timeout=0.05)
        except serial.SerialException:
            print("Failed to open device! ", data["port"])
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