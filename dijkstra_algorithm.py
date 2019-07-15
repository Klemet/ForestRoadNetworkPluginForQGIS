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
 This script describes the A* algorithm used to find the least cost path between two given
 node, both described by a row and a column of the cost raster.
"""


from math import sqrt
import queue
import random
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
    QgsProcessingParameterBoolean
)


def dijkstra(start_row_col, end_row_cols, block, raster_layer, feedback=None):
    sqrt2 = sqrt(2)

    # The grid class is used to both contain the matrix of the values
    # of the cost raster, but also to have usefull function for the
    # pathfinding algorithm used here.
    class Grid:
        def __init__(self, matrix):
            self.map = matrix
            # h is the height of the matrix/raster
            self.h = len(matrix)
            # w is the width of the matrix/raster
            self.w = len(matrix[0])

        # Function to test if a coordinate is in the bounds of the matrix/raster
        # In the code, self.h is used to invert the y axis of the coordinates of rows
        # because I used cartesian coordinates, and the raster have raster coordinates
        # (inverted y axis). Self.h is diminished by one because it starts at 1, while
        # the rows start at 0.
        def _in_bounds(self, id):
            row, col = id
            return 0 <= col < self.w and 0 <= row < (self.h-1)

        # Function to test if the raster value of this coordinate is not empty (has a cost to pass it)
        def _passable(self, id):
            row, col = id
            return self.map[(self.h-1)-row][col] is not None

        # Function to test a coordinate is both in bound and passable
        def is_valid(self, id):
            return self._in_bounds(id) and self._passable(id)

        # Function to get the eight neighbours of a given cell. They are filtered to get only the valid ones.
        def neighbors(self, id):
            row, col = id
            results = [(row + 1, col), (row, col - 1), (row - 1, col), (row, col + 1),
                       (row + 1, col - 1), (row + 1, col + 1), (row - 1, col - 1), (row - 1, col + 1)]
            results = filter(self.is_valid, results)
            return results

        # Static function to calculate the manhattan distance between two cells.
        @staticmethod
        def manhattan_distance(id1, id2):
            x1, y1 = id1
            x2, y2 = id2
            return abs(x1 - x2) + abs(y1 - y2)

        # Function to calculate the minimum manhattan distance between nodes that have been explored yet and the ending
        # nodes for feedback purposes.
        def min_manhattan(self, curr_node, end_nodes):
            return min(map(lambda node: self.manhattan_distance(curr_node, node), end_nodes))

        # Function to get the cost associated for passing from a node to another (current, next)
        def simple_cost(self, cur, nex):
            # Coordinates of current
            crow, ccol = cur
            # Coordinates of next
            nrow, ncol = nex
            # Get the value associated with the current node
            currV = self.map[(self.h-1) - crow][ccol]
            # Get the value associated with the next node
            offsetV = self.map[(self.h-1) - nrow][ncol]
            # Check if the nodes are horizontal/vertical neighbours, or diagonals.
            # Adjust the cost to go from one to the other accordingly.
            if ccol == ncol or crow == nrow:
                return (currV + offsetV) / 2
            else:
                return sqrt2 * (currV + offsetV) / 2

    # We create the grid object containing the values of the cost raster
    grid = Grid(block)
    # We create a set of nodes to reach (multiple goal possible)
    end_row_cols = set(end_row_cols)

    # We create a priority Queue which contains the nodes that are opened but
    # not closed (see functioning of dijkstra algorithm; nodes are opened to
    # initialize their remaining distance, then closed)
    frontier = queue.PriorityQueue()
    # In the frontier, we put tuples containing distance from start, and the node)
    frontier.put((0, start_row_col))
    # We initialize a dictionary of predecessors. For a given node, we'll know
    # which node is his predecessor.
    came_from = {}
    # A dictionary to know what is the distance from a given node to the start.
    cost_so_far = {}

    # If the starting node is invalid, we return nothing
    if not grid.is_valid(start_row_col):
        return None, None, None
    # If the starting node is also an ending node, we return nothing
    if start_row_col in end_row_cols:
        # feedback.pushInfo("Starting node seem to coincide with a ending node")
        return None, None, None

    # We initialize the beginning of the loop
    came_from[start_row_col] = None
    cost_so_far[start_row_col] = 0
    current_node = None
    # feedback.pushInfo("Dijkstra loop initialized.")

    # We launch the loop. It will end when there are no more cell to
    # check (impossible to reach an end node), or will be broken when
    # a end node is reached
    while not frontier.empty():
        # We get the node with the smallest distance to start
        # First node will be the start node, of course
        # By using this function, the current node is removed
        # from the frontier.
        current_cost, current_node = frontier.get()

        # update the progress bar if feedback is activated.
        if feedback:
            # The algorithm is canceled if users told it to feedback.
            if feedback.isCanceled():
                return None, None, None

        # We break the loop if the current node is a goal to reach
        if current_node in end_row_cols:
            break

        # If not, we look at each neighbour of the node
        for nex in grid.neighbors(current_node):
            # We calculate the distance to goal from this neighbour (which is the one
            # from the current node + the move from current node to neighbour)
            new_cost = cost_so_far[current_node] + grid.simple_cost(current_node, nex)
            # If the neighbour is not in the dictionary of opened nodes, or if
            # the cost of passing by this neighbour is cheaper than the previous
            # predecessor that this node had
            if nex not in cost_so_far or new_cost < cost_so_far[nex]:
                # We put the current node as predecessor of this neighbour,
                # we put the neighbour in the frontier, and we register
                # the cost to start
                cost_so_far[nex] = new_cost
                frontier.put((new_cost, nex))
                came_from[nex] = current_node

    # When the loop ends, if we did indeed found an end goal :
    if current_node in end_row_cols:
        # We calculate the cost from this end goal to the start
        end_node = current_node
        # We initialize the path object that we are going to return : it is a list.
        # We also make a list of costs.
        path = []
        costs = []
        # From the end node, we add the current node,
        # we register the cost to go to it from the goal,
        # and we take the predecessor as the current node.
        # We stop when there are no more predecessors
        # (meaning current node = starting node)
        while current_node is not None:
            path.append(current_node)
            costs.append(cost_so_far[current_node])
            current_node = came_from[current_node]

        # We reverse the order of the list to start from the start
        path.reverse()
        costs.reverse()
        # We return the path
        return path, costs, end_node
    # If we did not reached a end goal, it was unreachable.
    # We return nothing.
    else:
        return None, None, None
