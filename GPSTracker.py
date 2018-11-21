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
from __future__ import absolute_import
# Import the PyQt and QGIS libraries
from builtins import object
from qgis.PyQt.QtCore import QSettings, Qt, QObject, pyqtSlot
from qgis.PyQt.QtGui import QColor, QIcon
from qgis.PyQt.QtWidgets import QAction
from qgis.core import  Qgis
from .GPSTrackerDialog import GPSTrackerDialog, startfile
from . import resources

class GPSTracker(object):
    def __init__(self, iface):
        # Save reference to the QGIS interface
        self.iface = iface

    def initGui(self):
        self.dock  = GPSTrackerDialog(self.iface)
        self.action = self.dock.toggleViewAction()
        self.action.setIcon(QIcon(":/plugins/GPSTrackerPlugin/icon.png"))
        self.action.setText(u"GPS Tracker Plugin")
        self.manual = QAction(QIcon(":/plugins/GPSTrackerPlugin/help.png"), u"Instrukcja obsługi", self.iface.mainWindow())
        # self.manual.triggered.connect(self.showManual)
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
        self.startfile(self.dock.pluginPath+'/doc/GPS Tracker instrukcja obslugi.pdf')