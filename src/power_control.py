#!/usr/bin/env python
#
# power_control.py
#
# Python power plug-in for serial server
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

#=====================================================
# Power Control for FT817

#-------------------------------------------------
# Power device on
def power_on(serial):
    
    empty_seq = bytes([0x00,0x00,0x00,0x00,0x00])
    on_seq = bytes([0x00,0x00,0x00,0x00,0x0F])
    
    try:
        self.__ser_port.write(empty_seq)
        self.__ser_port.write(on_seq)
    except serial.SerialTimeoutException:
        # I guess we could get a timeout as well
        printf("Timeout trying to power-up rig!")
        
#-------------------------------------------------
# Power device on
def power_off(serial):
    
    empty_seq = bytes([0x00,0x00,0x00,0x00,0x00])
    off_seq = bytes([0x00,0x00,0x00,0x00,0x8F])
    
    try:
        self.__ser_port.write(empty_seq)
        self.__ser_port.write(off_seq)
    except serial.SerialTimeoutException:
        # I guess we could get a timeout as well
        printf("Timeout trying to power-down rig!")