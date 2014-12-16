# -*- coding: utf-8 -*-
"""
/***************************************************************************
 GPS Tracker Plugin
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
 This script initializes the plugin, making it known to QGIS.
"""
def classFactory(iface):
    from GPSTracker import GPSTracker
    return GPSTracker(iface)