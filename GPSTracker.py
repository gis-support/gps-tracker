# -*- coding: utf-8 -*-
"""
/***************************************************************************
 GPSTracker
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
# Import the PyQt and QGIS libraries
from PyQt4.QtCore import QSettings, Qt, QObject, SIGNAL, pyqtSlot
from PyQt4.QtGui import QColor, QAction, QIcon
from qgis.core import  QGis
from GPSTrackerDialog import GPSTrackerDialog, startfile
import resources

class GPSTracker:
    def __init__(self, iface):
        # Save reference to the QGIS interface
        self.iface = iface

    def initGui(self):
        self.dock  = GPSTrackerDialog(self.iface)
        self.action = self.dock.toggleViewAction()
        self.action.setIcon(QIcon(":/plugins/GPSTrackerPlugin/icon.png"))
        self.action.setText(u"GPS Tracker Plugin")
        self.manual = QAction(QIcon(":/plugins/GPSTrackerPlugin/help.png"), u"Instrukcja obsługi", self.iface.mainWindow())
        self.manual.triggered.connect(self.showManual)
        self.iface.addToolBarIcon(self.action)
        self.iface.addPluginToMenu("GPS Tracker Plugin", self.action)
        self.iface.addPluginToMenu("GPS Tracker Plugin", self.manual)

    def unload(self):
        self.iface.removeDockWidget(self.dock)
        self.iface.removeToolBarIcon(self.action)
        self.iface.removePluginMenu("GPS Tracker Plugin",self.action)
        self.iface.removePluginMenu("GPS Tracker Plugin",self.manual)
        self.dock.clean()
    
    @pyqtSlot()
    def showManual(self, checked):
        startfile(self.dock.pluginPath+'/doc/GPS Tracker instrukcja obslugi.pdf')