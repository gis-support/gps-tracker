# -*- coding: utf-8 -*-
"""
/***************************************************************************
 gpsConnection
                                 A QGIS plugin
                              -------------------
        begin                : 2013-08-20
        copyright            : (C) 2013 by Piotr Pociask
        email                : info@gis-support.pl
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
from __future__ import absolute_import
from builtins import str
from builtins import range
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import QMessageBox
from qgis.core import *
from .gpsUtils import playsound
from .gpsUtils import ErrorCatcher
from future.utils import with_metaclass

class GPSConnection(with_metaclass(ErrorCatcher, QObject)):
    DISCONNECTED = 0
    CONNECTED = 1
    NO_FIX = 2
    CONNECTING = 3
    measuring = False
    measuredPoints = []
    
    fixMode = {'A':u'Automatyczny', 'M':u'Manualny'}
    fixType = {1:u'Niedostępny', 2:u'2D', 3:u'3D'}
    quality = {0:u'Brak pozycji', 1:u'Nieróżnicowy', 2:u'Różnicowy',
               3:u'Precise positioning service fix (PPS)', 4:u'Real Time Kinematic (RTK)',
               5:u'Float Real Time Kinematic (RTK)', 6:u'Przybliżony (nawigacja zliczeniowa)',
               7:u'Tryb manualny', 8:u'Tryb symulacji'}
    status = {'A':u'Prawidłowy', 'V':u'Nieprawidłowy'}
    
    gpsMessage = pyqtSignal(str)
    gpsStatus = pyqtSignal(int)
    gpsInfromationReceived = pyqtSignal(dict)
    gpsConnectionStart = pyqtSignal()
    gpsConnectionStop = pyqtSignal()
    gpsConnectionStatusChanged = pyqtSignal(int)
    gpsFixTypeChanged = pyqtSignal(int, int)
    gpsMeasureStopped = pyqtSignal(dict, bool)
    gpsPositionChanged = pyqtSignal(float, float, float, float)
    gpsMeasureMethodChanged = pyqtSignal(int)
    
    def __init__(self, infoList, model, displayCrs, port=None, parent=None):
        QObject.__init__(self, parent)
        self.infoList = infoList
        self._model = model
        self.setStatus(self.DISCONNECTED)
        self.setPort(port)
    
    def setPort(self, port):
        if self._status != self.DISCONNECTED:
            return
        self._port = port
       
    def getPort(self):
        return self._port
    
    def setStatus(self, status):
        self._status = status
        self.gpsConnectionStatusChanged.emit(status)
    
    def getStatus(self):
        return self._status
    
    def connectGPS(self):
        if not self._port:
            self.gpsMessage.emit(u'Brak portu!')
            return None
        self.setStatus(self.CONNECTING)
        self.gpsMessage.emit(u'Łączenie z odbiornikiem GPS...')
        self.detector = QgsGpsDetector(self._port)
        self.detector.detected[QgsGpsConnection].connect(self.connectionSucceed)
        self.detector.detectionFailed.connect(self.connectionFailed)
        self.detector.advance()
    
    def disconnectGPS(self):
        self.gpsConnectionStop.emit()
        self.connection.stateChanged[QgsGpsInformation].disconnect()
        self.connection.close()
        QgsApplication.gpsConnectionRegistry().unregisterConnection(self.connection)
        del self.connection
        self.setStatus(self.DISCONNECTED)
        #rozłączenie sygnałów powoduje wystapienie błędu, więc wykonywane jest twarde usunięcie obiektu z pamięci
        # self.detector.detected[QgsGPSConnection].disconnect()
        # self.detector.detectionFailed.disconnect()
        del self.detector
        for i in range(len(self.infoList)-1):
            self.infoList[i+1] = ''
        self.infoList[0] = [0.,0.]
        self._model.dataChanged.emit(self._model.index(0, 0), self._model.index(12, 0))
        if self.measuring:
            self.resetMeasuring()
        self.gpsMessage.emit(u'Rozłączono z odbiornikiem GPS')
        playsound(300, 500)
    
    def connectionSucceed(self, connection):
        self.gpsMessage.emit(u'Połączono z odbiornikiem GPS')
        playsound(1000, 500)
        self.connection = connection
        self.connection.stateChanged[QgsGpsInformation].connect(self.informationReceived)
        QgsApplication.gpsConnectionRegistry().registerConnection(self.connection)
        self.gpsConnectionStart.emit()
        self.setStatus(self.CONNECTED)
    
    def connectionFailed(self):
        self.setStatus(self.DISCONNECTED)
        self.gpsMessage.emit(u'Błąd połączenia z odbiornikiem GPS')
        playsound(300, 500)
        QMessageBox.critical(None, 'GPS Tracker Plugin', u'Błąd połączenia z odbiornikiem GPS') 
        connections = QgsApplication.gpsConnectionRegistry().connectionList()
        if len(connections) > 0:
            msg = QMessageBox.question(None, 'GPS Tracker Plugin', 
                                       u'Wykryto zarejestrowane połączenia. Czy chcesz je usunąć w celu zwolnienia portu?',
                                       QMessageBox.Yes | QMessageBox.No)
            if msg == QMessageBox.Yes:
                for connection in connections:
                    connection.close()
                    QgsApplication.gpsConnectionRegistry().unregisterConnection(connection)
    
    def informationReceived(self, gpsData):
        try:
            self.infoList[7] = self.fixMode[str(gpsData.fixMode)]
        except KeyError:
            self.infoList[7] = 'N/A'

        try:
            if (self.infoList[8] != self.fixType[gpsData.fixType]) or (self.infoList[9] != self.quality[gpsData.quality]):
                self.gpsFixTypeChanged.emit(gpsData.fixType, gpsData.quality)
            self.infoList[8] = self.fixType[gpsData.fixType]
        except KeyError:
            self.infoList[8] = str(gpsData.fixType)
        
        try:
            self.infoList[9] = self.quality[gpsData.quality]
        except KeyError:
            self.infoList[9] = str(gpsData.quality)
        
        try:
            self.infoList[10] = self.status[str(gpsData.status)]
        except KeyError:
            self.infoList[10] = 'N/A'
        self.infoList[11] = str(gpsData.direction)
        
        if gpsData.fixType == 1 or gpsData.status == 0 or gpsData.quality == 0:
            if self.getStatus() != self.NO_FIX:
                playsound(300, 500)
            self.setStatus(self.NO_FIX)
            for i in [1, 2, 3, 4, 5, 6, 10, 11]:
                self.infoList[i] = ''
            self.infoList[0] = [0., 0.]
            self._model.dataChanged.emit(self._model.index(0, 0), self._model.index(12, 0))
            if self.measuring:
                self.resetMeasuring()
                QMessageBox.critical(None, u'GPS Tracker Plugin', u'Utracono sygnał GPS. Pomiar został przerwany.')
            return
        
        if self.getStatus() != self.CONNECTED:
            playsound(1000,500)
            self.setStatus(self.CONNECTED)
        
        self.infoList[0] = [gpsData.longitude, gpsData.latitude, gpsData.direction, gpsData.elevation]
        self.gpsPositionChanged.emit(gpsData.longitude, gpsData.latitude, gpsData.direction, gpsData.elevation)
        
        if self.measuring:
            self.measuredPoints.append([gpsData.longitude, gpsData.latitude, gpsData.direction, gpsData.elevation])
            self.gpsMessage.emit(u'Numer pomiaru: %d' % len(self.measuredPoints))
            if not self.measureTime and self.measureValue == len(self.measuredPoints):
                self.stopMeasuring()
        
        if hasattr(gpsData, 'elevation'):
            self.infoList[1] = str(gpsData.elevation)
        else: 
            self.infoList[1] = 'N/A'
        if hasattr(gpsData, 'pdop'):
            self.infoList[2] = str(gpsData.pdop)
        else:
            self.infoList[2] = 'N/A'
        if hasattr(gpsData, 'hdop'):
            self.infoList[3] = str(gpsData.hdop)
        else:
            self.infoList[3] = 'N/A'
        if hasattr(gpsData, 'vdop'):
            self.infoList[4] = str(gpsData.vdop)
        else:
            self.infoList[4] = 'N/A'
        if hasattr(gpsData, 'hacc'):
            self.infoList[5] = str(gpsData.hacc)
        else:
            self.infoList[5] = 'N/A'
        if hasattr(gpsData, 'vacc'):
            self.infoList[6] = str(gpsData.vacc)
        else:
            self.infoList[6] = 'N/A'
        if hasattr(gpsData, 'satellitesUsed'):
            self.infoList[11] = str(gpsData.satellitesUsed)
        else:
            self.infoList[11] = 'N/A'
        self._model.dataChanged.emit(self._model.index(0, 0), self._model.index(12, 0))
    
    def startMeasuring(self, value, updatePoint, measureTime=False):
        self.measuring = True
        self.measureValue = value

        self.measureTime = measureTime
        self.updatePoint = updatePoint
        if measureTime:
            QTimer.singleShot(value*1000, self.stopMeasuring)
    
    def stopMeasuring(self):
        count = len(self.measuredPoints)
        if count:
            x = sum([item[0] for item in self.measuredPoints])/count
            y = sum([item[1] for item in self.measuredPoints])/count
            self.gpsMeasureStopped.emit({'x':x, 'y':y, 'lp':count}, self.updatePoint)
        self.gpsMessage.emit(u'Zakończono pomiar')
        self.resetMeasuring()
    
    def resetMeasuring(self):
        self.measuredPoints = []
        self.measuring = False
        del self.measureTime
        del self.measureValue