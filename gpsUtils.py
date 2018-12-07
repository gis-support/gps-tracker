# -*- coding: utf-8 -*-
"""
/***************************************************************************
 gpsUtils
                                 A QGIS plugin
                              -------------------
        begin                : 2013-04-06
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
from PyQt5.QtGui import *
from PyQt5.QtCore import *
from qgis.core import *
from qgis.gui import *
from PyQt5.QtWidgets import QPushButton, QMessageBox
from math import sqrt
from time import strftime
from os import remove, stat, path
from sys import platform
from subprocess import Popen
import csv
from future.utils import with_metaclass
from . import GPSTrackerDialog

try:
    from winsound import Beep
except ImportError:
    def playsound(frequency,duration):
        pass
else: 
    def playsound(frequency,duration):
        Beep(frequency,duration)
import functools, traceback, sys
"""=============Obsługa wyjątków============"""
def catch_exception(f):
    @functools.wraps(f)
    def func(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except:
            exc_type, value, tb = sys.exc_info()
            GPSTrackerDialog.GPSLogger.writeException('%s' % (''.join([x.replace('\n', '\r\n') for x in traceback.format_exception(exc_type, value, tb)])))
    return func

class ErrorCatcher(type(QObject)):
    def __new__(cls, name, bases, dct):
        for m in dct:
            if hasattr(dct[m], '__call__'):
                if type(dct[m]) is pyqtSignal:
                    continue
                dct[m] = catch_exception(dct[m])
        return type(QObject).__new__(cls, name, bases, dct)
"""=============Elementy okna mapy============"""
class GPSMarkerItem(with_metaclass(ErrorCatcher, QgsMapCanvasItem)):
    def __init__(self, canvas, parent=None):
        QgsMapCanvasItem.__init__(self, canvas)
        self.parent = parent
        self.setLabel('')
        self.map_pos = QgsPoint(0.0, 0.0)

    def paint(self, painter, xxx, xxx2):
        self.setPos(self.toCanvasCoordinates(QgsPointXY(self.map_pos)))
        halfSize = self.parent.markerSize / 2.0
        self.parent.markerImg.paint(painter, 0 - halfSize, 0 - halfSize, self.parent.markerSize,
                                    self.parent.markerSize, alignment=Qt.AlignCenter)
        painter.setPen(self.parent.markerFontColor)
        painter.setFont(self.parent.markerFont)
        painter.drawText(halfSize+1, 0, self.label)

    def boundingRect(self):
        halfSize = self.parent.markerSize / 2.0
        if halfSize<self.parent.markerFontMetric.ascent():
            halfSize = self.parent.markerFontMetric.ascent()
        return QRectF(-halfSize, -halfSize, (2.0 * halfSize)+self.labelWidth+1, 2.0 * halfSize)

    def setCenter(self, map_pos):
        self.map_pos = QgsPointXY(self.map_pos)
        self.map_pos = map_pos
        self.setPos(self.toCanvasCoordinates(self.map_pos))
    
    def setLabel(self, label):
        self.label = label
        self.labelWidth = self.parent.markerFontMetric.width(self.label)

    def updatePosition(self):
        self.setCenter(QgsPointXY(self.map_pos))

class GPSMarker(with_metaclass(ErrorCatcher, QObject)):
    def __init__(self, canvas, iconPath, parent=None):
        QObject.__init__(self, parent)
        self.marker = None
        self.canvas = canvas
        self.model = parent.tvPointList.model()
        self.parent = parent
        self.setMarkerIcon(iconPath)
        self.setMarkerSize(32)
        self.setMarkerFont()
    
    def clean(self):
        self.setMarkerVisible(False)
    
    def setMarkerIcon(self, iconPath):
        self.markerImg = QIcon(iconPath)
    
    def setMarkerSize(self, size=24):
        self.markerSize = size
    
    def setMarkerFont(self, family='MS Shell Dlg 2', color=QColor('black'), size=8):
        self.markerFont = QFont(family, size)
        self.markerFont.setBold(True)
        self.markerFontColor = color
        self.markerFontMetric = QFontMetricsF(self.markerFont)
        if self.marker:
            self.marker.labelWidth = self.markerFontMetric.width(self.marker.label)
        
    def setMarkerPos(self, x, y):
        self.markerPos = self.transform.transform(x, y)
        if self.marker:
            if self.parent.gbPointDistance.isChecked():
                coords = self.model.getLastPoint()
                if coords:
                    lastPoint = self.transform.transform(coords[0], coords[1])
                    distance = sqrt(lastPoint.sqrDist(self.markerPos))
                    self.marker.setLabel('%.2f' % distance)
                else:
                    self.marker.setLabel('')
            else:
                self.marker.setLabel('')
            self.marker.setCenter(self.markerPos)
    
    def setMarkerVisible(self, visible):
        if visible:
            self.marker = GPSMarkerItem(self.canvas, self)
        else:
            self.canvas.scene().removeItem(self.marker)
            self.marker = None

class GPSPath(with_metaclass(ErrorCatcher, QObject)):
    def __init__(self, canvas, parent):
        QObject.__init__(self, parent)
        self.canvas = canvas
        self.parent = parent
        self.path = QgsRubberBand(canvas, QgsWkbTypes.PointGeometry)
        self.path.setColor(QColor('black'))
        self.vertexes = QgsRubberBand(canvas, QgsWkbTypes.PointGeometry)
        self.vertexes.setIcon(QgsRubberBand.ICON_CROSS)
        self.vertexes.setColor(QColor('red'))
        self.vertexes.setIconSize(10)
        self.parent.tvPointList.model().dataChanged.connect(self.dataChanged)
        
    def clean(self):
        self.resetPoints()
        del self.path
        del self.vertexes
    
    def dataChanged(self, *args):
        self.resetPoints()
        points = self.parent.tvPointList.model().getPointList()
        for coords in points:
            point = self.transform.transform(coords['x'], coords['y'])
            self.path.addPoint(point)
            self.vertexes.addPoint(point)
    
    def resetPoints(self):
        try:
            self.path.reset()
            self.vertexes.reset(QgsWkbTypes.PointGeometry)
        except:
            pass
    
    def setVisible(self, visible):
        self.path.setVisible(visible)
        self.vertexes.setVisible(visible)

class GPSSelectedMarker(with_metaclass(ErrorCatcher, QObject)):
    def __init__(self, canvas, parent=None):
        QObject.__init__(self, parent)
        self.marker = None
        self.point = None
        self.canvas = canvas
    
    def clean(self):
        self.setMarker(-1, QgsPoint())

    def createMarker(self):
        self.marker = QgsVertexMarker(self.canvas)
        self.marker.setPenWidth(2)
        self.marker.setColor(QColor('blue'))
        self.marker.setIconType(QgsVertexMarker.ICON_BOX)
    
    def destroyMarker(self):
        self.canvas.scene().removeItem(self.marker)
        self.marker = None
    
    def setMarker(self, index, point):
        self.point = point
        if index == -1:
            self.destroyMarker()
            return
        elif not self.marker:
            self.createMarker()
        self.marker.setCenter(self.transform.transform(QgsPointXY(point)))

"""=============Zapisywanie danych============"""
class GPSDataWriter(with_metaclass(ErrorCatcher, QObject)):
    wgs84 = QgsCoordinateReferenceSystem(4326, QgsCoordinateReferenceSystem.EpsgCrsId)
    geomIcon = {QgsWkbTypes.PointGeometry:'pointLayer.svg', QgsWkbTypes.LineGeometry:'lineLayer.svg', QgsWkbTypes.PolygonGeometry:'polygonLayer.svg'}
    iconsPath = str(QFileInfo(__file__).absolutePath()) + '/icons/'
    nrFieldIndex = -1
    rzFieldIndex = -1
    
    def __init__(self, parent, cmbLayers):
        QObject.__init__(self, parent)
        self.parent = parent
        self.cmbLayers = cmbLayers
        self.parent.connection.gpsMeasureStopped[dict, bool].connect(self.pointReceived)
        QgsProject.instance().layersAdded.connect(self.addLayers)
        QgsProject.instance().layersWillBeRemoved.connect(self.removeLayers)
        cmbLayers.currentIndexChanged[int].connect(self.changeLayer)
        #jeszcze zmiana nazwy warstwy
        self.setLayer(None)
        self.getAllLayers()
    
    def clean(self):
        QgsProject.instance().layersAdded.disconnect(self.addLayers)
        QgsProject.instance().layersWillBeRemoved.disconnect(self.removeLayers)
    
    def getAllLayers(self):
        self.addLayers(iter(list(QgsProject.instance().mapLayers().values())))
    
    def setLayer(self, layer):
        self.activeLayer = layer
        if layer:
            self.transform = QgsCoordinateTransform(self.wgs84, layer.crs(), QgsProject.instance())
    
    def changeLayer(self, index):
        layerId = self.sender().itemData(index)
        layer = QgsProject.instance().mapLayer(layerId)
        if not layer:
            self.setLayer(None)
            return
        if layer.name().lower() == 'punkty_pomocnicze' and layer.geometryType() == QgsWkbTypes.PointGeometry:
            self.nrFieldIndex = layer.fields().indexFromName('NR')
            self.rzFieldIndex = layer.fields().indexFromName('Rzedna')
        else:
            self.nrFieldIndex = -1
        self.setLayer(layer)
    
    def addLayers(self, layers):
        for layer in layers:
            if layer.type() == QgsMapLayer.VectorLayer:
                icon = QIcon(self.iconsPath + self.geomIcon[layer.geometryType()])
                self.cmbLayers.addItem(icon, layer.name(), layer.id())
        self.cmbLayers.model().sort(0)
    
    def removeLayers(self, layerIds):
        #ta funkcja jest wywoływana podwójnie
        model = self.cmbLayers.model()
        start = model.index(0, 0)
        for layerId in layerIds:
            try:
                row = model.match(start, Qt.UserRole, layerId)[0].row()
                model.removeRow(row)
            except:
                continue
    
    def pointReceived(self, coords, updatePoint=False):
        if updatePoint or not self.activeLayer:
            return
        if self.activeLayer.isEditable() and self.activeLayer.geometryType() == QgsWkbTypes.PointGeometry:
            self.fields = self.activeLayer.fields()
            self.savePoint(coords, self.parent.tvPointList.model().rowCount(), self.getShowFeatureForm())
            self.parent.iface.mapCanvas().refresh()
    
    def savePoint(self, coords, index, showFeatureForm):
        point = QgsFeature()
        point.setGeometry(QgsGeometry.fromPointXY(self.transform.transform(coords['x'], coords['y'])))
        point.setFields(self.fields, True)
        if self.nrFieldIndex != -1:
            point.setAttribute(self.nrFieldIndex, index+1)
            if self.parent.cbOffsetMeasure.isChecked() or self.parent.cmbMeasureMethod.currentIndex() == 0:
                point.setAttribute(self.rzFieldIndex, None)
            else:
                point.setAttribute(self.rzFieldIndex, index)
            showFeatureForm = False
        self.activeLayer.addFeature(point)
        if showFeatureForm and self.isFirstPoint:
            self.parent.iface.openFeatureForm(self.activeLayer, point)
    
    def savePoints(self, allPoints):
        self.activeLayer.startEditing()
        if self.nrFieldIndex != -1:
            rzedna = QgsField("Rzedna", QVariant.Int)
            self.activeLayer.addAttribute(rzedna)
        self.isFirstPoint = True
        self.fields = self.activeLayer.fields()
        points = self.parent.tvPointList.model().getPointList(allPoints)
        showFeatureForm = self.getShowFeatureForm()
        for i, point in enumerate(points):
            self.savePoint(point, i, showFeatureForm)
            self.isFirstPoint = False
        self.activeLayer.commitChanges()
        self.parent.iface.mapCanvas().refresh()
    
    @pyqtSlot()
    def saveFeature(self):
        sender = self.sender()
        button = sender.parent().btnAddFeatures
        allPoints = sender.allPoints
        button.allPoints = allPoints
        button.setDefaultAction(sender)
        sender.parent().saveSettings('saveType', allPoints)
        if allPoints:
            button.setText(u'Zap. wsz. pkt')
        else:
            button.setText(u'Zap. zaz. pkt')
        if self.parent.tvPointList.model().rowCount() == 0:
            QMessageBox.critical(None, 'GPS Tracker Plugin', u'Brak zarejestrowanych punktów!')
            return
        try:
            geomType = self.activeLayer.geometryType()
        except:
             self.parent.iface.messageBar().pushMessage('BŁĄD',
                 self.tr(u'Brak warstwy wektorowej do zapisu obiektów'),
                 Qgis.Critical,
                 duration = 3
             )
             return
        if geomType == QgsWkbTypes.PointGeometry:
            self.savePoints(allPoints)
        else:
            self.saveObject(allPoints, geomType)
    
    def saveObject(self, checkedOnly, geomType):
        points = self.parent.tvPointList.model().getPointList(checkedOnly)
        if (geomType == QgsWkbTypes.LineGeometry and len(points) < 2) or (geomType == QgsWkbTypes.PolygonGeometry and len(points) < 3):
            QMessageBox.critical(None, 'GPS Tracker Plugin', u'Liczba zarejestrowanych lub wybranych punktów jest zbyt mała!')
            return
        showFeatureForm = self.getShowFeatureForm()
        self.activeLayer.startEditing()
        feat = QgsFeature()
        if geomType == QgsWkbTypes.LineGeometry:
            feat.setGeometry(QgsGeometry.fromPolylineXY([self.transform.transform(point['x'], point['y']) for point in points]))
        else:
            feat.setGeometry(QgsGeometry.fromPolygonXY([[self.transform.transform(point['x'], point['y']) for point in points]]))
        feat.setFields(self.activeLayer.fields(), True)
        self.activeLayer.addFeature(feat)
        if showFeatureForm:
            self.parent.iface.openFeatureForm(self.activeLayer, feat)
        self.activeLayer.commitChanges()
        self.parent.iface.mapCanvas().refresh()
    
    @staticmethod
    def getShowFeatureForm():
        return not QSettings().value('Qgis/digitizing/disable_enter_attribute_values_dialog', False, type=bool)

class GPSLogFile(with_metaclass(ErrorCatcher, QObject)):
    ''' Pojedynczy plik logowania '''
    
    def __init__(self, filePath, parent=None):
        QObject.__init__(self, parent)
        self.filePath = filePath
        self.openFile()
    
    def clean(self):
        self.closeFile()
    
    def openFile(self):
        self.logFile = open(self.filePath, 'a')
        
    def writeData(self, data):
        self.logFile.write('%s' % data)
        self.logFile.write('\r\n')
    
    def closeFile(self):
        self.logFile.close()

class GPSLogger(with_metaclass(ErrorCatcher, QObject)):
    logDirectory = ''
    ''' Klasa zbiorcza do logowania '''
    def __init__(self, parent=None):
        QObject.__init__(self, parent)
        self.parent = parent
        self.changeDirectory(parent.eLogDir.text())
        self.writeNmea = False
        self.nmeaLog = None
        self.parent.connection.gpsMeasureStopped[dict, bool].connect(self.writeMeasuredPoint)
    
    def clean(self):
        self.parent.connection.gpsMeasureStopped[dict, bool].disconnect(self.writeMeasuredPoint)
        if self.nmeaLog:
            self.nmeaLog.closeFile()
        if path.isfile(path.join(self.getLogDirectory(), 'pointList.csv')):
            remove(path.join(self.getLogDirectory(), 'pointList.csv'))
    
    def openFile(self):
        self.setSessionDateTime()
        self.nmeaFile = '%s\%s.nmea' % (self.getLogDirectory(), self.sessionDateTime)
        self.nmeaLog = GPSLogFile(self.nmeaFile)
        self.parent.connection.connection.nmeaSentenceReceived[str].connect(self.nmeaReceived)
    
    def closeFile(self):
        self.parent.connection.connection.nmeaSentenceReceived[str].disconnect(self.nmeaReceived)
        self.nmeaLog.closeFile()
        if not stat(self.nmeaFile).st_size:
            remove(self.nmeaFile)
        self.nmeaLog = None
    
    def setSessionDateTime(self):
        #wywoływane w momencie połączenia
        self.sessionDateTime = self.getDateTimeFormat()
    
    def nmeaReceived(self, nmea):
        if self.writeNmea:
            nmea = nmea.strip()
            self.nmeaLog.writeData(nmea)
    
    def writeMeasuredPoint(self, calcPoint, updatePoint):
        #zapisywanie danych z pomiarów
        measureLog = GPSLogFile(path.join(self.getLogDirectory(), 'pomiar_%s.log' % self.sessionDateTime))
        try:
            measureLog.writeData('Pomiar z %s:' % (strftime('%H:%M:%S %d.%m.%Y')))
            for coords in self.sender().measuredPoints:
                point = self.transform.transform(coords[0], coords[1])
                measureLog.writeData('%.10f %.10f' % (point.x(), point.y()))
            point = self.transform.transform(calcPoint['x'], calcPoint['y'])
            measureLog.writeData('\r\nUśredniony wynik z %d pomiarów:\r\n%.10f %.10f\r\n' % (calcPoint['lp'], point.x(), point.y()))
            measureLog.writeData('===================================\r\n')
        finally:
            measureLog.closeFile()
    
    def writePointList(self):
        pointList = self.parent.tvPointList.model().getPointList(True)
        with open(path.join(self.getLogDirectory(), 'pointList.csv'), 'w') as csvfile:
            writer = csv.writer(csvfile, delimiter=',')
            for row in pointList:
                writer.writerow([row['id'], row['x'], row['y'], row['text'], row['lp'], row['checked']])
                
    @classmethod
    def changeDirectory(cls, directory):
        cls.logDirectory = str(directory)
    
    @classmethod
    def getLogDirectory(cls):
        if not cls.logDirectory:
            cls.logDirectory = QSettings().value('gpsTracker/logDir', path.join(path.dirname(__file__),'log'))
        return cls.logDirectory
    
    @classmethod
    def writeException(cls, text):
        errorFile = 'error_%s.log' % cls.getDateTimeFormat()
        errorLog = GPSLogFile(path.join(cls.getLogDirectory(), errorFile))
        try:
            errorLog.writeData(text)
        finally:
            errorLog.closeFile()
            cls.filePath = errorLog.filePath
            widget = cls.iface.messageBar().createMessage(u"Błąd", u"Wystąpił błąd podczas wykonywania operacji!\n\
Dane zostały zapisane w pliku '%s' w katalogu logowania." % cls.filePath)
            button = QPushButton(widget)
            button.setText(u"Otwórz folder")
            button.clicked.connect(cls.openErrorFile)
            widget.layout().addWidget(button)
            cls.iface.messageBar().pushWidget(widget, Qgis.Critical, duration=5)
    
    @classmethod
    def openErrorFile(cls):
        if platform == 'win32':
            Popen('explorer /select,"%s"' % cls.filePath)
        else:
            opener ="open" if platform == "darwin" else "xdg-open"
            Popen([opener, QFileInfo(cls.filePath).absolutePath()])
    
    @staticmethod
    def getDateTimeFormat():
        return strftime('%Y%m%d_%H%M%S')
    
    @staticmethod
    def verifyDirectory(dir):
        if not dir or not QDir(dir).exists():
            dir = '%s/log' % QFileInfo(__file__).absolutePath()
        return dir

class GPSMeasureSave(with_metaclass(ErrorCatcher, QObject)):
    """Autmatyczne zapisywanie danych pomiarowych"""
    
    def __init__(self, logger, interval=1, startTimer=False, parent=None):
        QObject.__init__(self, parent)
        self.timer = QTimer()
        self.setInterval(interval)
        self.timer.timeout.connect(self.saveMeasure)
        if startTimer:
            self.timer.start()
        self.logger = logger
    
    def setInterval(self, interval):
        self.timer.setInterval(interval*1000*60)
    
    def saveMeasure(self):
        self.logger.writePointList()
    
    def loadMeasure(self):
        fileName = path.join(self.logger.getLogDirectory(), 'pointList.csv')
        if not path.isfile(fileName) or not path.getsize(fileName):
            return []
        msg = QMessageBox.question(None, u'GPS Tracker Plugin', 
                                   u'QGIS nie został prawidłowo zamknięty. Czy chcesz odzyskać dane z ostatniej sesji?',
                                   QMessageBox.Yes | QMessageBox.No)
        if msg == QMessageBox.No:
            return []
        corruptedData = False
        data = []
        with open(fileName, 'rb') as csvfile:
            reader = csv.reader(csvfile, delimiter=',')
            for row in reader:
                try:
                    data.append({'id':int(row[0]), 'x':float(row[1]), 'y':float(row[2]), 'text':row[3], 'lp':int(row[4]), 'checked':int(row[5])})
                except:
                    corruptedData = True
                    continue
        if corruptedData:
            if data:
                QMessageBox.warning(None, 'GPS Tracker', u'Podczas wczytywania danych część informacji z ostatniej sesji nie została odzyskana.')
            else:
                QMessageBox.critical(None, 'GPS Tracker', u'Próba odzyskania danych nie powiodła się z powodu błędu przy odczycie informacji z ostatniej sesji.')
        return data

"""=============Wcięcie liniowe============"""
class GPSResection(with_metaclass(ErrorCatcher, QObject)):
    wgs84 = QgsCoordinateReferenceSystem(4326, QgsCoordinateReferenceSystem.EpsgCrsId)
    gpsDataChanged = pyqtSignal(QgsPoint)
    
    
    def __init__(self, parent=None):
        QObject.__init__(self, parent)
        self.parent = parent
        self.canvas = self.parent.iface.mapCanvas()
        self.leftPoint = None
        self.rightPoint = None
        self.rightDistance = 0.
        self.leftDistance = 0.
        self.leftMarker = None
        self.rightMarker = None
        self.calcMarker = None
    
    @pyqtSlot()
    def clean(self):
        self.leftPoint = None
        self.rightPoint = None
        self.rightDistance = 0.
        self.leftDistance = 0.
        self.leftMarker = self.showMarker(self.leftMarker, False)
        self.rightMarker = self.showMarker(self.rightMarker, False)
        self.calcMarker = self.showMarker(self.calcMarker, False)
        self.parent.lblAX.setText('N/A')
        self.parent.lblAY.setText('N/A')
        self.parent.lblBX.setText('N/A')
        self.parent.lblBY.setText('N/A')
        self.parent.lblXP.setText('N/A')
        self.parent.lblYP.setText('N/A')
        self.parent.sbAP.setValue(0.)
        self.parent.sbBP.setValue(0.)
    
    @pyqtSlot()
    def addCalcPoint(self):
        calcPoint = self.calcResection()
        if calcPoint:
            calcPoint = QgsPointXY(calcPoint)
            transform = QgsCoordinateTransform(self.canvas.mapSettings().destinationCrs(), self.wgs84, QgsProject.instance())
            calcPoint84 = transform.transform(calcPoint)
            pointData = {'x':calcPoint84.x(), 'y':calcPoint84.y(), 'lp':0}
            self.parent.tvPointList.model().insertRow(pointData, False)
    
    def setLeftPoint(self, point):
        self.leftPoint = QgsPointXY(point)
        self.leftMarker = self.showMarker(self.leftMarker, True, QColor('red'), self.leftPoint)
        self.parent.lblAX.setText(str(self.leftPoint.x()))
        self.parent.lblAY.setText(str(self.leftPoint.y()))
        self.calcResection()
    
    def setRightPoint(self, point):
        self.rightPoint = QgsPointXY(point)
        self.rightMarker = self.showMarker(self.rightMarker, True, QColor('blue'), self.rightPoint)
        self.parent.lblBX.setText(str(self.rightPoint.x()))
        self.parent.lblBY.setText(str(self.rightPoint.y()))
        self.calcResection()
    
    @pyqtSlot()
    def reversePoints(self):
        leftPoint = self.leftPoint
        self.leftPoint = self.rightPoint
        self.rightPoint = leftPoint
        self.calcResection()
        self.setMarkersVisible(2)
    
    def setLeftDistance(self, distance):
        self.leftDistance = distance
        self.calcResection()
    
    def setRightDistance(self, distance):
        self.rightDistance = distance
        self.calcResection()
        
    def noCalcResection(self):
        self.parent.lblXP.setText('N/A')
        self.parent.lblYP.setText('N/A')
        self.calcMarker = self.showMarker(self.calcMarker, False)
        return None
        
    def calcResection(self):
        if self.parent.getMeasureMethod() == 0:
            if self.leftPoint is not None and self.rightPoint is not None:
                c = sqrt(self.leftPoint.sqrDist(self.rightPoint))
                p = self.rightDistance
                l = self.leftDistance
                Xl = self.leftPoint.x()
                Yl = self.leftPoint.y()
                Xp = self.rightPoint.x()
                Yp = self.rightPoint.y()
                Ca = -p**2+l**2+c**2
                Cb = p**2-l**2+c**2
                Cc = p**2+l**2-c**2
                if Ca is not None and Cb is not None and Cc is not None:
                    try:
                        P4 = sqrt(Ca*Cb+Ca*Cc+Cb*Cc)
                        Xw = (Xl*Cb+Yl*P4+Xp*Ca-Yp*P4)/(Ca+Cb)
                        Yw = (-P4*Xl+Yl*Cb+P4*Xp+Yp*Ca)/(Ca+Cb)
                        self.parent.lblXP.setText(str(Xw))
                        self.parent.lblYP.setText(str(Yw))
                        calcPoint = QgsPoint(Xw, Yw)
                        self.calcMarker = self.showMarker(self.calcMarker, True, QColor('green'),  calcPoint)
                        return calcPoint
                    except:
                        self.noCalcResection()
                else:
                    self.noCalcResection()
            else:
                self.noCalcResection()
        else:
            if self.leftPoint is not None and self.rightPoint is not None:
                a = self.leftPoint
                b = self.rightPoint
                line = QgsGeometry.fromPolylineXY([a,b])
                dist = self.leftDistance
                if dist == 0.0:
                    self.noCalcResection()
                else:
                    calcPoint = (line.interpolate(dist).asPoint())
                    Xcp = calcPoint.x()
                    Ycp = calcPoint.y()
                    self.parent.lblXP.setText(str(Xcp))
                    self.parent.lblYP.setText(str(Ycp))
                    self.calcMarker = self.showMarker(self.calcMarker, True, QColor('green'), calcPoint)
                    return calcPoint 
            else:
                self.noCalcResection()
                
    def setMarkersVisible(self, index):
        if index != 2:
            if self.canvas.mapTool() == self.parent.getLeftPoint:
                self.canvas.unsetMapTool(self.parent.getLeftPoint)
            if self.canvas.mapTool() == self.parent.getRightPoint:
                self.canvas.unsetMapTool(self.parent.getRightPoint)
            self.calcMarker = self.showMarker(self.calcMarker, False)
        else:
            self.calcResection()
        self.leftMarker = self.showMarker(self.leftMarker, index==2 and self.leftPoint, QColor('red'), self.leftPoint)
        self.rightMarker = self.showMarker(self.rightMarker, index==2 and self.rightPoint, QColor('blue'), self.rightPoint)
    
    def showMarker(self, marker, visible, color=QColor('green'), point=None):
        if visible:
            if not marker:
                marker = self.createMarker(color)
            marker.setCenter(QgsPointXY(point))
        elif marker:
            self.canvas.scene().removeItem(marker)
            marker = None
        return marker
    
    def createMarker(self, color):
        marker = QgsVertexMarker(self.canvas)
        marker.setColor(color)
        return marker
 
class GPSGetCanvasPoint(with_metaclass(ErrorCatcher, QgsMapTool)):
    emitPoint = pyqtSignal(QgsPoint)
    
    def __init__(self, canvas, btn):
        QgsMapTool.__init__(self, canvas)
        self.setButton(btn)
        self.setSignals()
    
    def setSignals(self):
        self.mButton.toggled[bool].connect(self.setMapTool)
    
    def setMapTool(self, setTool):
        if setTool:
            self.canvas().setMapTool(self)
        else:
            self.canvas().unsetMapTool(self)
    
    def canvasReleaseEvent(self, e):
        p = self.toMapCoordinates(QPoint(e.x(), e.y()))
        self.emitPoint.emit(QgsPoint(p))
    
    def setButton(self, btn):
        self.mButton = btn
    
    def button(self):
        return self.mButton
    
    def activate(self):
        if self.mButton:
            self.mButton.setChecked(True)
        QgsMapTool.activate(self)
    
    def deactivate(self):
        try:
            if self.mButton:
                self.mButton.setChecked(False)
            QgsMapTool.deactivate(self)
        except:
            pass
    
    def isZoomTool(self):
        return False

    def isTransient(self):
        return False

    def isEditTool(self):
        return False