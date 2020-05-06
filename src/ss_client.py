#!/usr/bin/env python
#
# ss_client.py
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
The Serial Server client runs on the host machine.
"""

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
        
        # Temp connect data
        data = [{"port": "COM4", "baud": 9600, "data_bits": 8, "parity": "N", "stop_bits": 2}]
        # Open remote port
        try:
            # Send connect data to the remote device
            self.__sock.sendto(pickle.dumps({"rqst": "connect", "data": data}), self.__addr)
        except socket.timeout:
            print ("Error sending connect data!")
            return

        # Processing loop
        while not self.__terminate:
            self.__process()
            
        try:
            self.__sock.sendto(pickle.dumps({"rqst": "disconnect", "data": []}), self.__addr)
        except socket.timeout:
            print ("Error disconnecting!")
            
        print ("Serial Client - UDP thread exiting...")

    #-------------------------------------------------
    # Process exchanges
    def __process(self):
        # We wait data from the serial class instance
        # Format the data and send to the remote device over UDP
        # Wait for response data and write to the serial device
        
        try:
            data = self.__reader_q.get(timeout=0.1)
        except queue.Empty:
            return
        
        # Dispatch data
        try:
            self.__sock.sendto(pickle.dumps({"rqst": "data", "data": data}), self.__addr)
        except socket.timeout:
            print ("Error sending UDP data!")
            return
        
        l = [0x01,0x42,0x34,0x56,0x01]
        #res = ''.join(format(x, '02x') for x in list)
        #print(l)
        self.__writer_q.put([l])
        return
        
        # Wait for any response
        try:
            data, self.__addr = self.__sock.recvfrom(100)
        except socket.timeout:
            # No response is not an error
            return
        except socket.error as err:
            print("Socket error: {0}".format(err))
            # Probably not connected
            return
        
        # Dispatch to serial
        d = pickle.loads(data)
        if d[0]["resp"]:
            # Good response
            self.__writer_q.put(d[0]["data"])
            
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
        self.__data = []
        self.__resp_data = None
    
    #-------------------------------------------------
    # Terminate thread
    def terminate(self):
        """ Terminate thread """
        
        self.__terminate = True
    
    #-------------------------------------------------
    # Thread entry point    
    def run(self):
        """
        Open port
        Wait for data from serial port.
        Send data to writer q
        Wait for response data from reader q
        Send response data to serial port
        
        Format for requests is:
            {"rqst":rqst_type, "data":[parameters or data]}
            reqst_type : "connect", "disconnect", "serial_data"
        
        """
        
        # Open local serial port
        # Temp connect data
        data = [{"port": "COM3", "baud": 9600, "data_bits": 8, "parity": "N", "stop_bits": 2}]
        # Open local port
        self.__do_connect(data);
            
        # Main thread loop            
        while not self.__terminate:
            # Read data from serial port
            data = self.__read_data()
            if len(data) > 0:
                # Have some data
                # Dispatch to UDP
                self.__dispatch_data(data)
                # Wait for response
                if self.__response_data():
                    # We have response data
                    #byte_data = b''.join(self.__resp_data[0])
                    self.__write_data(self.__resp_data[0])
                    
        # Terminating
        self.__do_disconnect()
        print("Serial Client - Serial thread exiting...")
                
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
                                        timeout=0.05,
                                        xonxoff=0,
                                        rtscts=0,
                                        write_timeout=0.05)
        except serial.SerialException:
            print("Failed to open device! ", p["port"])
            return False
        return True    
    
    #-------------------------------------------------
    # Disconnect from serial port    
    def __do_disconnect(self):
        
        self.__ser.close()
        return True
    
    #-------------------------------------------------
    # Write data to serial port 
    def __write_data_sav(self, data):
       
        # Write data is a bytearray
        print("Client write: ", data)
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
    
    def __write_data(self, data):
       
        # Write data is a bytearray
        print("Client write: ", data)
        try:
            for d in data:
                self.__ser.write(d)
        except serial.SerialTimeoutException:
            print ("Timeout writing serial data. Bytes written %d!", bytes_written)
            return False
        
        return True
        
    #-------------------------------------------------
    # Read response data
    def __read_data_sav(self):

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
            if len(data) > 1:
                print("Client read: ", data[:len(data)-1])
            return data[:len(data)-1]
        return data
    
    #-------------------------------------------------
    # Read response data
    def __read_data(self):
      
        data = []
        while True:
            if self.__terminate:
                return b''    
            try:
                # Data length should never exceed 50 bytes
                data.append(self.__ser.read(1))
                # Returns on 50 chars or on timeout
                if data[-1] == b'':
                    if len(data) > 1:
                        print("Client read: ", data[:len(data)-1])
                        return data[:len(data)-1]
                    else:
                        data.clear()
                        continue
                
            except serial.SerialTimeoutException:
                # This is not an error as we don't know how many bytes to expect
                # Therefore a timeout signals the end of the data
                print("Client timeout: ", data)
                break
        
        return data
    
    #-------------------------------------------------
    # Dispatch data
    def __dispatch_data(self, data):
       
        try:
            self.__writer_q.put(data, timeout=0.1)
        except queue.Full:
            print("Client - queue full writing data!")
            return False
        return True
    
    #-------------------------------------------------
    # Get response data
    def __response_data(self):
    
        try:
            self.__resp_data = self.__reader_q.get(timeout=0.1)
        except queue.Empty:
            return False
        return True
    
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
        
        print ("Serial Client running...")
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
        
        print("Serial Client exiting...")
        return 0

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