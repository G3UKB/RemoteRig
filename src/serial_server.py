#!/usr/bin/env python
#
# serial_server.py
#
# Python serial to UDP server
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
The Serial Server runs on the remote machine.
Its purpose is to -
    Initialise the remote system.
    Read data from the serial device and send to the client device over UDP.
    Read responsers from the client device and write to the serial device.
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
import platform

"""
The server consists of two threads:
    The reader and writer threads.
        and a control class responsible for startup/shutdown.
"""

#=====================================================
# Reader thread
#===================================================== 
class ReaderThrd (threading.Thread):
    
    #-------------------------------------------------
    # Initialisation
    def __init__(self, client_ip, client_port, serial_port):
        """
        Constructor
        
        Arguments
            
        """

        super(ReaderThrd, self).__init__()
        
        self.__ser_port = serial_port
        
        self.__sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        #self.__addr = client_addr
        self.__addr = (client_ip, client_port)
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
        # Send byte immediately to the client
        
        # Read 1 byte
        try:
            data = self.__ser_port.read(1)
            if data == b'':
                # Timeout seems to return an empty bytes object
                return
        except serial.SerialTimeoutException:
            # I guess we could get a timeout as well
            return
        except serial.SerialException:
            self.__terminate = True
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
    def __init__(self, port) :
        """
        Constructor
        
        Arguments
            
        """

        self.__control_port = port
        
    #-------------------------------------------------
    # Main
    def main(self) :
        """
        Constructor
        
        Arguments
            
        """
        
        # Bind address is our ip, control port is provided in args
        # Client address we get from the first receive.
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.__localip = self.__get_local_ip()
        if len(self.__localip) == 0:
            return 0
        addr = (self.__localip, self.__control_port)
        sock.bind(addr)
        sock.settimeout(1)
        
        # Wait for connect data on control port
        print ("Serial Server waiting for connect...")
        while True:
            try:
                data, client_addr = sock.recvfrom(512)
                break
            except socket.timeout:
                continue
            except KeyboardInterrupt:
                print("Terminated by user...")
                return 0
        data = pickle.loads(data)
        
        # Open local serial port
        if data["rqst"] == "connect":
            if not self.__do_connect(data["data"]["serial"]):
                print("Serial Server - Failed to connect to serial port!")
                return 0
        else:
            print("Expected connect, got ", data["rqst"])
            return 0
        
        # Start the threads
        reader_thread = ReaderThrd(client_addr[0], data["data"]["net"][1], self.__ser)
        reader_thread.start()
        writer_thread = WriterThrd(self.__localip, data["data"]["net"][0], self.__ser)
        writer_thread.start()
        
        print ("Serial Server running...")
        # Wait for disconnect data
        while True:
            try:
                data, addr = sock.recvfrom(512)
                break
            except socket.timeout:
                continue
            except KeyboardInterrupt:
                print("Terminated by user...")
                return 0
        data = pickle.loads(data)    
        # Close local port
        if data["rqst"] == "disconnect":
            self.__ser.close()
        else:
            print("Expected disconnect, got ", data["rqst"])
        
        # Close threads    
        reader_thread.terminate()
        reader_thread.join()
        writer_thread.terminate()
        writer_thread.join()
        
        print("Serial Server exiting...")
        return 0

    #-------------------------------------------------
    # Connect to serial port        
    def __do_connect(self, p):
        # Connect data p:
        try:
            self.__ser = serial.Serial( port=p["port"],
                                        baudrate=p["baud"],
                                        bytesize=p["databits"],
                                        parity=p["parity"],
                                        stopbits=p["stopbits"],
                                        timeout=p["readtimeout"],
                                        xonxoff=p["xonxoff"],
                                        rtscts=p["rtscts"],
                                        write_timeout=p["writetimeout"])
        except serial.SerialException:
            print("Failed to open device! ", p["port"])
            return False
        return True    
    
    #-------------------------------------------------
    # Get my local ip address   
    def __get_local_ip(self):
        
        if platform.system() == 'Windows':
            return socket.gethostbyname(socket.gethostname())
        elif platform.system() == 'Linux':
            ip_address = '';
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8",80))
            ip_address = s.getsockname()[0]
            s.close()
            return ip_address
        else:
            print ("Sorry, platform is %s which is not supported!" % platform.system())
            return ''
            
        
#=====================================================
# Entry point
#=====================================================

#-------------------------------------------------
# Start processing and wait for user to exit the application
def main():
    
    if len(sys.argv) != 2:
        print ("Please supply the control port number on the command line!")
        return
    try:
        app = SerialClient(int(sys.argv[1]))
        sys.exit(app.main())
        
    except Exception as e:
        print ('Exception from main SerialServer code','Exception [%s][%s]' % (str(e), traceback.format_exc()))

#-------------------------------------------------
# Enter here when run as script        
if __name__ == '__main__':
    main()