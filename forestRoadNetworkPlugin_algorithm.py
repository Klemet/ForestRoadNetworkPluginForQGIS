# -*- coding: utf-8 -*-

"""
/***************************************************************************
 ForestRoads
                                 A QGIS plugin
 Create a network of forest roads based on zones to access, roads to connect
 them to, and a cost matrix.
 The code of the plugin is based on the "LeastCostPath" plugin available on
 https://github.com/Gooong/LeastCostPath. We thank their team for the template.
 Generated by Plugin Builder: http://g-sherman.github.io/Qgis-Plugin-Builder/
                              -------------------
        begin                : 10-07-2019
        copyright            : (C) 2019 by Clement Hardy
        email                : clem.hardy@outlook.fr
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
 This script describes the algorithm used to make the forest road network.
"""

__author__ = 'clem.hardy@outlook.fr'
__date__ = 'Currently in work'
__copyright__ = '(C) 2019 by Clement Hardy'

# FOR TEST PURPOSES : TO REMOVE
import random

# We load every function necessary from the QIS packages.
from PyQt5.QtCore import QCoreApplication, QVariant
from PyQt5.QtGui import QIcon
from qgis.core import (
    QgsFeature,
    QgsGeometry,
    QgsPoint,
    QgsPointXY,
    QgsField,
    QgsFields,
    QgsWkbTypes,
    QgsProcessing,
    QgsFeatureSink,
    QgsProcessingException,
    QgsProcessingAlgorithm,
    QgsProcessingParameterFeatureSource,
    QgsProcessingParameterFeatureSink,
    QgsProcessingParameterRasterLayer,
    QgsProcessingParameterBand,
    QgsProcessingParameterBoolean,
    QgsProcessingParameterNumber,
    QgsProcessingParameterEnum
)
# We import the algorithm used for processing a road.
from .dijkstra_algorithm import dijkstra
# We import mathematical functions needed for the algorithm.
from math import floor, sqrt

# The algorithm class heritates from the algorithm class of QGIS.
# There, it can register different parameter during initialization
# that can be put into variables using "
class ForestRoadNetworkAlgorithm(QgsProcessingAlgorithm):
    """
    Class that described the algorithm, that will be launched
    via the provider, itself launched via initialization of
    the plugin.

    The algorithm takes 4 entries :

    - A cost raster
    - The raster band to use for the cost
    - The layer with the polygons of zones to access
    - The layer with the roads (lines) that they can be connected to
    by the generated roads
    """

    # Constants used to refer to parameters and outputs. They will be
    # used when calling the algorithm from another algorithm, or when
    # calling from the QGIS console.

    INPUT_COST_RASTER = 'INPUT_COST_RASTER'
    INPUT_RASTER_BAND = 'INPUT_RASTER_BAND'
    INPUT_POLYGONS_TO_ACCESS = 'INPUT_POLYGONS_TO_ACCESS'
    INPUT_ROADS_TO_CONNECT_TO = 'INPUT_ROADS_TO_CONNECT_TO'
    # BOOLEAN_OUTPUT_LINEAR_REFERENCE = 'BOOLEAN_OUTPUT_LINEAR_REFERENCE'
    SKIDDING_DISTANCE = 'SKIDDING_DISTANCE'
    METHOD_OF_GENERATION = 'METHOD_OF_GENERATION'
    OUTPUT = 'OUTPUT'

    def initAlgorithm(self, config):
        """
        Here we define the inputs and output of the algorithm, along
        with some other properties. Theses will be asked to the user.
        """
        self.addParameter(
            QgsProcessingParameterRasterLayer(
                self.INPUT_COST_RASTER,
                self.tr('Cost raster layer'),
            )
        )

        self.addParameter(
            QgsProcessingParameterBand(
                self.INPUT_RASTER_BAND,
                self.tr('Cost raster band'),
                0,
                self.INPUT_COST_RASTER,
            )
        )

        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.INPUT_POLYGONS_TO_ACCESS,
                self.tr('Polygons to access via the generated roads'),
                [QgsProcessing.TypeVectorPolygon]
            )
        )

        self.addParameter(
            QgsProcessingParameterFeatureSource(
                self.INPUT_ROADS_TO_CONNECT_TO,
                self.tr('Roads to connect the polygons to access to'),
                [QgsProcessing.TypeVectorLine]
            )
        )

        self.addParameter(
            QgsProcessingParameterNumber(
                self.SKIDDING_DISTANCE,
                self.tr('Skidding distance (in CRS units)'),
                type=QgsProcessingParameterNumber.Double,
                defaultValue=100,
                optional=False,
                minValue=0
            )
        )

        self.addParameter(
            QgsProcessingParameterEnum(
                self.METHOD_OF_GENERATION,
                self.tr('Method of generation of the road network'),
                ['Random', 'Closest first', 'Farthest first']
            )
        )

        self.addParameter(
            QgsProcessingParameterFeatureSink(
                self.OUTPUT,
                self.tr('Output for the forest road network')
            )
        )

    def processAlgorithm(self, parameters, context, feedback):
        """
        Here is where the processing itself takes place.
        """
        cost_raster = self.parameterAsRasterLayer(
            parameters,
            self.INPUT_COST_RASTER,
            context
        )

        cost_raster_band = self.parameterAsInt(
            parameters,
            self.INPUT_RASTER_BAND,
            context
        )

        polygons_to_connect = self.parameterAsVectorLayer(
            parameters,
            self.INPUT_POLYGONS_TO_ACCESS,
            context
        )

        current_roads = self.parameterAsVectorLayer(
            parameters,
            self.INPUT_ROADS_TO_CONNECT_TO,
            context
        )

        skidding_distance = self.parameterAsInt(
            parameters,
            self.SKIDDING_DISTANCE,
            context
        )

        method_of_generation = self.parameterAsString(
            parameters,
            self.METHOD_OF_GENERATION,
            context
        )

        # If source was not found, throw an exception to indicate that the algorithm
        # encountered a fatal error. The exception text can be any string, but in this
        # case we use the pre-built invalidSourceError method to return a standard
        # helper text for when a source cannot be evaluated
        if cost_raster is None:
            raise QgsProcessingException(self.invalidSourceError(parameters, self.INPUT_COST_RASTER))
        if cost_raster_band is None:
            raise QgsProcessingException(self.invalidSourceError(parameters, self.INPUT_RASTER_BAND))
        if polygons_to_connect is None:
            raise QgsProcessingException(self.invalidSourceError(parameters, self.INPUT_START_LAYER))
        if current_roads is None:
            raise QgsProcessingException(self.invalidSourceError(parameters, self.INPUT_START_LAYER))
        if skidding_distance is None:
            raise QgsProcessingException(self.invalidSourceError(parameters, self.INPUT_START_LAYER))
        if method_of_generation is None:
            raise QgsProcessingException(self.invalidSourceError(parameters, self.INPUT_START_LAYER))

        # We try to see if there are divergence between the CRSs of the inputs
        if cost_raster.crs() != polygons_to_connect.sourceCrs() \
                or polygons_to_connect.sourceCrs() != current_roads.sourceCrs():
            raise QgsProcessingException(self.tr("ERROR: The input layers have different CRSs."))

        # We check if the cost raster in indeed numeric
        if cost_raster.rasterType() not in [cost_raster.Multiband, cost_raster.GrayOrUndefined]:
            raise QgsProcessingException(self.tr("ERROR: The input cost raster is not numeric."))

        # We initialize the "sink", an object that will make use able to create an output.
        # First, we create the fields for the attributes of our lines as outputs.
        # They will only have one field :
        sink_fields = MinCostPathHelper.create_fields()
        # We indicate that our output will be a line, stored in WBK format.
        output_geometry_type = QgsWkbTypes.LineString
        # Finally, we create the field object and register the destination ID of it.
        # This sink will be based on the OUTPUT parameter we registered during initialization,
        # will have the fields and the geometry type we just created, and the same CRS as the cost raster.
        (sink, dest_id) = self.parameterAsSink(
            parameters,
            self.OUTPUT,
            context,
            fields=sink_fields,
            geometryType=output_geometry_type,
            crs=cost_raster.crs(),
        )

        # If sink was not created, throw an exception to indicate that the algorithm
        # encountered a fatal error. The exception text can be any string, but in this
        # case we use the pre-built invalidSinkError method to return a standard
        # helper text for when a sink cannot be evaluated
        if sink is None:
            raise QgsProcessingException(self.invalidSinkError(parameters, self.OUTPUT))

        # First of all : We transform the starting polygons into cells on the raster (coordinates
        # in rows and colons).
        polygons_to_reach_features = list(polygons_to_connect.getFeatures())
        # feedback.pushInfo(str(len(start_features)))
        # We make a set of nodes to reach.
        set_of_nodes_to_reach = MinCostPathHelper.features_to_row_cols(feedback, polygons_to_reach_features, cost_raster)
        # If there are no nodes to reach (e.g. all polygons are out of the raster)
        if len(set_of_nodes_to_reach) == 0:
            raise QgsProcessingException(self.tr("ERROR: There is no polygon to reach in this raster. Check if some"
                                                 "polygons are inside the raster."))

        # We do another set concerning the nodes that contains roads to connect to
        roads_to_connect_to_features = list(current_roads.getFeatures())
        # feedback.pushInfo(str(len(end_features)))
        set_of_nodes_to_connect_to = MinCostPathHelper.features_to_row_cols(feedback, roads_to_connect_to_features, cost_raster)
        # If there is no nodes to connect to, throw an exception
        if len(set_of_nodes_to_connect_to) == 0:
            raise QgsProcessingException(self.tr("ERROR: There is no road to connect to in this raster. Check if some"
                                                 "roads are inside the raster."))
        # If some overlap, raise another exception :
        if set_of_nodes_to_reach in set_of_nodes_to_connect_to:
            raise QgsProcessingException(self.tr("ERROR: Some polygons to reach are overlapping with roads to connect to"
                                                 "given this resolution."))
        # feedback.pushInfo(str(start_col_rows))
        # feedback.pushInfo(str(end_col_rows))

        # We put the data of the raster into a variable that we will send to the algorithm.
        block = MinCostPathHelper.get_all_block(cost_raster, cost_raster_band)
        # We transform the raster data into a matrix and check if the matrix contains negative values
        matrix, contains_negative = MinCostPathHelper.block2matrix(block)
        # We display a feedback on the loading of the raster
        feedback.pushInfo(self.tr("The size of cost raster is: %d * %d") % (block.height(), block.width()))

        # If there are negative values in the raster, we make an issue.
        if contains_negative:
            raise QgsProcessingException(self.tr("ERROR: Cost raster contains negative value."))

        # Now, time to launch the algorithm properly !
        feedback.pushInfo(self.tr("Searching least cost path..."))

        # From the algorithm, we get back a minimum cost path on the form of a list of nodes from start to goal,
        # a list of accumulated cost for each step, and the node that was chosen for the ending.
        # FOR TESTING PURPOSES
        start_row_col = random.choice(tuple(set_of_nodes_to_reach))
        end_row_cols = list(set_of_nodes_to_connect_to)
        min_cost_path, costs, selected_end = dijkstra(start_row_col, end_row_cols, matrix, cost_raster, feedback)
        # feedback.pushInfo(str(min_cost_path))

        # If there was a problem, we indicate if it's because the search was cancelled by the user
        # or if there was no end point that could be reached.
        if min_cost_path is None:
            if feedback.isCanceled():
                raise QgsProcessingException(self.tr("ERROR: Search canceled."))
            else:
                raise QgsProcessingException(self.tr("ERROR: The end-point(s) is not reachable from start-point."))
        feedback.setProgress(100)
        feedback.pushInfo(self.tr("Search completed! Saving path..."))

        # Time to save the path as a vector.
        # We take the starting and ending points in our dictionaries as pointXY in QGIS format
        # FOR TESTING PURPOSES
        start_point = MinCostPathHelper._row_col_to_point(min_cost_path[0], cost_raster)
        end_point = MinCostPathHelper._row_col_to_point(min_cost_path[-1], cost_raster)
        # We make a list of Qgs.pointXY from the nodes in our pathlist
        path_points = MinCostPathHelper.create_points_from_path(cost_raster, min_cost_path, start_point, end_point)
        # With the total cost which is the last item in our accumulated cost list,
        # we create the PolyLine that will be returned as a vector.
        total_cost = costs[-1]
        path_feature = MinCostPathHelper.create_path_feature_from_points(path_points, total_cost, sink_fields)

        # Into the sink that serves as our output, we put the PolyLines from the list of lines we created
        # one by one
        sink.addFeature(path_feature, QgsFeatureSink.FastInsert)
        sink.addFeature(path_feature, QgsFeatureSink.FastInsert)
        sink.addFeature(path_feature, QgsFeatureSink.FastInsert)
        # We return our output, that is linked to our sink.
        return {self.OUTPUT: dest_id}

    # Here are different functions used by QGIS to name and define the algorithm
    # to the user.
    def name(self):
        """
        Returns the algorithm name, used for identifying the algorithm. This
        string should be fixed for the algorithm, and must not be localised.
        The name should be unique within each provider. Names should contain
        lowercase alphanumeric characters only and no spaces or other
        formatting characters.
        """
        return 'Forest Road Network creation'

    def displayName(self):
        """
        Returns the translated algorithm name, which should be used for any
        user-visible display of the algorithm name.
        """
        return self.tr(self.name())

    def group(self):
        """
        Returns the name of the group this algorithm belongs to. This string
        should be localised.
        """
        return self.tr(self.groupId())

    def groupId(self):
        """
        Returns the unique ID of the group this algorithm belongs to. This
        string should be fixed for the algorithm, and must not be localised.
        The group id should be unique within each provider. Group id should
        contain lowercase alphanumeric characters only and no spaces or other
        formatting characters.
        """
        # We don't need it right now, as our plugin only have one algorithm
        return ''

    # Function used for translation. Called everytime something needs to be
    # Translated
    def tr(self, string):
        return QCoreApplication.translate('Processing', string)

    def createInstance(self):
        return ForestRoadNetworkAlgorithm()

    def helpUrl(self):
        # No help URL for now; Github of the project could be nice once done.
        return ''

    def shortHelpString(self):
        return self.tr("""
        This algorithm creates a forest road network based on areas to access (polygons) and current roads to connect them to (lines).
        
        **Parameters:**
          
          Please ensure all the input layers have the same CRS.
        
          - Cost raster layer: Numeric raster layer that represents the cost of each spatial unit. It should not contains negative value. Pixel with `NoData` value represent it is unreachable.
         
          - Cost raster band: The input band of the cost raster.
         
          - Polygons to access via the generated roads: Layer that contains the polygons to access.
         
          - Roads to connect the polygons to access to: Layer that contains the roads to connect the polygons to.
          
          - Network generation type: a parameter indicating what type of heuristic is used to generate the network. Random cell order, farther cells from current roads first, closer cells from curent roads first.
          
          - Skidding distance. Maximum distance that a cell can be to not need a road going up to it.
         
        """)

    def shortDescription(self):
        return self.tr('Generate a network of roads to connect forest area to an existing road network.')

    # Path to the icon of the algorithm
    def svgIconPath(self):
        return '.icon.png'

    def tags(self):
        return ['least', 'cost', 'path', 'distance', 'raster', 'analysis', 'road', 'network', 'forest', 'A*', 'dijkstra']

 # Methods to help the algorithm; all static, do not need to initialize an object of this class.
class MinCostPathHelper:

    # Function to transform a given row/column into a QGIS point with a x,y
    # coordinates based on the resolution of the raster layer we're considering
    # (calculated with its extent and number of cells)
    @staticmethod
    def _row_col_to_point(row_col, raster_layer):
        xres = raster_layer.rasterUnitsPerPixelX()
        yres = raster_layer.rasterUnitsPerPixelY()
        extent = raster_layer.dataProvider().extent()

        x = (row_col[1] + 0.5) * xres + extent.xMinimum()
        # There is a dissonance about how I see y axis of the raster
        # and how the program sees it.
        y = (row_col[0] + 0.5) * yres + extent.yMinimum()
        return QgsPointXY(x, y)

    # Method to determine where a given polygon is in the raster
    @staticmethod
    def _polygon_to_row_col(feedback, polygon, raster_layer):
        # We initialize the object to return : a set of nodes, corresponding a tuple of a row
        # and a column in the raster
        listOfNodesInPolygons = set()

        # We get the extent of the raster
        xres = raster_layer.rasterUnitsPerPixelX()
        yres = raster_layer.rasterUnitsPerPixelY()
        extentRaster = raster_layer.dataProvider().extent()
        maxRasterCols = round((extentRaster.xMaximum() - extentRaster.xMinimum()) / xres)
        maxRasterRows = round((extentRaster.yMaximum() - extentRaster.yMinimum()) / yres)

        # We get the extent of the polygon
        extentPolygon = QgsGeometry.fromPolygonXY(polygon).boundingBox()

        # We traduce this extent into limits of columns and rows on the raster
        rowMin = floor((extentPolygon.yMinimum() - extentRaster.yMinimum()) / yres)
        rowMax = floor((extentPolygon.yMaximum() - extentRaster.yMinimum()) / yres)
        colMin = floor((extentPolygon.xMinimum() - extentRaster.xMinimum()) / xres)
        colMax = floor((extentPolygon.xMaximum() - extentRaster.xMinimum()) / xres)
        feedback.pushInfo("rowMin : " + str(rowMin))
        feedback.pushInfo("rowMax : " + str(rowMax))
        feedback.pushInfo("colMin : " + str(colMin))
        feedback.pushInfo("colMax : " + str(colMax))

        # If one of these values is not in the range of the raster, then we
        # restrict it to column and rows that are inside of it.
        if rowMin < 0: rowMin = 0
        if rowMax > maxRasterRows: rowMax = maxRasterRows
        if colMin < 0: colMin = 0
        if colMax > maxRasterCols: colMax = maxRasterCols
        # If the polygon is out of range, then we return an empty set
        if rowMin > maxRasterRows or colMin > maxRasterCols or rowMax < 0 or colMax < 0:
            return set()

        # If not, we treat the select range of the raster.
        # For each column of our range,
        for col in range(colMin, colMax):
            # For each row of our range,
            feedback.pushInfo("Checking col " + str(col))
            for row in range(rowMin, rowMax):
                feedback.pushInfo("Checking row " + str(row))
                # We make a ceintroid of the row/column of the raster
                centroid = MinCostPathHelper._row_col_to_point((row, col), raster_layer)
                feedback.pushInfo("Centroid infos : " + str(QgsGeometry.fromPointXY(centroid)))

                # We check if the centroid is in the polygon

                isInPolygon = QgsGeometry.fromPolygonXY(polygon).contains(centroid)
                feedback.pushInfo("Polygon infos : " + str(QgsGeometry.fromPolygonXY(polygon).wkbType()))
                feedback.pushInfo("Polygon infos : " + str(QgsGeometry.fromPolygonXY(polygon)))

                # If it is, we add the centroid to a set with the form of a node (tuple (row, column))
                if isInPolygon:
                    listOfNodesInPolygons.add((row, col))
                    feedback.pushInfo("Polygon contained the centroid !")
                else:
                    feedback.pushInfo("Polygon did not contained centroid.")
                # if not, we continue the loops

        # When the loops are done, we return the set of nodes that have been taken into account
        return listOfNodesInPolygons

    # Method to determine where a given line is in the raster
    @staticmethod
    def _line_to_row_col(line, raster_layer):
        # We initialize the object to return : a set of nodes, corresponding a tuple of a row
        # and a column in the raster
        listOfNodesInPolygons = set()

        # We get the extent of the raster
        xres = raster_layer.rasterUnitsPerPixelX()
        yres = raster_layer.rasterUnitsPerPixelY()
        extentRaster = raster_layer.dataProvider().extent()
        maxRasterCols = round((extentRaster.xMaximum() - extentRaster.xMinimum()) / xres)
        maxRasterRows = round((extentRaster.yMaximum() - extentRaster.yMinimum()) / yres)

        # We get the extent of the line
        extentLine = QgsGeometry.fromPolylineXY(line).boundingBox()

        # We traduce this extent into limits of colomns and rows on the raster
        rowMin = floor((extentLine.yMinimum() - extentRaster.yMinimum()) / yres)
        rowMax = floor((extentLine.yMaximum() - extentRaster.yMinimum()) / yres)
        colMin = floor((extentLine.xMinimum() - extentRaster.xMinimum()) / xres)
        colMax = floor((extentLine.xMaximum() - extentRaster.xMinimum()) / xres)

        # If one of these values is not in the range of the raster, then we
        # restrict it to column and rows that are inside of it.
        if rowMin < 0: rowMin = 0
        if rowMax > maxRasterRows: rowMax = maxRasterRows
        if colMin < 0: colMin = 0
        if colMax > maxRasterCols: colMax = maxRasterCols
        # If the polygon is out of range, then we return an empty set
        if rowMin > maxRasterRows or colMin > maxRasterCols or rowMax < 0 or colMax < 0:
            return set()

        # If not, we treat the select range of the raster.
        # For each column of our range,
        for col in range(colMin, colMax):
            # For each row of our range,
            for row in range(rowMin, rowMax):
                # We make square polygon around the cell
                centroid = MinCostPathHelper._row_col_to_point((row, col), raster_layer)
                halfACellX = 0.5 * raster_layer.rasterUnitsPerPixelX()
                halfACellY = 0.5 * raster_layer.rasterUnitsPerPixelY()
                square = QgsGeometry.fromPolygonXY([[QgsPointXY(centroid.x() - halfACellX,centroid.y() - halfACellY),
                                                   QgsPointXY(centroid.x() + halfACellX,centroid.y() - halfACellY),
                                                   QgsPointXY(centroid.x() + halfACellX,centroid.y() + halfACellY),
                                                   QgsPointXY(centroid.x() - halfACellX,centroid.y() + halfACellY)]])

                # We check if the centroid is in the polygon
                intersectWithSquare = square.intersects(QgsGeometry.fromPolylineXY(line))

                # If it is, we add the centroid to a set with the form of a node (tuple (row, column))
                if intersectWithSquare:
                    listOfNodesInPolygons.add((row, col))
                # if not, we continue the loops

        # When the loops are done, we return the set of nodes that have been taken into account
        return listOfNodesInPolygons

    # Function to return a list of Qgs.pointXY. Each point is made based on the center of the node
    # that we get from the path list.
    # At the end, we put the precise coordinates of the starting/ending nodes that were given by
    # the user at the start.
    @staticmethod
    def create_points_from_path(cost_raster, min_cost_path, start_point, end_point):
        path_points = list(
            map(lambda row_col: MinCostPathHelper._row_col_to_point(row_col, cost_raster), min_cost_path))
        path_points[0].setX(start_point.x())
        path_points[0].setY(start_point.y())
        path_points[-1].setX(end_point.x())
        path_points[-1].setY(end_point.y())
        return path_points

    @staticmethod
    def create_fields():
        # Create the field of "total cost" by indicating name, type, typeName, lenght and precision (decimals in that case)
        cost_field = QgsField("total cost", QVariant.Double, "double", 10, 3)
        # Then, we create a container of multiple fields
        fields = QgsFields()
        fields.append(cost_field)
        # We return the container with our field.
        return fields

    # Function to create a polyline with the list of qgs.pointXY
    @staticmethod
    def create_path_feature_from_points(path_points, total_cost, fields):
        polyline = QgsGeometry.fromPolylineXY(path_points)
        feature = QgsFeature(fields)
        # feature.setAttribute(0, 1) # id
        cost_index = feature.fieldNameIndex("total cost")
        feature.setAttribute(cost_index, total_cost)  # cost
        feature.setGeometry(polyline)
        return feature

    # Method to transform given features into a set of
    # nodes (row + column) on the raster.
    @staticmethod
    def features_to_row_cols(feedback, given_features, raster_layer):

        row_cols = set()
        extent = raster_layer.dataProvider().extent()
        # if extent.isNull() or extent.isEmpty:
        #     return list(col_rows)

        for given_feature in given_features:
            if given_feature.hasGeometry():

                given_feature = given_feature.geometry()
                if given_feature.wkbType() == QgsWkbTypes.MultiPolygon:
                    feedback.pushInfo("MultiPolygon detected !")
                    multi_polygon = given_feature.asMultiPolygon()
                    for polygon in multi_polygon:
                        row_cols_for_this_polygon = MinCostPathHelper._polygon_to_row_col(feedback, polygon, raster_layer)
                        feedback.pushInfo("Polygon is in " + str(len(row_cols_for_this_polygon)) + " cells !")
                        row_cols.update(row_cols_for_this_polygon)

                elif given_feature.wkbType() == QgsWkbTypes.Polygon:
                    feedback.pushInfo("Polygon detected !")
                    given_feature = given_feature.asPolygon()
                    row_cols_for_this_polygon = MinCostPathHelper._polygon_to_row_col(feedback, given_feature, raster_layer)
                    feedback.pushInfo("Polygon is in " + str(len(row_cols_for_this_polygon)) + " cells !")
                    row_cols.update(row_cols_for_this_polygon)

                elif given_feature.wkbType() == QgsWkbTypes.MultiLineString:
                    feedback.pushInfo("MultiLineString detected !")
                    multi_line = given_feature.asMultiPolyline()
                    for line in multi_line:
                        row_cols_for_this_line = MinCostPathHelper._line_to_row_col(line, raster_layer)
                        feedback.pushInfo("Line is in " + str(len(row_cols_for_this_line)) + " cells !")
                        row_cols.update(row_cols_for_this_line)

                elif given_feature.wkbType() == QgsWkbTypes.LineString:
                    feedback.pushInfo("Line detected !")
                    given_feature = given_feature.asPolyline()
                    row_cols_for_this_line = MinCostPathHelper._line_to_row_col(given_feature, raster_layer)
                    feedback.pushInfo("Line is in " + str(len(row_cols_for_this_line)) + " cells !")
                    row_cols.update(row_cols_for_this_line)

        return row_cols

    @staticmethod
    def get_all_block(raster_layer, band_num):
        provider = raster_layer.dataProvider()
        extent = provider.extent()

        xres = raster_layer.rasterUnitsPerPixelX()
        yres = raster_layer.rasterUnitsPerPixelY()
        width = floor((extent.xMaximum() - extent.xMinimum()) / xres)
        height = floor((extent.yMaximum() - extent.yMinimum()) / yres)
        return provider.block(band_num, extent, width, height)

    @staticmethod
    def block2matrix(block):
        contains_negative = False
        matrix = [[None if block.isNoData(i, j) else block.value(i, j) for j in range(block.width())]
                  for i in range(block.height())]

        for l in matrix:
            for v in l:
                if v is not None:
                    if v < 0:
                        contains_negative = True

        return matrix, contains_negative
