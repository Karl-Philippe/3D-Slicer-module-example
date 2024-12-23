import os
import unittest
import vtk
import qt
import ctk
import slicer
from slicer.ScriptedLoadableModule import *
import logging

#
# LineProfileTP
#


class LineProfileTP(ScriptedLoadableModule):
    """Uses ScriptedLoadableModule base class, available at:
    https://github.com/Slicer/Slicer/blob/main/Base/Python/slicer/ScriptedLoadableModule.py
    """

    def __init__(self, parent):
        ScriptedLoadableModule.__init__(self, parent)
        self.parent.title = "Line Profile TP"
        self.parent.categories = ["Quantification"]
        self.parent.dependencies = []
        parent.contributors = ["Andras Lasso (PerkLab)"]
        self.parent.helpText = """
This module computes intensity profile of a volume along a line line.
"""
        self.parent.helpText += self.getDefaultModuleDocumentationLink()
        self.parent.acknowledgementText = """
This file was originally developed by Andras Lasso (PerkLab)  and was partially funded by CCO ACRU.
"""  # replace with organization, grant and thanks.

#
# LineProfileTPWidget
#


class LineProfileTPWidget(ScriptedLoadableModuleWidget):
    """Uses ScriptedLoadableModuleWidget base class, available at:
    https://github.com/Slicer/Slicer/blob/main/Base/Python/slicer/ScriptedLoadableModule.py
    """

    def setup(self):
        ScriptedLoadableModuleWidget.setup(self)

        self.logic = LineProfileTPLogic()
        uiWidget = slicer.util.loadUI(self.resourcePath("UI/LineProfileTP.ui"))
        self.layout.addWidget(uiWidget)
        self._widgets = slicer.util.childWidgetVariables(uiWidget)

        # Parameters widgets

        self._widgets.inputLineWidget.tableWidget().setVisible(False)
        self._widgets.inputLineWidget.setDefaultNodeColor(
            qt.QColor().fromRgbF(1, 1, 0))

        self.inputLineSelector = self._widgets.inputLineWidget.markupsSelectorComboBox()
        self.inputLineSelector.nodeTypes = [
            "vtkMRMLMarkupsLineNode", "vtkMRMLMarkupsCurveNode"]
        self.inputLineSelector.selectNodeUponCreation = True
        self.inputLineSelector.addEnabled = True
        self.inputLineSelector.removeEnabled = True
        self.inputLineSelector.noneEnabled = False
        self.inputLineSelector.showHidden = False

        # Apply button

        self._widgets.applyButton.enabled = False
        self._widgets.applyButton.checkable = False
        self._widgets.applyButton.checkBoxControlsButtonToggleState = True

        # Connect widgets

        uiWidget.setMRMLScene(slicer.mrmlScene)

        self._widgets.applyButton.connect('clicked(bool)', self.onApplyButton)
        self._widgets.applyButton.connect(
            'checkBoxToggled(bool)', self.onApplyButtonToggled)
        self._widgets.inputVolumeSelector.connect(
            "currentNodeChanged(vtkMRMLNode*)", self.onSelectNode)
        self.inputLineSelector.connect(
            "currentNodeChanged(vtkMRMLNode*)", self.onSelectNode)
        self._widgets.outputPlotSeriesSelector.connect(
            "currentNodeChanged(vtkMRMLNode*)", self.onSelectNode)
        self._widgets.outputTableSelector.connect(
            "currentNodeChanged(vtkMRMLNode*)", self.onSelectNode)
        self._widgets.outputPeaksTableSelector.connect(
            "currentNodeChanged(vtkMRMLNode*)", self.onSelectNode)
        self._widgets.lineResolutionSliderWidget.connect(
            "valueChanged(double)", self.onSetLineResolution)
        self._widgets.plotProportionalDistanceCheckBox.connect(
            "clicked()", self.onProportionalDistance)
        self._widgets.peakMinimumWidthSpinBox.connect(
            "valueChanged(double)", self.onSetPeakMinimumWidth)
        self._widgets.heightPercentageForWidthMeasurementSpinBox.connect(
            "valueChanged(double)", self.onSetHeightPercentageForWidthMeasurement)
        self._widgets.peakIsMaximumCheckBox.connect(
            "toggled(bool)", self.onSetPeakIsMaximum)

        # Refresh Apply button state
        self.onSelectNode()

    def cleanup(self):
        self.logic.setEnableAutoUpdate(False)

    def onSelectNode(self):
        self._widgets.applyButton.enabled = self._widgets.inputVolumeSelector.currentNode(
        ) and self.inputLineSelector.currentNode()
        self.logic.setInputVolumeNode(
            self._widgets.inputVolumeSelector.currentNode())
        self.logic.setInputLineNode(self.inputLineSelector.currentNode())
        self.logic.setOutputTableNode(
            self._widgets.outputTableSelector.currentNode())
        self.logic.setOutputPeaksTableNode(
            self._widgets.outputPeaksTableSelector.currentNode())
        self.logic.setOutputPlotSeriesNode(
            self._widgets.outputPlotSeriesSelector.currentNode())

    def onSetLineResolution(self, resolution):
        lineResolution = int(self._widgets.lineResolutionSliderWidget.value)
        self.logic.lineResolution = lineResolution

    def createOutputNodes(self):
        if not self._widgets.outputTableSelector.currentNode():
            outputTableNode = slicer.mrmlScene.AddNewNodeByClass(
                "vtkMRMLTableNode")
            self._widgets.outputTableSelector.setCurrentNode(outputTableNode)
        if not self._widgets.outputPlotSeriesSelector.currentNode():
            outputPlotSeriesNode = slicer.mrmlScene.AddNewNodeByClass(
                "vtkMRMLPlotSeriesNode")
            self._widgets.outputPlotSeriesSelector.setCurrentNode(
                outputPlotSeriesNode)

    def onApplyButton(self):
        self.createOutputNodes()
        self.logic.update()

    def onApplyButtonToggled(self, toggle):
        if toggle:
            self.createOutputNodes()
        self.logic.setEnableAutoUpdate(toggle)

    def onProportionalDistance(self):
        self.logic.setPlotProportionalDistance(
            self._widgets.plotProportionalDistanceCheckBox.checked)

    def onSetPeakMinimumWidth(self, value):
        self.logic.setPeakMinimumWidth(value)

    def onSetHeightPercentageForWidthMeasurement(self, value):
        self.logic.setHeightPercentageForWidthMeasurement(value)

    def onSetPeakIsMaximum(self, toggle):
        self.logic.setPeakIsMaximum(toggle)

#
# LineProfileTPLogic
#


class LineProfileTPLogic(ScriptedLoadableModuleLogic):
    """This class should implement all the actual
    computation done by your module.  The interface
    should be such that other python code can import
    this class and make use of the functionality without
    requiring an instance of the Widget.
    Uses ScriptedLoadableModuleLogic base class, available at:
    https://github.com/Slicer/Slicer/blob/main/Base/Python/slicer/ScriptedLoadableModule.py
    """

    def __init__(self):
        self.inputVolumeNode = None
        self.inputLineNode = None
        self.lineObservation = None  # pair of line object and observation ID
        self.lineResolution = 100
        self.outputPlotSeriesNode = None
        self.outputTableNode = None
        self.outputPeaksTableNode = None
        self.peakMinimumWidth = 1.0
        self.heightPercentageForWidthMeasurement = 50
        self.peakIsMaximum = True
        self.plotChartNode = None
        self.plotProportionalDistance = False

    def __del__(self):
        self.setEnableAutoUpdate(False)

    def setInputVolumeNode(self, volumeNode):
        if self.inputVolumeNode == volumeNode:
            return
        self.inputVolumeNode = volumeNode
        if self.getEnableAutoUpdate():
            self.update()

    def setInputLineNode(self, lineNode):
        if self.inputLineNode == lineNode:
            return
        self.inputLineNode = lineNode
        if self.getEnableAutoUpdate():
            self.setEnableAutoUpdate(False)  # remove old observers
            self.setEnableAutoUpdate(True)  # add new observers
            self.update()

    def setPlotProportionalDistance(self, proportional):
        if self.plotProportionalDistance == proportional:
            return
        self.plotProportionalDistance = proportional
        if self.getEnableAutoUpdate():
            self.update()

    def setPeakMinimumWidth(self, peakMinimumWidth):
        if self.peakMinimumWidth == peakMinimumWidth:
            return
        self.peakMinimumWidth = peakMinimumWidth
        if self.getEnableAutoUpdate():
            self.update()

    def setHeightPercentageForWidthMeasurement(self, heightPercentageForWidthMeasurement):
        if self.heightPercentageForWidthMeasurement == heightPercentageForWidthMeasurement:
            return
        self.heightPercentageForWidthMeasurement = heightPercentageForWidthMeasurement
        if self.getEnableAutoUpdate():
            self.update()

    def setPeakIsMaximum(self, peakIsMaximum):
        if self.peakIsMaximum == peakIsMaximum:
            return
        self.peakIsMaximum = peakIsMaximum
        if self.getEnableAutoUpdate():
            self.update()

    def setOutputTableNode(self, tableNode):
        if self.outputTableNode == tableNode:
            return
        self.outputTableNode = tableNode
        if self.getEnableAutoUpdate():
            self.update()

    def setOutputPeaksTableNode(self, tableNode):
        if self.outputPeaksTableNode == tableNode:
            return
        self.outputPeaksTableNode = tableNode
        if self.getEnableAutoUpdate():
            self.update()

    def setOutputPlotSeriesNode(self, plotSeriesNode):
        if self.outputPlotSeriesNode == plotSeriesNode:
            return
        self.outputPlotSeriesNode = plotSeriesNode
        if self.getEnableAutoUpdate():
            self.update()

    def update(self):
        self.updateOutputTable(
            self.inputVolumeNode, self.inputLineNode, self.outputTableNode, self.lineResolution)
        if self.outputPeaksTableNode:
            self.updateOutputPeaksTable(self.outputPeaksTableNode, self.outputTableNode,
                                        self.peakMinimumWidth, self.heightPercentageForWidthMeasurement, self.peakIsMaximum)
        self.updatePlot(self.outputPlotSeriesNode,
                        self.outputTableNode, self.inputVolumeNode.GetName())
        self.showPlot()

    def getEnableAutoUpdate(self):
        return self.lineObservation is not None

    def setEnableAutoUpdate(self, toggle):
        if self.lineObservation:
            self.lineObservation[0].RemoveObserver(self.lineObservation[1])
            self.lineObservation = None
        if toggle and (self.inputLineNode is not None):
            self.lineObservation = [self.inputLineNode,
                                    self.inputLineNode.AddObserver(slicer.vtkMRMLMarkupsNode.PointModifiedEvent, self.onLineModified)]

    def onLineModified(self, caller=None, event=None):
        self.update()

    def getArrayFromTable(self, outputTable, arrayName):
        if outputTable is None:
            return None
        distanceArray = outputTable.GetTable().GetColumnByName(arrayName)
        if distanceArray:
            return distanceArray
        newArray = vtk.vtkDoubleArray()
        newArray.SetName(arrayName)
        outputTable.GetTable().AddColumn(newArray)
        return newArray

    def updateOutputTable(self, inputVolume, inputCurve, outputTable, lineResolution):
        if inputCurve is None or inputVolume is None or outputTable is None:
            return
        if inputCurve.GetNumberOfDefinedControlPoints() < 2:
            outputTable.GetTable().SetNumberOfRows(0)
            return

        curvePoints_RAS = inputCurve.GetCurvePointsWorld()
        closedCurve = inputCurve.IsA('vtkMRMLClosedCurveNode')
        curveLengthMm = slicer.vtkMRMLMarkupsCurveNode.GetCurveLength(
            curvePoints_RAS, closedCurve)

        # Need to get the start/end point of the line in the IJK coordinate system
        # as VTK filters cannot take into account direction cosines
        # We transform the curve points from RAS coordinate system (instead of directly from the inputCurve coordinate system)
        # to make sure the curve is transformed to RAS exactly the same way as it is done for display.
        inputVolumeToIJK = vtk.vtkMatrix4x4()
        inputVolume.GetRASToIJKMatrix(inputVolumeToIJK)
        rasToInputVolumeTransform = vtk.vtkGeneralTransform()
        slicer.vtkMRMLTransformNode.GetTransformBetweenNodes(
            None, inputVolume.GetParentTransformNode(), rasToInputVolumeTransform)
        # rasToIJKTransform = inputVolumeToIJK * rasToInputVolumeTransform
        rasToIJKTransform = vtk.vtkGeneralTransform()
        rasToIJKTransform.Concatenate(inputVolumeToIJK)
        rasToIJKTransform.Concatenate(rasToInputVolumeTransform)

        curvePoly_RAS = vtk.vtkPolyData()
        curvePoly_RAS.SetPoints(curvePoints_RAS)

        transformRasToIjk = vtk.vtkTransformPolyDataFilter()
        transformRasToIjk.SetInputData(curvePoly_RAS)
        transformRasToIjk.SetTransform(rasToIJKTransform)
        transformRasToIjk.Update()
        curvePoly_IJK = transformRasToIjk.GetOutput()
        curvePoints_IJK = curvePoly_IJK.GetPoints()

        if curvePoints_IJK.GetNumberOfPoints() < 2:
            # We checked before that there are at least two control points, so it should not happen
            raise ValueError()

        startPointIndex = 0
        endPointIndex = curvePoints_IJK.GetNumberOfPoints() - 1
        lineStartPoint_IJK = curvePoints_IJK.GetPoint(startPointIndex)
        lineEndPoint_IJK = curvePoints_IJK.GetPoint(endPointIndex)

        # Special case: single-slice volume
        # vtkProbeFilter treats vtkImageData as a general data set and it considers its bounds to end
        # in the middle of edge voxels. This makes single-slice volumes to have zero thickness, which
        # can be easily missed by a line that that is drawn on the plane (e.g., they happen to be
        # extremely on the same side of the plane, very slightly off, due to runding errors).
        # We move the start/end points very close to the plane and force them to be on opposite sides of the plane.
        dims = inputVolume.GetImageData().GetDimensions()
        for axisIndex in range(3):
            if dims[axisIndex] == 1:
                if abs(lineStartPoint_IJK[axisIndex]) < 0.5 and abs(lineEndPoint_IJK[axisIndex]) < 0.5:
                    # both points are inside the volume plane
                    # keep their distance the same (to keep the overall length of the line he same)
                    # but make sure the points are on the opposite side of the plane (to ensure probe filter
                    # considers the line crossing the image plane)
                    pointDistance = max(
                        abs(lineStartPoint_IJK[axisIndex]-lineEndPoint_IJK[axisIndex]), 1e-6)
                    lineStartPoint_IJK[axisIndex] = -0.5 * pointDistance
                    lineEndPoint_IJK[axisIndex] = 0.5 * pointDistance
                    curvePoints_IJK.SetPoint(
                        startPointIndex, lineStartPoint_IJK)
                    curvePoints_IJK.SetPoint(endPointIndex, lineEndPoint_IJK)

        sampledCurvePoints_IJK = vtk.vtkPoints()
        samplingDistance = curveLengthMm / lineResolution
        slicer.vtkMRMLMarkupsCurveNode.ResamplePoints(
            curvePoints_IJK, sampledCurvePoints_IJK, samplingDistance, closedCurve)

        sampledCurvePoly_IJK = vtk.vtkPolyData()
        sampledCurvePoly_IJK.SetPoints(sampledCurvePoints_IJK)

        probeFilter = vtk.vtkProbeFilter()
        probeFilter.SetInputData(sampledCurvePoly_IJK)
        probeFilter.SetSourceData(inputVolume.GetImageData())
        probeFilter.ComputeToleranceOff()
        probeFilter.Update()

        probedPoints = probeFilter.GetOutput()

        # Create arrays of data
        distanceArray = self.getArrayFromTable(
            outputTable, DISTANCE_ARRAY_NAME)
        relativeDistanceArray = self.getArrayFromTable(
            outputTable, PROPORTIONAL_DISTANCE_ARRAY_NAME)
        intensityArray = self.getArrayFromTable(
            outputTable, INTENSITY_ARRAY_NAME)
        outputTable.GetTable().SetNumberOfRows(probedPoints.GetNumberOfPoints())
        x = range(0, probedPoints.GetNumberOfPoints())
        xStep = curveLengthMm/(probedPoints.GetNumberOfPoints()-1)
        probedPointScalars = probedPoints.GetPointData().GetScalars()
        xLength = x[len(x) - 1] * xStep
        for i in range(len(x)):
            distanceArray.SetValue(i, x[i]*xStep)
            relativeDistanceArray.SetValue(i, (x[i]*xStep / xLength) * 100)
            intensityArray.SetValue(i, probedPointScalars.GetTuple(i)[0])
        distanceArray.Modified()
        relativeDistanceArray.Modified()
        intensityArray.Modified()
        outputTable.GetTable().Modified()

    def updateOutputPeaksTable(self, outputPeaksTable, intensitiesTable, peakMinimumWidth=None, heightPercentageForWidthMeasurement=50, peakIsMaximum=True):
        if outputPeaksTable is None or intensitiesTable is None:
            return
        if intensitiesTable.GetTable().GetNumberOfRows() == 0:
            outputPeaksTable.GetTable().SetNumberOfRows(0)
            return

        intensityArray = self.getArrayFromTable(
            intensitiesTable, INTENSITY_ARRAY_NAME)

        # Create output arrays
        peakPositionArray = self.getArrayFromTable(
            outputPeaksTable, DISTANCE_ARRAY_NAME)
        peakIntensityArray = self.getArrayFromTable(
            outputPeaksTable, INTENSITY_ARRAY_NAME)
        peakHeightArray = self.getArrayFromTable(
            outputPeaksTable, PEAK_HEIGHT_ARRAY_NAME)
        peakWidthArray = self.getArrayFromTable(
            outputPeaksTable, PEAK_WIDTH_ARRAY_NAME)
        peakStartArray = self.getArrayFromTable(
            outputPeaksTable, PEAK_START_ARRAY_NAME)
        peakEndArray = self.getArrayFromTable(
            outputPeaksTable, PEAK_END_ARRAY_NAME)

        # Ensure that the intensities are equally sampled (it may not be evenly sample if closed curve)
        from scipy.signal import resample, find_peaks, peak_widths
        distances_input = slicer.util.arrayFromTableColumn(
            intensitiesTable, DISTANCE_ARRAY_NAME)
        intensities_input = slicer.util.arrayFromTableColumn(
            intensitiesTable, INTENSITY_ARRAY_NAME)
        sample_count = len(distances_input) * 10
        intensities, distances = resample(
            intensities_input, sample_count, distances_input)

        # Compute peak physical width from indices
        start = distances[0]
        scale = distances[1] - distances[0]

        # Find peaks and get their widths
        intensityMultiplier = 1.0 if peakIsMaximum else -1.0
        peakIndices, _ = find_peaks(
            intensityMultiplier * intensities, width=peakMinimumWidth / scale)
        relativeHeight = 1.0 - (heightPercentageForWidthMeasurement / 100)
        peakWidthIndices, peakHeights, peakStartIndices, peakEndIndices = peak_widths(
            intensityMultiplier * intensities, peakIndices, rel_height=relativeHeight)
        peakHeights *= intensityMultiplier

        outputPeaksTable.GetTable().SetNumberOfRows(len(peakIndices))

        for peak in range(len(peakIndices)):
            peakPositionArray.SetValue(peak, start + scale * peakIndices[peak])
            peakIntensity = intensities[peakIndices[peak]]
            peakIntensityArray.SetValue(peak, peakIntensity)
            # total peak height is computed from base to tip
            peakHeightArray.SetValue(
                peak, (peakIntensity - peakHeights[peak]) / heightPercentageForWidthMeasurement)
            peakWidthArray.SetValue(peak, scale * peakWidthIndices[peak])
            peakStartArray.SetValue(
                peak, start + scale * peakStartIndices[peak])
            peakEndArray.SetValue(peak, start + scale * peakEndIndices[peak])

        peakPositionArray.Modified()
        peakIntensityArray.Modified()
        peakWidthArray.Modified()
        peakHeightArray.Modified()
        peakStartArray.Modified()
        peakEndArray.Modified()
        outputPeaksTable.GetTable().Modified()

    def updatePlot(self, outputPlotSeries, outputTable, name=None):
        if outputPlotSeries is None or outputTable is None:
            return

        # Create plot
        if name:
            outputPlotSeries.SetName(name)
        outputPlotSeries.SetAndObserveTableNodeID(outputTable.GetID())
        if self.plotProportionalDistance:
            outputPlotSeries.SetXColumnName(PROPORTIONAL_DISTANCE_ARRAY_NAME)
        else:
            outputPlotSeries.SetXColumnName(DISTANCE_ARRAY_NAME)
        outputPlotSeries.SetYColumnName(INTENSITY_ARRAY_NAME)
        outputPlotSeries.SetPlotType(
            slicer.vtkMRMLPlotSeriesNode.PlotTypeScatter)
        outputPlotSeries.SetMarkerStyle(
            slicer.vtkMRMLPlotSeriesNode.MarkerStyleNone)
        outputPlotSeries.SetColor(0, 0.6, 1.0)

    def showPlot(self):

        # Create chart and add plot
        if not self.plotChartNode:
            plotChartNode = slicer.mrmlScene.AddNewNodeByClass(
                "vtkMRMLPlotChartNode")
            self.plotChartNode = plotChartNode
            self.plotChartNode.SetXAxisTitle(DISTANCE_ARRAY_NAME+" (mm)")
            self.plotChartNode.SetYAxisTitle(INTENSITY_ARRAY_NAME)
            self.plotChartNode.AddAndObservePlotSeriesNodeID(
                self.outputPlotSeriesNode.GetID())
        if self.plotProportionalDistance:
            self.plotChartNode.SetXAxisTitle("Proportional distance (%)")
        else:
            self.plotChartNode.SetXAxisTitle(DISTANCE_ARRAY_NAME+" (mm)")

        # Show plot in layout
        slicer.modules.plots.logic().ShowChartInLayout(self.plotChartNode)
        slicer.app.layoutManager().plotWidget(0).plotView().fitToContent()


class LineProfileTPTest(ScriptedLoadableModuleTest):
    """
    This is the test case for your scripted module.
    Uses ScriptedLoadableModuleTest base class, available at:
    https://github.com/Slicer/Slicer/blob/main/Base/Python/slicer/ScriptedLoadableModule.py
    """

    def setUp(self):
        """ Do whatever is needed to reset the state - typically a scene clear will be enough.
        """
        slicer.mrmlScene.Clear(0)

    def runTest(self):
        """Run as few or as many tests as needed here.
        """
        self.setUp()
        self.test_LineProfile1()

    def test_LineProfile1(self):
        """ Ideally you should have several levels of tests.  At the lowest level
        tests should exercise the functionality of the logic with different inputs
        (both valid and invalid).  At higher levels your tests should emulate the
        way the user would interact with your code and confirm that it still works
        the way you intended.
        One of the most important features of the tests is that it should alert other
        developers when their changes will have an impact on the behavior of your
        module.  For example, if a developer removes a feature that you depend on,
        your test should break so they know that the feature is needed.
        """

        self.delayDisplay("Starting the test")
        #
        # first, get some data
        #
        import SampleData
        sampleDataLogic = SampleData.SampleDataLogic()
        volumeNode = sampleDataLogic.downloadMRHead()

        logic = LineProfileTPLogic()

        self.delayDisplay('Test passed!')


DISTANCE_ARRAY_NAME = "Distance"
PROPORTIONAL_DISTANCE_ARRAY_NAME = "RelativeDistance"
INTENSITY_ARRAY_NAME = "Intensity"
PEAK_HEIGHT_ARRAY_NAME = "Height"
PEAK_WIDTH_ARRAY_NAME = "Width"
PEAK_START_ARRAY_NAME = "Start"
PEAK_END_ARRAY_NAME = "End"
