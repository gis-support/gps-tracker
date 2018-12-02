# -*- coding: utf-8 -*-
"""
/***************************************************************************
 GPSTrackerDialog
                                 A QGIS plugin
                              -------------------
        begin                : 2013-03-12
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
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import QDockWidget, QMenu, QAction, QColorDialog, QFileDialog
from qgis.core import *
from qgis.gui import *
from .Ui_GPSTracker import Ui_GPSTracker

from .gpsConnection import GPSConnection

from .gpsWidgets import GPSPointListView, GPSInfoListView

from math import sqrt
import json
from .gpsUtils import *
from future.utils import with_metaclass

try:
    from os import startfile
except:
    from subprocess import call
    from sys import platform
    def startfile(fileName):
        opener ="open" if platform == "darwin" else "xdg-open"
        call([opener, fileName])
       
class GPSTrackerDialog(with_metaclass(ErrorCatcher, type('NewBase', (QDockWidget , Ui_GPSTracker), {})) ):
    infoList = [[0., 0.], '', '', '', '', '', '', '', '', '', '', '']
    #pointList = [{'x':20.9, 'y':52.2, 'lp':10, 'text':'1 pomiar', 'checked':Qt.Checked, 'id':1}, 
    #             {'x':21.1, 'y':52.3, 'lp':30, 'text':'2 pomiar', 'checked':Qt.Checked, 'id':2},
    #             {'x':21.05, 'y':52.2, 'lp':20, 'text':'3 pomiar', 'checked':Qt.Checked, 'id':3}]
    # wgs84 = QgsCoordinateReferenceSystem(4326, QgsCoordinateReferenceSystem.EpsgCrsId)
    wgs84 = QgsCoordinateReferenceSystem(4326, QgsCoordinateReferenceSystem.EpsgCrsId)
    
    def __init__(self,iface):
        QDockWidget.__init__(self)
        self.iface = iface
        GPSLogger.iface = iface
        self.canvas = self.iface.mapCanvas()
        self.setupUi(self)
        self.setupCustomUi()
        self.connection = GPSConnection(self.infoList, self.tvInfoList.model(),
                                        QgsCoordinateReferenceSystem(4326, QgsCoordinateReferenceSystem.EpsgCrsId))
        self.marker = GPSMarker(self.canvas,
                                path.join(self.pluginPath, 'markers/krzyz w okregu.svg'),
                                self)
        self.path = GPSPath(self.canvas, self)
        self.dataWriter = GPSDataWriter(self, self.cmbLayers)
        self.getLeftPoint = GPSGetCanvasPoint(self.canvas, self.btnA)
        self.getLeftPoint.pointSide = 'left'
        self.getRightPoint = GPSGetCanvasPoint(self.canvas, self.btnB)
        self.getRightPoint.pointSide = 'right'
        self.resection = GPSResection(self)
        self.selectedMarker = GPSSelectedMarker(self.canvas)
        self.logger = GPSLogger(self)
        self.lastGpsPoint = None
        self.measureType = None
        self.doIntervalMeasure = False
        self.setMenus()
        self.setProjectCrs()
        self.loadSettings()
        self.setupSignals()
        self.groupBox_3.setVisible(False)
        self.pointListLogger = GPSMeasureSave(self.logger, QSettings().value('gpsTracker/measureSaveInterval', 1, type=int), QSettings().value('gpsTracker/measureSave', True, type=bool))
        self.tvPointList.model().insertRows(self.pointListLogger.loadMeasure())
        
    def clean(self):
        #if self.connection.getStatus() != self.connection.DISCONNECTED:
        #    self.connection.disconnectGPS()
        if self.pointListLogger.timer.isActive():
            self.pointListLogger.timer.stop()
        self.dataWriter.clean()
        self.path.clean()
        self.marker.clean()
        self.selectedMarker.clean()
        self.logger.clean()
        self.resection.setMarkersVisible(0)
    
    def setStatus(self, status):
        self.iface.mainWindow().statusBar().showMessage( u"GPS Tracker: %s" % status)
    
    def setupCustomUi(self):
        #self.tvPointList = GPSPointListView(self.pointList)
        self.tvPointList = GPSPointListView()
        self.vlPointList.addWidget(self.tvPointList)
        self.tvInfoList = GPSInfoListView(self.infoList)
        self.vlInfoList.addWidget(self.tvInfoList)
        self.iface.addDockWidget(Qt.RightDockWidgetArea,self)
        self.pluginPath = QFileInfo(__file__).absolutePath()
        #ikony
        self.btnPosition.setIcon(QIcon(path.join(self.pluginPath,'icons/direction.png')))
        self.btnPosition.pageIndex = 0
        self.btnLayers.setIcon(QIcon(path.join(self.pluginPath,'icons/connection.png')))
        self.btnLayers.pageIndex = 1
        self.btnOptions.setIcon(QIcon(path.join(self.pluginPath,'icons/settings.png')))
        self.btnOptions.pageIndex = 3
        self.btnCalcPoint.setIcon(QIcon(path.join(self.pluginPath,'icons/calcPoint.png')))
        self.btnCalcPoint.pageIndex = 2
        self.btnA.setIcon(QIcon(path.join(self.pluginPath,'icons/target.png')))
        self.btnB.setIcon(QIcon(path.join(self.pluginPath,'icons/target.png')))
        self.btnPorts.setIcon(QIcon(path.join(self.pluginPath,'icons/reloadPorts.png')))
        #ikony markera GPS
        markerPath = path.join(self.pluginPath,'markers')
        markerDir = QDir(markerPath)
        markerDir.setFilter(QDir.Files | QDir.NoSymLinks)
        for markerFile in markerDir.entryInfoList():
            self.cmbMarker.addItem(QIcon(markerFile.absoluteFilePath()), markerFile.fileName())
        #opcje
        self.cmbFontSizes.addItems([str(x) for x in QFontDatabase().standardSizes()])
    
    def loadSettings(self):
        s = QSettings()
        index = s.value('gpsTracker/pageNumber', 0, type=int)
        self.stack.setCurrentIndex(index)
        if index == 0:
            self.btnPosition.setChecked(True)
        elif index == 1:
            self.btnLayers.setChecked(True)
        elif index == 2:
            self.btnCalcPoint.setChecked(True)
        elif index == 3:
            self.btnOptions.setChecked(True)
        #Zakładka Położenie
        self.tvInfoList.verticalHeader().restoreState(s.value('gpsTracker/infoOrder', QByteArray(), type=QByteArray))
        distance = s.value('gpsTracker/measureDistance', 25, type=int)
        self.btnIntervalMeasure.setText('Automatyczny\npomiar co %d m' % distance)
        self.sbMeasureDistance.setValue(distance)
        #Zakładka Rejestracja punktów
        if s.value('gpsTracker/measureType', 'shotsAverage') == 'shotsAverage':
            self.rbShotsAverage.setChecked(True)
        else:
            self.rbTimeAverage.setChecked(True)
        self.sbMeasureCount.setValue(s.value('gpsTracker/measureCount', 5, type=int))
        self.cbDisplayPoints.setChecked(s.value('gpsTracker/displayPoints', False, type=bool))
        self.displayPoints(self.cbDisplayPoints.isChecked())
        value = s.value('gpsTracker/saveType', True, type=bool)
        if value:
            self.btnAddFeatures.setDefaultAction(self.saveAllPoints)
            self.btnAddFeatures.setText(u'Zap. wsz. pkt')
        else:
            self.btnAddFeatures.setDefaultAction(self.saveSelectedPoints)
            self.btnAddFeatures.setText(u'Zap. zaz. pkt')
        value = s.value('gpsTracker/measureUpdate', False, type=bool)
        if value == 0:
            self.btnMeasurePoint.setDefaultAction(self.newMeasure)
        else:
            self.btnMeasurePoint.setDefaultAction(self.updateMeasure)
        self.btnMeasurePoint.setEnabled(False)
        value = s.value('gpsTracker/selectionType', 2, type=int)
        if value == 0:
            self.btnSelection.setDefaultAction(self.selectNoneAction)
        elif value == 1:
            self.btnSelection.setDefaultAction(self.reverseSelectionAction)
        else:
            self.btnSelection.setDefaultAction(self.selectAllAction)
        value = s.value('gpsTracker/deleteItemType', 2, type=int)
        if value == 0:
            self.btnDeletePoint.setDefaultAction(self.deleteCheckedItems)
        elif value == 1:
            self.btnDeletePoint.setDefaultAction(self.deleteAll)
        else:
            self.btnDeletePoint.setDefaultAction(self.deleteSelectedItem)
        self.cmbMeasureMethod.setCurrentIndex(s.value('gpsTracker/measureMethod', 0, type=int))
        self.measureMethodChanged(self.cmbMeasureMethod.currentIndex())
        #Zakładka Opcje
        self.cmbCRS.setCurrentIndex(s.value('gpsTracker/crs', 4, type=int))
        self.pluginCrsChanged(self.cmbCRS.currentIndex())
        ports = s.value('gpsTracker/comList', '')
        self.getPorts(ports)
        index = self.cmbPorts.findText(s.value('gpsTracker/port', ''), Qt.MatchFixedString)
        if index>=0:
            self.cmbPorts.setCurrentIndex(index)
        else:
            self.cmbPorts.setCurrentIndex(0)
        self.gbMarker.setChecked(s.value('gpsTracker/showMarker', True, type=bool))
        index = self.cmbMarker.findText(s.value('gpsTracker/markerFile', ''), Qt.MatchFixedString)
        if index>=0:
            self.cmbMarker.setCurrentIndex(index)
        else:
            self.cmbMarker.setCurrentIndex(0)
        self.sMarkerSize.setValue(s.value('gpsTracker/markerSize', 24, type=int))
        self.setMarkerIcon(str(self.cmbMarker.currentText()))
        self.cmbCenter.setCurrentIndex(s.value('gpsTracker/centerType', 1, type=int))
        self.sbExt.setValue(s.value('gpsTracker/centerExtent', 50, type=int))
        self.sbExt.setEnabled(self.cmbCenter.currentIndex()==2)
        logDir = self.logger.verifyDirectory(s.value('gpsTracker/logDir', self.pluginPath+'/log'))
        self.eLogDir.setText(logDir)
        self.logger.changeDirectory(logDir)
        self.cbLogGPS.setChecked(s.value('gpsTracker/saveLog', False, type=bool))
        self.cbSaveMeasure.setChecked(s.value('gpsTracker/measureSave', True, type=bool))
        self.sbMesaureSaveTime.setValue(s.value('gpsTracker/measureSaveInterval', 1, type=int))
        self.logger.writeNmea = self.cbLogGPS.isChecked()
        self.gbPointDistance.setChecked(s.value('gpsTracker/showMarkerLabel', False, type=bool))
        fontName = s.value('gpsTracker/markerLabelFont', 'MS Shell Dlg 2')
        index = self.cmbFonts.findText(fontName, Qt.MatchFixedString)
        if index>=0:
            self.cmbFonts.setCurrentIndex(index)
        else:
            self.cmbFonts.setCurrentIndex(0)
        self.cmbFontSizes.setCurrentIndex(self.cmbFontSizes.findText(s.value('gpsTracker/markerLabelSize', '8'),Qt.MatchFixedString)) 
        self.btnFontColor.fontColor = QColor()
        self.btnFontColor.fontColor.setNamedColor(s.value('gpsTracker/markerLabelColor', 'black'))
        self.setPointDistanceStyle()
        self.cbOffsetMeasure.setChecked(s.value('gpsTracker/offsetMeasure', False, type=bool))
        self.sbOffsetDist.setValue(s.value('gpsTracker/offsetDist', 1, type=int))
        self.cmbOffsetDirection.setCurrentIndex(s.value('gpsTracker/offsetDirection', 0, type=int))
        
    def setMenus(self):
        #Przycisk Pomiar
        self.measureMenu = QMenu()
        self.newMeasure = QAction(u'Nowy pomiar', self)
        self.newMeasure.triggered.connect(self.measureStart)
        self.newMeasure.updatePoint = False
        self.btnMeasurePoint.updatePoint = False
        self.updateMeasure = QAction(u'Aktualizuj pomiar', self)
        self.updateMeasure.updatePoint = True
        self.updateMeasure.triggered.connect(self.measureStart)
        self.measureMenu.addAction(self.newMeasure)
        self.measureMenu.addAction(self.updateMeasure)
        self.btnMeasurePoint.setMenu(self.measureMenu)
        #Przycisk Usuń
        self.deleteMenu = QMenu()
        self.deleteSelectedItem = QAction(u'Usuń wybrany', self)
        self.deleteSelectedItem.triggered.connect(self.tvPointList.deleteItem)
        self.deleteCheckedItems = QAction(u'Usuń zaznaczone', self)
        self.deleteCheckedItems.all = False
        self.deleteCheckedItems.triggered.connect(self.tvPointList.deleteItems)
        self.deleteAll = QAction(u'Usuń wszystkie', self)
        self.deleteAll.all = True
        self.deleteAll.triggered.connect(self.tvPointList.deleteItems)
        self.deleteMenu.addAction(self.deleteSelectedItem)
        self.deleteMenu.addAction(self.deleteCheckedItems)
        self.deleteMenu.addAction(self.deleteAll)
        self.btnDeletePoint.setMenu(self.deleteMenu)
        #Przycisk Zaznaczenie
        self.selectionMenu = QMenu()
        self.selectAllAction = QAction(u'Zaznacz wszystkie', self)
        self.selectAllAction.state = Qt.Checked
        self.selectAllAction.triggered.connect(self.tvPointList.setItemsCheck)
        self.selectNoneAction = QAction(u'Odznacz wszystkie', self)
        self.selectNoneAction.state = Qt.Unchecked
        self.selectNoneAction.triggered.connect(self.tvPointList.setItemsCheck)
        self.reverseSelectionAction = QAction(u'Odwróć zaznaczenie', self)
        self.reverseSelectionAction.state = Qt.PartiallyChecked
        self.reverseSelectionAction.triggered.connect(self.tvPointList.setItemsCheck)
        self.selectionMenu.addAction(self.selectAllAction)
        self.selectionMenu.addAction(self.selectNoneAction)
        self.selectionMenu.addAction(self.reverseSelectionAction)
        self.btnSelection.setMenu(self.selectionMenu)
        #wcięcie liniowe
        self.calcMenuA = QMenu()
        self.calcMenuA.pointSide = 'left' #lewy czyli A
        self.btnA.setMenu(self.calcMenuA)
        self.calcMenuB = QMenu()
        self.calcMenuB.pointSide = 'right' #lewy czyli A
        self.btnB.setMenu(self.calcMenuB)
        #Przycisk Zapisz
        self.saveFeatureMenu = QMenu()
        self.saveAllPoints = QAction(u'Zapisz wszystkie punkty', self)
        self.saveAllPoints.allPoints = True
        self.saveAllPoints.triggered.connect(self.dataWriter.saveFeature)
        self.saveSelectedPoints = QAction(u'Zapisz zaznaczone punkty', self)
        self.saveSelectedPoints.allPoints = False
        self.saveSelectedPoints.triggered.connect(self.dataWriter.saveFeature)
        self.saveFeatureMenu.addAction(self.saveAllPoints)
        self.saveFeatureMenu.addAction(self.saveSelectedPoints)
        self.btnAddFeatures.setMenu(self.saveFeatureMenu)
        #Przycisk Katalog logowania
        self.logMenu = QMenu()
        self.openLog = QAction(u'Otwórz katalog logowania', self)
        self.openLog.triggered.connect(self.openLogDir)
        self.logMenu.addAction(self.openLog)
        self.btnChangeLogDir.setMenu(self.logMenu)

    def setupSignals(self):
        self.btnConnect.toggled[bool].connect(self.connectionToggled)
        #połączenie GPS
        self.connection.gpsConnectionStatusChanged[int].connect(self.connectionStatusChanged)
        self.connection.gpsFixTypeChanged.connect(self.fixTypeChanged)
        self.connection.gpsMeasureStopped[dict, bool].connect(self.measureStopped)
        self.connection.gpsPositionChanged[float,float].connect(self.positionChanged)
        self.connection.gpsMessage[str].connect(self.setStatus)
        self.connection.gpsConnectionStart.connect(self.logger.openFile)
        self.connection.gpsConnectionStop.connect(self.logger.closeFile)
        #zmiana układu współrzędnych
        self.canvas.destinationCrsChanged.connect(self.setProjectCrs)
        #zakładki
        self.btnPosition.clicked.connect(self.changePage)
        self.btnLayers.clicked.connect(self.changePage)
        self.btnCalcPoint.clicked.connect(self.changePage)
        self.btnOptions.clicked.connect(self.changePage)
        #pomiar
        self.rbTimeAverage.type = 'timeAverage'
        self.rbTimeAverage.clicked.connect(self.setMesaureType)
        self.rbShotsAverage.type = 'shotsAverage'
        self.rbShotsAverage.clicked.connect(self.setMesaureType)
        self.sbMeasureCount.type = 'measureCount'
        self.sbMeasureCount.valueChanged[int].connect(self.saveValue)
        self.cbDisplayPoints.stateChanged[int].connect(self.displayPoints)
        self.tvPointList.gpsSelectionChanged[int, QgsPoint].connect(self.selectedMarker.setMarker)
        self.btnIntervalMeasure.clicked[bool].connect(self.setIntervalMeasure)
        #wciecie liniowe
        self.stack.currentChanged[int].connect(self.resection.setMarkersVisible)
        self.getLeftPoint.emitPoint[QgsPoint].connect(self.setPoint)
        self.getRightPoint.emitPoint[QgsPoint].connect(self.setPoint)
        self.sbAP.valueChanged[float].connect(self.resection.setLeftDistance)
        self.sbBP.valueChanged[float].connect(self.resection.setRightDistance)
        self.bClear.clicked.connect(self.resection.clean)
        self.bReplace.clicked.connect(self.resection.reversePoints)
        self.bAddCalcPoint.clicked.connect(self.resection.addCalcPoint)
        self.calcMenuA.aboutToShow.connect(self.updatePointMenu)
        self.calcMenuA.aboutToHide.connect(self.deleteCalcMarker)
        self.calcMenuB.aboutToShow.connect(self.updatePointMenu)
        self.calcMenuB.aboutToHide.connect(self.deleteCalcMarker)
        self.cmbMeasureMethod.currentIndexChanged[int].connect(self.measureMethodChanged)
        #opcje
        self.cmbCRS.currentIndexChanged[int].connect(self.pluginCrsChanged)
        self.cmbPorts.currentIndexChanged[str].connect(self.portChanged)
        self.btnPorts.clicked.connect(self.getPorts)
        self.sbMeasureDistance.valueChanged[int].connect(self.setMeasureDistance)
        self.gbMarker.toggled[bool].connect(self.showMarker)
        self.cmbMarker.currentIndexChanged[str].connect(self.setMarkerIcon)
        self.sMarkerSize.valueChanged[int].connect(self.setMarkerSize)
        self.cmbCenter.currentIndexChanged[int].connect(self.setCenterType)
        self.sbExt.type = 'centerExtent'
        self.sbExt.valueChanged[int].connect(self.saveValue)
        self.cbLogGPS.toggled[bool].connect(self.setLogging)
        self.cbSaveMeasure.toggled[bool].connect(self.setMeasureSave)
        self.cbOffsetMeasure.toggled[bool].connect(self.offsetMeasureChanged)
        self.sbOffsetDist.valueChanged[int].connect(self.setOffsetDistance)
        #self.sbMesaureSaveTime.valueChanged[int].connect(self.setMeasureSaveInterval)
        self.sbMesaureSaveTime.editingFinished.connect(self.setMeasureSaveInterval)
        self.cmbOffsetDirection.currentIndexChanged[int].connect(self.offsetDirectionChanged)
        self.eLogDir.editingFinished.connect(self.setLogDirectory)
        self.btnChangeLogDir.clicked.connect(self.getLogDirectory)
        self.gbPointDistance.toggled[bool].connect(self.setPointDistance)
        self.cmbFonts.currentIndexChanged[str].connect(self.savePointDistanceStyle)
        self.cmbFontSizes.currentIndexChanged[str].connect(self.savePointDistanceStyle)
        self.btnFontColor.clicked.connect(self.savePointDistanceStyle)
    
    def saveSettings(self, key, value):
        s = QSettings()
        s.setValue('gpsTracker/%s' % key, value)
    
    """ sloty """
    def connectionToggled(self, checked):
        if checked:
            self.connection.setPort(self.cmbPorts.itemData(self.cmbPorts.currentIndex()))
            self.connection.connectGPS()
        else:
            if self.connection.getStatus() != self.connection.DISCONNECTED:
                self.connection.disconnectGPS()
    
    def connectionStatusChanged(self, status):
        if status == self.connection.DISCONNECTED:
            self.btnConnect.setStyleSheet('')
            self.btnConnect.setChecked(False)
            self.btnConnect.setEnabled(True)
            self.btnConnect.setText(u'Połącz')
            self.btnMeasurePoint.setEnabled(False)
            self.setIntervalMeasure(False)
            self.btnIntervalMeasure.setChecked(False)
            self.btnIntervalMeasure.setEnabled(False)
        elif status == self.connection.CONNECTED:
            self.btnConnect.setStyleSheet('background-color: rgb(0, 250, 0);')
            self.btnConnect.setEnabled(True)
            self.btnConnect.setText(u'Rozłącz')
            self.btnMeasurePoint.setEnabled(True)
            self.btnIntervalMeasure.setEnabled(True)
        elif status == self.connection.NO_FIX:
            self.btnConnect.setStyleSheet('background-color: rgb(255, 0, 0);')
            self.btnConnect.setEnabled(True)
            self.btnConnect.setText(u'Rozłącz')
            self.btnMeasurePoint.setEnabled(False)
            self.btnIntervalMeasure.setEnabled(False)
        elif status == self.connection.CONNECTING:
            self.btnConnect.setEnabled(False)
            self.btnIntervalMeasure.setEnabled(False)
            self.btnConnect.setText(u'Łączenie...')
        self.marker.setMarkerVisible(status == self.connection.CONNECTED and self.gbMarker.isChecked())
    
    def fixTypeChanged(self, fixType):
        if fixType == 2:
            self.btnConnect.setStyleSheet('background-color: rgb(255, 255, 0);')
        elif fixType == 3:
            self.btnConnect.setStyleSheet('background-color: rgb(0, 255, 0);')
    
    def measureStopped(self, data, updatePoint):
        self.tvPointList.model().insertRow(data, updatePoint)
        if updatePoint:
            self.selectedMarker.setMarker(0, QgsPoint(data['x'], data['y']))
    
    def positionChanged(self, x, y):
        self.marker.setMarkerPos(x, y)
        gpsCoords = self.transform.transform(x, y)
        if not self.lastGpsPoint == gpsCoords:
            if self.doIntervalMeasure:
                try:
                    self.checkInterval(x, y)
                except:
                    return
            self.lastGpsPoint = gpsCoords
            if self.cmbCenter.currentIndex() == 0:
                self.moveCanvas(gpsCoords)
            elif self.cmbCenter.currentIndex() == 2:
                extentlimt = QgsRectangle(self.canvas.extent())
                extentlimt.scale(self.sbExt.value()/100.)
                if not extentlimt.contains(gpsCoords):
                    self.moveCanvas(gpsCoords)
    
    def moveCanvas(self, newCenter):
        newExtent = QgsRectangle(newCenter, newCenter)
        self.canvas.setExtent(newExtent)
        self.canvas.refresh()
    
    def setProjectCrs(self):
        self.transform = QgsCoordinateTransform(self.wgs84, self.canvas.mapSettings().destinationCrs(), QgsProject.instance())
        self.marker.transform = self.transform
        self.path.transform = self.transform
        self.path.dataChanged()
        self.selectedMarker.transform = self.transform
        if self.selectedMarker.point:
            self.selectedMarker.setMarker(0, self.selectedMarker.point)
    
    @pyqtSlot()
    def changePage(self):
        index = self.sender().pageIndex
        self.stack.setCurrentIndex(int(index))
        self.btnPosition.setChecked(index==0)
        self.btnLayers.setChecked(index==1)
        self.btnCalcPoint.setChecked(index==2)
        self.btnOptions.setChecked(index==3)
        self.saveSettings('pageNumber', self.stack.currentIndex())
    
    @pyqtSlot()
    def setMesaureType(self):
        self.saveSettings('measureType', self.sender().type)
    
    def setMeasureDistance(self, value):
        self.saveSettings('measureDistance', value)
        self.btnIntervalMeasure.setText('Automatyczny\npomiar co %d m' % value)
    
    def saveValue(self, i):
        self.saveSettings('measureCount', i)
    
    def setPoint(self, point):
        if self.sender().pointSide == 'left':
            self.resection.setLeftPoint(point)
        else:
            self.resection.setRightPoint(point)
    
    def updatePointMenu(self):
        menu = self.sender()
        menu.clear()
        self.calcMarker = QgsVertexMarker(self.canvas)
        self.calcMarker.setColor(QColor('black'))
        self.calcMarker.setIconType(QgsVertexMarker.ICON_CROSS)
        points = self.tvPointList.model().getPointList(True)
        transform = QgsCoordinateTransform(self.wgs84, self.canvas.mapSettings().destinationCrs(), QgsProject.instance())
        
        for coords in points:
            point = transform.transform(coords['x'], coords['y'])
            action = QAction('Punkt %d (%f,%f)' % (coords['id'], point.x(), point.y()), menu)
            action.setData([point.x(), point.y()])
            action.triggered.connect(self.addCalcPoint)
            action.hovered.connect(self.showCalcPoint)
            menu.addAction(action)
    
    def deleteCalcMarker(self):
        self.canvas.scene().removeItem(self.calcMarker)
        del self.calcMarker
    
    @pyqtSlot()
    def addCalcPoint(self):
        coords = self.sender().data()
        point = QgsPoint(coords[0], coords[1])
        if self.sender().parent().pointSide == 'left':
            self.resection.setLeftPoint(point)
        else:
            self.resection.setRightPoint(point)
    
    def showCalcPoint(self):
        coords = self.sender().data()
        point = QgsPoint(coords[0], coords[1])
        self.calcMarker.setCenter(QgsPointXY(point))
    
    def pluginCrsChanged(self, index):
        crs = QgsCoordinateReferenceSystem(2176+index,)
        transform = QgsCoordinateTransform(self.wgs84, crs, QgsProject.instance())
        self.tvInfoList.model()._displayTranformation = transform
        self.logger.transform = transform
        self.setWindowTitle(u'GPS Tracker - PUWG %s' % self.cmbCRS.currentText())
        self.saveSettings('crs', self.cmbCRS.currentIndex())
        
    def offsetDirectionChanged(self, index):
        if index == 0:
            self.saveSettings('gpsTracker/offsetDirection', self.cmbMeasureMethod.currentIndex())
        else:
            self.saveSettings('gpsTracker/offsetDirection', self.cmbMeasureMethod.currentIndex())
     
    def measureMethodChanged(self, index):
        self.resection.calcResection()
        if index == 0:
            self.sbBP.setEnabled(True)
            self.saveSettings('measureMethod', self.cmbMeasureMethod.currentIndex())
        else:
            self.sbBP.setEnabled(False)
            self.saveSettings('measureMethod', self.cmbMeasureMethod.currentIndex())
       
    def getMeasureMethod(self):
        if self.cmbMeasureMethod.currentIndex() == 0:
            return 0
        else:
            return 1
    
    def offsetMeasureChanged(self, checked):
        if self.cbOffsetMeasure.isChecked() and checked:
            self.saveSettings('offsetMeasure', True)
        else:
            self.saveSettings('offsetMeasure', False)

    def setOffsetDistance(self, value):
        self.saveSettings('offsetDist', value)
            
    def portChanged(self, text):
        self.saveSettings('port', text)
    
    @pyqtSlot()
    def getPorts(self, ports=''):
        """ Sprawdzenie czy są zarejestrowane połączenia """
        connections = QgsApplication.gpsConnectionRegistry().connectionList()
        if len(connections) > 0 and self.connection.getStatus() == self.connection.DISCONNECTED:
            msg = QMessageBox.question(None, 'GPS Tracker Plugin',
                                           u'Wykryto zarejestrowane połączenia! Nie wszystkie dostępne porty mogą być widoczne na liście.\
                                           \nCzy chcesz zamknąć otwarte połączenia?',
                                           QMessageBox.Yes | QMessageBox.No)
            if msg == QMessageBox.Yes:
                for connection in connections:
                    connection.close()
                    QgsApplication.gpsConnectionRegistry().unregisterConnection(connection)
        if not ports:
            ports = json.dumps([[str(x[0]), str(x[1])] for x in QgsGpsDetector.availablePorts()[1:]])
            self.saveSettings('comList', ports)
        self.cmbPorts.clear()
        portList = json.loads(ports)
        for port in portList:
            self.cmbPorts.addItem(port[1], port[0])
    
    def showMarker(self, checked):
        self.marker.setMarkerVisible(self.connection.getStatus() == self.connection.CONNECTED and checked)
        self.saveSettings('showMarker', checked)
    
    def setMarkerIcon(self, fileName):
        markerPath = self.pluginPath+'/markers/'+fileName
        self.marker.setMarkerIcon(markerPath)
        self.setMarkerPreview(self.sMarkerSize.value())
        self.saveSettings('markerFile', fileName)
    
    def setMarkerPreview(self, size):
        p = self.marker.markerImg.pixmap(size, size)
        self.lblMarker.setPixmap(p)
    
    def setMarkerSize(self, value):
        self.marker.setMarkerSize(value)
        self.setMarkerPreview(value)
        self.saveSettings('markerSize', value)
    
    def setCenterType(self, index):
        self.sbExt.setEnabled(index==2)
        self.saveSettings('centerType', index)
    
    def setLogging(self, check):
        self.logger.writeNmea = check
        self.saveSettings('saveLog', check)
    
    def setMeasureSave(self, checked):
        if checked:
            self.pointListLogger.timer.start()
        else:
            self.pointListLogger.timer.stop()
        self.saveSettings('measureSave', checked)
    
    def setMeasureSaveInterval(self):
        value = self.sbMesaureSaveTime.value()
        self.pointListLogger.setInterval(value)
        self.pointListLogger.saveMeasure()
        self.saveSettings('measureSaveInterval', value)
    
    def setLogDirectory(self):
        logDir = self.logger.verifyDirectory(self.eLogDir.text())
        self.eLogDir.setText(logDir)
        self.eLogDir.setToolTip(logDir)
        self.logger.changeDirectory(logDir)
        self.saveSettings('logDir', logDir)
    
    @pyqtSlot()
    def getLogDirectory(self):
        logDir = QFileDialog.getExistingDirectory(None, 'Katalog logowania', self.eLogDir.text(),  QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks)
        self.eLogDir.setText(logDir)
        self.setLogDirectory()
    
    def setPointDistance(self, check):
        self.saveSettings('showMarkerLabel', self.gbPointDistance.isChecked())
        
    def setPointDistanceStyle(self):
        self.lblSampleText.setStyleSheet('color: %s;font: bold %spt "%s";'
                                         % (str(self.btnFontColor.fontColor.name()),
                                            self.cmbFontSizes.currentText(), 
                                            self.cmbFonts.currentFont().family()))
        self.marker.setMarkerFont(self.cmbFonts.currentText(),
                                  self.btnFontColor.fontColor,
                                  int(self.cmbFontSizes.currentText()))
    
    @pyqtSlot()
    def savePointDistanceStyle(self):
        if self.sender().objectName() == 'btnFontColor':
            self.sender().fontColor = QColorDialog.getColor()
        self.setPointDistanceStyle()
        self.saveSettings('markerLabelFont', self.cmbFonts.currentText())
        self.saveSettings('markerLabelColor', self.btnFontColor.fontColor.name())
        self.saveSettings('markerLabelSize', self.cmbFontSizes.currentText())
    
    def displayPoints(self, visible):
        self.path.setVisible(visible)
        self.saveSettings('displayPoints', visible)
    
    @pyqtSlot()
    def measureStart(self):
        sender = self.sender()
        updatePoint = sender.updatePoint
        self.saveSettings('measureUpdate', int(updatePoint))
        self.btnMeasurePoint.setDefaultAction(sender)
        if updatePoint and not len(self.tvPointList.selectedIndexes()):
            QMessageBox.information(None, u'GPS Tracker Plugin', u'Zaznacz punkt na liście aby zaktualizować jego pozycję!')
            return
        self.connection.startMeasuring(self.sbMeasureCount.value(), updatePoint, self.rbTimeAverage.isChecked())
    
    def setIntervalMeasure(self, checked):
        if checked:
            if self.tvPointList.model().rowCount() > 0 and self.connection.getStatus() == self.connection.CONNECTED:
                self.doIntervalMeasure = True
            else:
                self.btnIntervalMeasure.setChecked(False)
                self.doIntervalMeasure = False
                self.doIntervalMeasure = False
        else:
            self.doIntervalMeasure = False
    
    @pyqtSlot()
    def openLogDir(self):
        startfile(str(self.eLogDir.text()))
    
    def checkInterval(self, x, y):
        lastPointCoords = self.tvPointList.model().getLastPoint()
        lastPoint = self.transform.transform(lastPointCoords[0], lastPointCoords[1])
        thisPoint = self.transform.transform(x, y)
        distance = lastPoint.sqrDist(thisPoint)
        measureDistance = self.sbMeasureDistance.value()
        if distance > measureDistance**2:
            calcPoint = self.transform.transform(self.getPointAtDistance(lastPoint, thisPoint, measureDistance), QgsCoordinateTransform.ReverseTransform)
            self.tvPointList.model().insertRow({'x':calcPoint.x(), 'y':calcPoint.y(), 'lp':1}, False)
    
    @staticmethod
    def getPointAtDistance(p1, p2, distance):
        x = p2.x()-p1.x()
        y = p2.y()-p1.y()
        
        length = sqrt(x**2+y**2)
        x /= length
        y /= length
        
        x *= distance
        y *= distance
        return QgsPointXY(p1.x()+x, p1.y()+y)
        
        
        # if(self.cbOffsetMeasure.isChecked == True):
            # measureOffset = self.sbOffsetDist
            # if(self.cmbOffsetDirection.currentIndex() == 0):
                # angle = 270
                # calcPoint = thisPoint.project(measureOffset, angle)
            # else:
                # angle = 90
                # calcPoint = thisPoint.project(measureOffset, angle)
                # calcPoint = self.transform.transform(point_offset, QgsCoordinateTransform.ReverseTransform)
                
                
    # def pointReceived(self, coords, updatePoint=False):
        # if updatePoint or not self.activeLayer:
            # return
        # print (coords)
        # if self.activeLayer.isEditable() and self.activeLayer.geometryType() == QgsWkbTypes.PointGeometry:
            # if(self.parent.cbOffsetMeasure.isChecked == True):
                # measureOffset = self.parent.sbOffestDist
                # p = QgsPoint(coords['x'], coords['y'])
                # if(self.parent.cmbOffsetDirection.currentIndex() == 0):
                    # angle = 270
                    # calcPoint = p.project(measureOffset, angle)
                    # self.fields = self.activeLayer.fields()
                    # coords['x'] = calcPoint.x()
                    # coords['y'] = calcPoind.y()
                    # self.savePoint(coords, self.parent.tvPointList.model().rowCount(), self.getShowFeatureForm())
                    # print (coords)
                # else:
                    # angle = 90
                    # calcPoint = p.project(measureOffset, angle)
                    # self.fields = self.activeLayer.fields()
                    # coords['x'] = calcPoint.x()
                    # coords['y'] = calcPoind.y()
                    # self.savePoint(coords, self.parent.tvPointList.model().rowCount(), self.getShowFeatureForm())
                    # print (coords)
            # else:
                # self.fields = self.activeLayer.fields()
                # self.savePoint(coords, self.parent.tvPointList.model().rowCount(), self.getShowFeatureForm())
                # self.parent.iface.mapCanvas().refresh()
        
 