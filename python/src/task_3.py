#!/usr/bin/python
# -*- coding: utf-8 -*-

import RPi.GPIO as GPIO
from ctypes import c_short
import smbus
import csv
import lib.lcddriver as lcddriver
import Adafruit_DHT
import time

sensor = Adafruit_DHT.DHT11

SENSOR_PIN = 26
RED_LIGHT = 17
BLUE_LIGHT = 27


DEVICE = 0x77 # Default device I2C address

delay = 5

#bus = smbus.SMBus(0)  # Rev 1 Pi uses 0
bus = smbus.SMBus(1)   # Rev 2 Pi uses 1


def convertToString(data):
    # Simple function to convert binary data into
    # a string
    return str((data[1] + (256 * data[0])) / 1.2)


def getShort(data, index):
    # return two bytes from data as a signed 16-bit value
    return c_short((data[index] << 8) + data[index + 1]).value


def getUshort(data, index):
    # return two bytes from data as an unsigned 16-bit value
    return (data[index] << 8) + data[index + 1]


def readBmp180Id(addr=DEVICE):
    # Register Address
    REG_ID     = 0xD0

    (chip_id, chip_version) = bus.read_i2c_block_data(addr, REG_ID, 2)
    return (chip_id, chip_version)

def readBmp180(addr=DEVICE):
    # Register Addresses
    REG_CALIB  = 0xAA
    REG_MEAS   = 0xF4
    REG_MSB    = 0xF6
    REG_LSB    = 0xF7
    # Control Register Address
    CRV_TEMP   = 0x2E
    CRV_PRES   = 0x34
    # Oversample setting
    OVERSAMPLE = 3    # 0 - 3

    # Read calibration data
    # Read calibration data from EEPROM
    cal = bus.read_i2c_block_data(addr, REG_CALIB, 22)

    # Convert byte data to word values
    AC1 = getShort(cal, 0)
    AC2 = getShort(cal, 2)
    AC3 = getShort(cal, 4)
    AC4 = getUshort(cal, 6)
    AC5 = getUshort(cal, 8)
    AC6 = getUshort(cal, 10)
    B1  = getShort(cal, 12)
    B2  = getShort(cal, 14)
    MB  = getShort(cal, 16)
    MC  = getShort(cal, 18)
    MD  = getShort(cal, 20)

    # Read temperature
    bus.write_byte_data(addr, REG_MEAS, CRV_TEMP)
    time.sleep(0.005)
    (msb, lsb) = bus.read_i2c_block_data(addr, REG_MSB, 2)
    UT = (msb << 8) + lsb

    # Read pressure
    bus.write_byte_data(addr, REG_MEAS, CRV_PRES + (OVERSAMPLE << 6))
    time.sleep(0.04)
    (msb, lsb, xsb) = bus.read_i2c_block_data(addr, REG_MSB, 3)
    UP = ((msb << 16) + (lsb << 8) + xsb) >> (8 - OVERSAMPLE)

    # Refine temperature
    X1 = ((UT - AC6) * AC5) >> 15
    X2 = (MC << 11) / (X1 + MD)
    B5 = X1 + X2
    temperature = (B5 + 8) >> 4

    # Refine pressure
    B6  = B5 - 4000
    B62 = B6 * B6 >> 12
    X1  = (B2 * B62) >> 11
    X2  = AC2 * B6 >> 11
    X3  = X1 + X2
    B3  = (((AC1 * 4 + X3) << OVERSAMPLE) + 2) >> 2

    X1 = AC3 * B6 >> 13
    X2 = (B1 * B62) >> 16
    X3 = ((X1 + X2) + 2) >> 2
    B4 = (AC4 * (X3 + 32768)) >> 15
    B7 = (UP - B3) * (50000 >> OVERSAMPLE)

    P = (B7 * 2) / B4

    X1 = (P >> 8) * (P >> 8)
    X1 = (X1 * 3038) >> 16
    X2 = (-7357 * P) >> 16
    pressure = P + ((X1 + X2 + 3791) >> 4)

    return (temperature/10.0,pressure/ 100.0)

def run():

    GPIO.setup(RED_LIGHT, GPIO.OUT)
    GPIO.setup(BLUE_LIGHT, GPIO.OUT)
    last_temp = 0

    print "Die Messung erfolgt alle %d Sekunden." % delay

    (chip_id, chip_version) = readBmp180Id()

    print "Chip ID     :", chip_id
    print "Chip Version:", chip_version

    print '+-------------------------------------------------+'

    with open('readings.csv', 'w') as readings_file:
        readings_writer = csv.writer(readings_file, delimiter=";")
        readings_writer.writerow(["Messzeit", "Temperatur", "Luftdruck"])

        while True:

            (temperature, pressure) = readBmp180()
            messzeit = time.strftime("%d.%m.%Y %H:%M:%S")

            print "Messzeit : ", messzeit
            print "Temperatur : ", temperature, "°C"
            print "Luftdruck  : ", pressure, "mbar"
            print "------------------------------"

            readings_writer = csv.writer(readings_file, delimiter=";")
            readings_writer.writerow([messzeit, temperature, pressure])

            GPIO.output(RED_LIGHT, False)
            GPIO.output(BLUE_LIGHT, False)

            luftfeuchte, temperatur = Adafruit_DHT.read_retry(sensor, SENSOR_PIN)

            if temperatur > last_temp:
                GPIO.output(RED_LIGHT, True)
            elif temperatur < last_temp:
                GPIO.output(BLUE_LIGHT, True)
            else:
                GPIO.output(RED_LIGHT, True)
                GPIO.output(BLUE_LIGHT, True)

            last_temp = temperatur

            print 'Temperatur: {0:0.1f}°C '.format(temperatur)
            print 'Luftfeuchtigkeit: {1:0.1f}%'.format(luftfeuchte)
            print '+-------------------------------------------------+'

            time.sleep(delay)
