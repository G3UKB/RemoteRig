#!/usr/bin/env python
#
# ss_server.py
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
The Serial Server server runs on the remote machine, usually an RPi.
Its purpose is to -
    Read UDP packets from the host and write the raw data to a serial device.
    Read raw data from the serial device and send it to the UDP address of the hosr.
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
The server consists of two threads:
    The serial thread and the UDP thread.
        and a control class responsible for startup/shutdown.
"""

#=====================================================
# UDP thread
#===================================================== 
class UDPThrd (threading.Thread):
    
    #-------------------------------------------------
    # Initialisation
    def __init__(self, reader_q, writer_q):
        """
        Constructor
        
        Arguments
            reader_q    -- incoming data/requests
            writer_q    -- outgoing data/requests
            
        """

        super(UDPThrd, self).__init__()
        
        self.__reader_q = reader_q
        self.__writer_q = writer_q
        
        self.__sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.__sock.bind(("localhost", 10001))
        self.__sock.settimeout(3)
        
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
        
        while not self.__terminate:
            try:
                data, self.__addr = self.__sock.recvfrom(512)
            except socket.timeout:
                continue
            self.__process(pickle.loads(data))
            
        print("Serial Server - UDP thread exiting...")

    #-------------------------------------------------
    # Process data
    def __process(self, data):
        # We simply dispatch data to the serial class instance
        # The client is responsible for proper formatting of the request
        print(data)
        try:
            self.__writer_q.put(data, timeout=0.1)
        except queue.Full:
            print("Exception queue full writing request data!")
            return False
        
        # Wait for any response
        try:
            item = self.__reader_q.get(timeout=0.1)
            self.__sock.sendto( pickle.dumps([{"resp":True, "data":[item]}]), self.__addr)
        except queue.Empty:
            self.__sock.sendto (pickle.dumps([{"resp":False, "data":[]}]), self.__addr)
        
#=====================================================
# Serial thread
#===================================================== 
class SerialThrd (threading.Thread):
    
    #-------------------------------------------------
    # Initialisation
    def __init__(self, reader_q, writer_q):
        """
        Constructor
        
        Arguments
            reader_q    -- incoming data/requests
            writer_q    -- outgoing data/requests
            
        """
        
        super(SerialThrd, self).__init__()

        self.__reader_q = reader_q
        self.__writer_q = writer_q
        self.__terminate = False
        self.__ser = None
        self.__resp = []
    
    #-------------------------------------------------
    # Terminate thread
    def terminate(self):
        """ Terminate thread """
        
        self.__terminate = True
    
    #-------------------------------------------------
    # Thread entry point    
    def run(self):
        """
        Wait for data from q:
        Format for requests is:
            {"rqst":rqst_type, "data":[parameters or data]}
            reqst_type : "connect", "disconnect", "serial_data"
        
        """
        
        # Outer loop
        while not self.__terminate:
            # Wait for the connect data
            while True:
                if self.__terminate:
                    print("Serial Server - Serial thread exiting...")
                    return
                try:
                    item = self.__reader_q.get(timeout=1.0)
                    if item["rqst"] == "connect":
                        if self.__do_connect(item["data"]):
                            break
                        else:
                            print("Failed to connect to serial port!")
                            return
                    else:
                        continue
                except queue.Empty:
                    continue
            
            # Main thread loop            
            while not self.__terminate:
                # Process send data
                # Wait for response and dispatch
                # We do not expect unsolicited data from the serial port
                try:
                    item = self.__reader_q.get(timeout=0.1)
                    if item["rqst"] == "disconnect":
                        if self.__do_disconnect():
                            break
                        else:
                            print("Failed to disconnect from serial port!")
                            return
                    elif item["rqst"] == "data":
                        if self.__write_data(item["data"]):
                            data = self.__read_data()
                            # There may be no response data so we can't treat it as an error
                            if len(data) > 0:
                                self.__dispatch_data(data)
                            continue
                        else:
                            print("Failed to write [all] data to serial port! Attempting to continue.")
                            continue
                except queue.Empty:
                    continue
        print("Serial Server - Serial thread exiting...")
        
    #-------------------------------------------------
    # Connect to serial port    
    def __do_connect(self, data):
        # Connect data:
        # {"port": d, "baud": b, "data_bits": b, "parity": p, "stop_bits": s}
        # Data is an array which contains 1 item for connect
        p = data[0]
        try:
            self.__ser = serial.Serial( port=p["port"],
                                        baudrate=p["baud"],
                                        bytesize=p["data_bits"],
                                        parity=p["parity"],
                                        stopbits=p["stop_bits"],
                                        timeout=0.5,
                                        xonxoff=0,
                                        rtscts=0,
                                        write_timeout=0.5)
        except serial.SerialException:
            print("Failed to open device %s!", p["port"])
            return False
        except serial.ValueException:
            print("Parameter error in serial port %s parameters!", p["port"])
            return False
        return True    
    
    #-------------------------------------------------
    # Disconnect from serial port    
    def __do_disconnect():
        
        self.__ser.close()
        return True
    
    #-------------------------------------------------
    # Write data to serial port 
    def __write_data(self, data):
       
        # Write data is a bytearray
        try:
            bytes_written = self.__ser.write(data)
        except serial.SerialTimeoutException:
            print ("Timeout writing serial data. Bytes written %d!", bytes_written)
            return False
        
        # Check our write was successful
        if bytes_written == len(data):
            return True
        else:
            print ("Failed to write all serial data. Buffer %d, written %d!", len(data), bytes_written)
            return False
            
    #-------------------------------------------------
    # Read response data
    def __read_data(self):
       
        data = []      
        while True:
            try:
                data.append(self.__ser.read(1))
                if (data[-1] == b''):
                    break
            except serial.SerialTimeoutException:
                # This is not an error as we don't know how many bytes to expect
                # Therefore a timeout signals the end of the data
                break
        if len(data) > 0:
            return data[:len(data)-1]
        return data
    
    #-------------------------------------------------
    # Dispatch data
    def __dispatch_data(self, data):
       
        try:
            self.__writer_q.put(data, timeout=0.1)
        except queue.Full:
            print("Exception queue full writing response data!")
            return False
        return True
    
#=====================================================
# Main server class
#===================================================== 
class SerialServer: 
    #-------------------------------------------------
    # Initialisation
    def __init__(self) :
        """
        Constructor
        
        Arguments
            
        """
        # Create the inter-thread queues
        self.__to_serial = queue.Queue(100)
        self.__to_udp = queue.Queue(100)

    #-------------------------------------------------
    # Main
    def main(self) :
        """
        Constructor
        
        Arguments
            
        """
        
        # Start the threads
        self.__udp_thread = UDPThrd(self.__to_udp, self.__to_serial)
        self.__udp_thread.start()
        self.__serial_thread = SerialThrd(self.__to_serial, self.__to_udp)
        self.__serial_thread.start()
        
        print ("Serial Server running...")
        # Wait for exit
        while True:
            try:
                sleep(1)
            except KeyboardInterrupt:
                break
        
        # Close threads    
        self.__udp_thread.terminate()
        self.__udp_thread.join()
        self.__serial_thread.terminate()
        self.__serial_thread.join()
        
        print("Serial Server exiting...")        

#=====================================================
# Entry point
#=====================================================

#-------------------------------------------------
# Start processing and wait for user to exit the application
def main():
    try:
        app = SerialServer()
        sys.exit(app.main())
        
    except Exception as e:
        print ('Exception from main SerialServer code','Exception [%s][%s]' % (str(e), traceback.format_exc()))

#-------------------------------------------------
# Enter here when run as script        
if __name__ == '__main__':
    main()