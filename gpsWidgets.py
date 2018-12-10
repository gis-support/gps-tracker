# -*- coding: utf-8 -*-
"""
/***************************************************************************
 gpsWidgets   A QGIS plugin
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
from PyQt5.QtWidgets import QStyledItemDelegate, QTableView, QAbstractItemView, QMessageBox, QLineEdit
from qgis.core import *
from .gpsUtils import ErrorCatcher
from future.utils import with_metaclass
from . import GPSTrackerDialog as trackerDialog

class GPSEditDelegate(with_metaclass(ErrorCatcher, QStyledItemDelegate)):
    def createEditor(self, parent, option, index):
        edit = QLineEdit(parent)
        return edit

    def setEditorData(self, editor, index):
        editor.setText(index.data(Qt.EditRole))
    
    def setModelData(self, editor, model, index):
        text = editor.text()
        model.setData(index, text)

"""=============Modele danych============"""
class GPSModel(with_metaclass(ErrorCatcher, QAbstractTableModel)):
    def __init__(self, tableView, parent=None):
        QAbstractTableModel.__init__(self, parent)
        self.tableView = tableView

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self._hHeader[section]
        return QAbstractTableModel.headerData(self, section, orientation, role)
    
    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < self.rowCount():
            return NULL
        row = index.row()
        if role == Qt.BackgroundRole:
            if self.tableView.verticalHeader().visualIndex(row) % 2 != 0:
                return QBrush(QColor(0, 0, 0, 20))
        return NULL

class GPSInfoListModel(GPSModel):
    wgs84 = QgsCoordinateReferenceSystem(4326, QgsCoordinateReferenceSystem.EpsgCrsId)
    toolTips = {'X':u'Długość geograficzna', u'Y':u'Szerokość geograficzna', u'H':u'Wysokość anteny odbiornika GPS w stosunku do geoidy',
                u'PDOP':u'Pozycyjne rozmycie dokładności',u'HDOP':u'Poziome rozmycie dokłądności',u'VDOP':u'Pionowe rozmycie dokładności',
                u'Dok. H':u'Dokładność pozioma pomiaru',u'Dok. V':u'Dokładność pionowa pomiaru',u'Tryb':u'Tryb konfiguraci odbiornika GPS (autmatyczny/manualny',
                u'Wymiary':u'Wymiary położenia (2D/3D/brak)',u'Jakość':u'Jakość sygnału (m.in. nieróżnicowy, różnicowy, RTK',
                u'Stan':u'Stan sygnału (poprawny/nieporpawny',u'Satelity':u'Liczba satelitów do ustalenia pozycji'}
    
    def __init__(self, data, tableView, parent=None):
        self._data = data
        self._vHeader = [u'X', u'Y', u'H', u'PDOP', u'HDOP', u'VDOP', u'Dok. H', u'Dok. V',
                        u'Tryb', u'Wymiary', u'Jakość', u'Stan', u'Satelity']
        GPSModel.__init__(self, tableView, parent)
    
    def columnCount(self, parent=QModelIndex()):
        return 1
    
    def rowCount(self, parent=QModelIndex()):
        return len(self._data)+1
    
    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Vertical:
            return self._vHeader[section]
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return u'Wartość'
    
    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < self.rowCount():
            return NULL
        row = index.row()
        if role == Qt.DisplayRole:
            if row == 0:
                if self._data[0][0] == 0. and self._data[0][1] == 0.:
                    return ''
                else:
                    return str(self._displayTranformation.transform(self._data[0][0], self._data[0][1]).x())
            elif row == 1:
                if self._data[0][0] == 0. and self._data[0][1] == 0.:
                    return ''
                else:
                    return str(self._displayTranformation.transform(self._data[0][0], self._data[0][1]).y())
            else:
                return self._data[row-1]
        elif role == Qt.ToolTipRole:
            return self.toolTips[self._vHeader[row]]
    
    def setCoordsTransform(self, transform):
        self._displayTranformation = transform

class GPSPointListModel(GPSModel):
    _hHeader = ['L.pom.', 'Opis']
    lastDescription = ''
    
    def __init__(self, data, tableView, parent=None):
        self._data = data
        GPSModel.__init__(self, tableView, parent)
        self.movingRow = False
    
    def columnCount(self, parent=QModelIndex()):
        return 2
    
    def rowCount(self, parent=QModelIndex()):
        return len(self._data)
    
    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Vertical:
            return 'Punkt %d' % self._data[section]['id']
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self._hHeader[section]
    
    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < self.rowCount():
            return NULL
        row = index.row()
        col = index.column()
        if role == Qt.DisplayRole:
            if col == 0:
                return self._data[row]['lp']
            elif col == 1:
                return self._data[row]['text']
        elif role == Qt.EditRole:
            return self._data[row]['text']
        elif role == Qt.CheckStateRole:
            if col == 0:
                return self._data[row]['checked']
        elif role == Qt.TextAlignmentRole:
            if col == 0:
                return Qt.AlignCenter
            else:
                return Qt.AlignLeft | Qt.AlignVCenter
        elif role == Qt.FontRole:
            if self._data[row]['checked'] == Qt.Unchecked:
                font = QFont()
                font.setItalic(True)
                return font
        elif role == Qt.UserRole:
            x = self._data[row]['x']
            y = self._data[row]['y']
            return [x, y]
        
        GPSModel.data(self, index, role)
    
    def flags(self, index):
        flag = QAbstractTableModel.flags(self, index) | Qt.ItemIsDragEnabled | Qt.ItemIsDropEnabled
        if index.column() == 1:
            return flag | Qt.ItemIsEditable
        else:
            return flag | Qt.ItemIsUserCheckable
    
    def setData(self, index, value, role=Qt.EditRole):
        row = index.row()
        # self._data[row].update({"rzedna": h})
        if role == Qt.EditRole:
            self._data[row]['text'] = value
            self.lastDescription = value
            self.tableView.resizeRowToContents(row)
        elif role == Qt.CheckStateRole:
            self._data[row]['checked'] = value
        elif role == Qt.UserRole: #uaktualnienie współrzędnych punktu
            self._data[row]['x'] = value['x']
            self._data[row]['y'] = value['y']
            self._data[row]['lp'] = value['lp']
            self._data[row]['rzedna'] = value['rzedna']
        lastIndex = self.index(index.row(), 1)
        self.dataChanged.emit(index, lastIndex)
        return True
    
    def removeRow(self, row, parent=QModelIndex()):
        self.beginRemoveRows(parent, row, row)
        self._data.pop(row)
        self.endRemoveRows()
        self.dataChanged.emit(QModelIndex(), QModelIndex())
        return True
    
    def insertRow(self, data, updatePoint):
        if updatePoint:
            self.setData(self.tableView.selectedIndexes()[0], data, Qt.UserRole)
            return True
        self.beginInsertRows(QModelIndex(), len(self._data), len(self._data))
        lastIndex = self.getNewIndex()
        self._data.append(data)
        self._data[-1].update({'text':self.lastDescription, 'checked':Qt.Checked, 'id':lastIndex})
        self.endInsertRows()
        item = self.index(len(self._data), 0)
        self.dataChanged.emit(item, item)
        self.tableView.resizeRowToContents(len(self._data)-1)
        return True
    
    def insertRows(self, data):
        self.beginInsertRows(QModelIndex(), 0, len(data)-1)
        self._data = data
        self.endInsertRows()
        return True
    
    def moveRow(self, logicalIndex, oldVisualIndex, newVisualIndex):
        if self.movingRow:
            self.movingRow = False
            return
        self.movingRow = True
        self._data.insert(newVisualIndex, self._data.pop(oldVisualIndex))
        self.tableView.verticalHeader().moveSection(newVisualIndex, oldVisualIndex)
        self.dataChanged.emit(self.index(0, 0), self.index(self.rowCount()-1, 1))
    
    def getPointList(self, allPoints=False):
        return [point for point in self._data if point['checked'] == Qt.Checked or allPoints]
    
    def getLastPoint(self):
        if self.rowCount() == 0:
            return None
        else:
            lastItem = self._data[-1]
            return (lastItem['x'], lastItem['y'])
    
    def getNewIndex(self):
        if self._data:
            return max([x['id'] for x in self._data])+1
        else:
            return 1

"""=============Kontrolki============"""
class GPSListView(with_metaclass(ErrorCatcher, QTableView)):
    def __init__(self, data=[], parent=None):
        QTableView.__init__(self, parent)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.verticalHeader().setSectionsMovable(True)
    
    def mousePressEvent(self, event):
        if self.rowAt(event.y()) == -1:
            self.clearSelection()
        QTableView.mousePressEvent(self, event)

class GPSInfoListView(GPSListView):
    def __init__(self, data=[], parent=None):
        GPSListView.__init__(self, parent)
        self.setModel(GPSInfoListModel(data, self))
        self.horizontalHeader().setStretchLastSection(True)
        self.verticalHeader().sectionMoved[int, int, int].connect(self.saveVHeaderState)
    
    def saveVHeaderState(self, logicalIndex, oldVisualIndex, newVisualIndex):
        QSettings().setValue('gpsTracker/infoOrder', self.verticalHeader().saveState())

class GPSPointListView(GPSListView):
    checkState = {True:Qt.Checked, False:Qt.Unchecked}
    gpsSelectionChanged = pyqtSignal(int, QgsPoint)
    
    def __init__(self, data=[], parent=None):
        GPSListView.__init__(self, parent)
        self.setModel(GPSPointListModel(data, self))
        self.setItemDelegateForColumn(1, GPSEditDelegate())
        self.resizeRowsToContents()
        self.resizeColumnToContents(0)
        #self.setContextMenuPolicy(Qt.CustomContextMenu)
        #self.customContextMenuRequested[QPoint].connect(self.displayMenu)
        self.horizontalHeader().setStretchLastSection(True)
        self.verticalHeader().sectionMoved[int, int, int].connect(self.model().moveRow)
    
    def displayMenu(self, pos):
        item = self.indexAt(pos)
        if item.row() == -1:
            return
        menu = QMenu(self)
        deleteAction = QAction(u'Usuń', menu)
        deleteAction.triggered[bool].connect(self.deleteItem)
        menu.addAction(deleteAction)
        
        lblF = QFont()
        lblF.setItalic(True)
        lbl = QLabel('Zaznaczenie')
        lbl.setAlignment(Qt.AlignHCenter)
        lbl.setFont(lblF)
        lbl.setStyleSheet("QLabel { color : grey; padding:4px 5px 4px 25px ;}")
        wa = QWidgetAction(menu)
        wa.setDefaultWidget(lbl)
        menu.addAction(wa)
        
        firstItem = item.sibling(item.row(), 0)
        checkAction = QAction(menu)
        checkAction.setCheckable(True)
        if firstItem.data(Qt.CheckStateRole) == Qt.Checked:
            checkAction.setText(u'Odznacz')
            checkAction.setChecked(True)
        else:
            checkAction.setText(u'Zaznacz')
            checkAction.setChecked(False)
        checkAction.triggered[bool].connect(self.setItemCheck)
        menu.addAction(checkAction)
        menu.exec_(QCursor.pos())
    
    def deleteItem(self, checked=True, item=None):
        parent = self.sender().parent()
        parent.saveSettings('deleteItemType', 2)
        parent.btnDeletePoint.setDefaultAction(self.sender())
        if self.model().rowCount() == 0:
            return
        if not item:
            if len(self.selectedIndexes())==0:
                QMessageBox.critical(None, 'GPS Tracker Plugin', u'Wybierz punkt do usunięcia')
                return
            else:
                item = self.selectedIndexes()[0]
                msg = QMessageBox.question(None, 'GPS Tracker Plugin', u'Czy usunąć wybrany punkt?', QMessageBox.Yes | QMessageBox.No)
                if msg == QMessageBox.No:
                    return
        self.model().removeRow(item.row())
    
    def deleteItems(self, checked):
        
        sender = self.sender()
        parent = sender.parent()
        parent.saveSettings('deleteItemType', int(sender.all))
        parent.btnDeletePoint.setDefaultAction(sender)
        if self.model().rowCount() == 0:
            return
        msg = QMessageBox.question(None, 'GPS Tracker Plugin', u'Czy usunąć punkty?', QMessageBox.Yes | QMessageBox.No)
        if msg == QMessageBox.No:
            return
        indexes = list(range(self.model().rowCount()))
        indexes.reverse()
        for i in indexes:
            item = self.model().index(i, 0)
            if not sender.all and item.data(Qt.CheckStateRole) == Qt.Unchecked:
                continue
            self.deleteItem(True, item)
    
    def setItemCheck(self, checked):
        item = self.selectedIndexes()[0]
        self.model().setData(item, self.checkState[checked], Qt.CheckStateRole)
    
    def setItemsCheck(self, checked):
        sender = self.sender()
        parent = sender.parent()
        state = sender.state
        parent.btnSelection.setDefaultAction(sender)
        parent.saveSettings('selectionType', state)
        for i in range(self.model().rowCount()):
            item = self.model().index(i, 0)
            if state != Qt.PartiallyChecked:
                self.model().setData(item, state, Qt.CheckStateRole)
            else:
                self.model().setData(item, self.checkState[item.data(Qt.CheckStateRole) !=Qt.Checked],
                                     Qt.CheckStateRole)
    
    def selectionChanged(self, selected, deselected):
        if len(selected.indexes()) == 0:
            row = -1
            point = QgsPoint()
        else:
            row = selected.indexes()[0].row()
            x, y = self.model().index(selected.indexes()[0].row(), 0).data(Qt.UserRole)
            point = QgsPoint(x, y)
        self.gpsSelectionChanged.emit(row, point)
        GPSListView.selectionChanged(self, selected, deselected)