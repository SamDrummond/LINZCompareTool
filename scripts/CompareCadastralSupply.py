import arcpy
import os

_newFeatureClass = arcpy.GetParameterAsText(0)
_oldFeatureClass = arcpy.GetParameterAsText(1)
_outputGeodatabasePath = arcpy.GetParameterAsText(2)
_outputNewFeatureClassName = arcpy.GetParameterAsText(3)
_outputOldFeatureClassName = arcpy.GetParameterAsText(4)
_outputResultsTableName = arcpy.GetParameterAsText(5)
_scratchWorkspaceExists = False
_addedFeatureIDs = None
_removedFeatureIDs = None
_reportTable = None
_formattedCSVTable = None
_compareResultsFile = None
_defaultScratchWorkspaceDirectory = ".." + os.path.sep + "temp"
_defaultGDBName = "scratch.gdb"
_compareResultsFileName = "compareResultsFile.txt"
_reportTableName = "ReportTable.csv"
_formattedCSVFileName = "FormattedCSVTable.csv"

def addMessage(message):
	arcpy.AddMessage(message)

def VerifyInParameters():
	addMessage("Verifying output parameters")
	hasOutputResultsTable = arcpy.Exists(_outputGeodatabasePath + os.path.sep + _outputResultsTableName)
	hasOutputNewFeatureClass = arcpy.Exists(_outputGeodatabasePath + os.path.sep + _outputNewFeatureClassName)
	hasOutputOldFeatureClass = arcpy.Exists(_outputGeodatabasePath + os.path.sep + _outputOldFeatureClassName)
	
	if (hasOutputResultsTable or 
		hasOutputNewFeatureClass or
		hasOutputOldFeatureClass):
			arcpy.AddError("Output parameters are not valid. Please verify feature classes or tables do not already exist");
			raise sys.exit()
	
def DefineScratchWorkspace():
	
	addMessage("Setting up Scratch Workspace")
	CreateNewScratchWorkspaceDirectory()
	SetNewScratchWorkSpaceDirectory()
	CreateDefaultGDB()

def CreateNewScratchWorkspaceDirectory():

	if DefaultScratchWorkspaceExists():
		RemoveScratchWorkspaceContents()
	else:
		os.makedirs(_defaultScratchWorkspaceDirectory)
		
def DefaultScratchWorkspaceExists():
	global _scratchWorkspaceExists
	_scratchWorkspaceExists = os.path.exists(_defaultScratchWorkspaceDirectory)
	return _scratchWorkspaceExists

def RemoveScratchWorkspaceContents():
	
	for fileName in os.listdir(_defaultScratchWorkspaceDirectory):
		fileDir = _defaultScratchWorkspaceDirectory + os.path.sep + fileName
		arcpy.Delete_management(fileDir)
		
def SetNewScratchWorkSpaceDirectory():
	arcpy.env.scratchWorkspace = _defaultScratchWorkspaceDirectory

def CleanUpScratchWorkspace():

	addMessage("Cleaning Up")
	
	arcpy.Delete_management("cleanCompareResultsTable")
	arcpy.Delete_management("formattedResultsTable")
	arcpy.Delete_management("FormattedCompareResults")
	arcpy.Delete_management("parcelsNewCompare")
	arcpy.Delete_management("parcelsOldCompare")
	arcpy.Delete_management("addedFeatures")
	arcpy.Delete_management("removedFeatures")
	
	if _scratchWorkspaceExists:
		RemoveScratchWorkspaceContents()
		os.rmdir(_defaultScratchWorkspaceDirectory)	
	
def CreateDefaultGDB():
	arcpy.CreateFileGDB_management(arcpy.env.scratchWorkspace, _defaultGDBName)
	
def DeleteScratchWorkspace():
	arcpy.Delete_management(_defaultScratchWorkspaceDirectory)

def IdentifyFeatureAdditionsAndRemovals():

	addMessage("Identifying Parcels that have been added or removed since previous supply")
	
	global _addedFeatureIDs
	global _removedFeatureIDs
	global _newFeatureFeatureLayer
	
	oldFeatureClassIDs = GetAllTheOldFeatureClassIDs()
	newFeatureClassIDs = GetAllTheNewFeatureClassIDs()
	
	_addedFeatureIDs = IdentifyAddedFeatures(oldFeatureClassIDs, newFeatureClassIDs)
	_removedFeatureIDs = IdentifyRemovedFeatures(oldFeatureClassIDs, newFeatureClassIDs)
	
	MakeAddedFeatureLayer()
	MakeRemovedFeatureLayer()

def GetAllTheOldFeatureClassIDs():
	return GetFieldValuesAsList(_oldFeatureClass, 'id');

def GetAllTheNewFeatureClassIDs():
	return GetFieldValuesAsList(_newFeatureClass, 'id');
	
def GetFieldValuesAsList(featureClass, fieldName):
	fieldValueList = []
	features = arcpy.SearchCursor(featureClass)
	for feature in features:
	
		fieldValue = feature.getValue(fieldName)
		fieldValueList.append(fieldValue)
		
	del features
	
	return fieldValueList

def IdentifyAddedFeatures(baseFeatures, updatedFeatures):
	return ListDifference(updatedFeatures, baseFeatures)
	
def IdentifyRemovedFeatures(baseFeatures, updatedFeatures):
	return ListDifference(baseFeatures, updatedFeatures)	
	
def ListDifference(a, b):
	b = set(b)
	return [aa for aa in a if aa not in b]

def MakeAddedFeatureLayer():
	whereClause = CreateWhereClause(_addedFeatureIDs)
	arcpy.MakeFeatureLayer_management(_newFeatureClass, "addedFeatures", whereClause)
	
def MakeRemovedFeatureLayer():
	whereClause = CreateWhereClause(_removedFeatureIDs)
	arcpy.MakeFeatureLayer_management(_oldFeatureClass, "removedFeatures", whereClause)
	
def CreateWhereClause(featureIDs, hasFeatures=True):
	whereClause = ""
	
	if featureIDs:
		whereClause = 'ID = ' + (' OR ID = '.join(str(id) for id in featureIDs))
		#whereClause = 'NOT (ID = ' + (' OR ID = '.join(str(id) for id in featureIDs)) + ")"
	
		if not hasFeatures:
			whereClause = 'NOT (' + whereClause + ')'
		
	return whereClause
	
def IdentifyAttributeChanges():

	addMessage("Identifying attribute changes since last supply")
	#Esri's feature compare tool can only compare feature classes with the same number of features - i.e. comparible features
	filterAddedFeaturesFromNewFeatureClass()
	filterRemovedFeaturesFromOldFeatureClass()
	CompareCommonFeaturesBetweenTheOldFeatureLayerAndNewFeatureLayer()
	MapCompareResultsWithOriginalIDs() #Esri Processes on ObjectID we are interested in the ID field produced by LINZ
	
def filterAddedFeaturesFromNewFeatureClass():
	createdFeaturesWhereClause = CreateWhereClause(_addedFeatureIDs, False)
	arcpy.MakeFeatureLayer_management(_newFeatureClass, "parcelsNewCompare", createdFeaturesWhereClause)
	
def filterRemovedFeaturesFromOldFeatureClass():
	deletedFeaturesWhereClause = CreateWhereClause(_removedFeatureIDs, False)
	arcpy.MakeFeatureLayer_management(_oldFeatureClass, "parcelsOldCompare", deletedFeaturesWhereClause)
	
def CompareCommonFeaturesBetweenTheOldFeatureLayerAndNewFeatureLayer():
	
	baseFeatures = "parcelsOldCompare"
	testFeatures = "parcelsNewCompare"
	sortField = "id"
	compareType = "ALL"
	ignoreOption = "IGNORE_M;IGNORE_Z;IGNORE_POINTID;IGNORE_EXTENSION_PROPERTIES;IGNORE_SUBTYPES;IGNORE_RELATIONSHIPCLASSES;IGNORE_REPRESENTATIONCLASSES"
	xyTolerance = "1.0 METERS"
	mTolerance = 0
	zTolerance = 0
	attributeTolerance = ""
	omitField = "ObjectID;SHAPE;"#SHAPE_Area;SHAPE_Length"
	continueCompare = "CONTINUE_COMPARE"
	compareResultsFile = arcpy.env.scratchWorkspace + os.path.sep + _compareResultsFileName

	arcpy.FeatureCompare_management(baseFeatures, testFeatures,sortField, compareType, ignoreOption, xyTolerance, mTolerance,zTolerance, attributeTolerance, omitField, continueCompare, compareResultsFile)

def MapCompareResultsWithOriginalIDs():
	
	OpenCompareResultsFile()
	CreateRawFormattedCSVTable()
	WriteCompareResultsToFormattedCSVTable()
	CloseFormattedCSVTable()
	CloseCompareResultsFile()
	ImportFormattedCSVIntoGDBForJoining()
	JoinNewParcelsFeatureLayerToImportedTable()
	
def OpenCompareResultsFile():
	
	global _compareResultsFile
	
	compareResultsFilePath = arcpy.env.scratchWorkspace + os.path.sep + _compareResultsFileName
	_compareResultsFile = open(compareResultsFilePath, 'r')

def CreateRawFormattedCSVTable():
	relatedIDFieldName = "RelatedID"
	descriptionFieldName = "Description"
	changeTypeFieldName = "ChangeType"
	formattedCSVTablePath = arcpy.env.scratchWorkspace + os.path.sep + _formattedCSVFileName
	
	global _formattedCSVTable
	_formattedCSVTable = open(formattedCSVTablePath, "a")
	_formattedCSVTable.write(relatedIDFieldName + ", " + descriptionFieldName + ", " + changeTypeFieldName + "\n")
	
def WriteCompareResultsToFormattedCSVTable():
	isFirstLine = True
	
	for line in _compareResultsFile:
		
		if not isFirstLine:
			
			compareResultRow = str(line).split(", ")
			objectIDIndex = len(compareResultRow)-1 #Last Column in the CompareResultsFile
			rawObjectIDColumnValue = compareResultRow[objectIDIndex]
			rawObjectIDColumnValue = rawObjectIDColumnValue.translate(None, "\n")
			objectID = int(rawObjectIDColumnValue)
			
			if objectID > 0:
				row = "{0},{1},AttributeChange\n".format(objectID, compareResultRow[2])
				_formattedCSVTable.write(row)
			
		
		isFirstLine = False

def CloseFormattedCSVTable():
	_formattedCSVTable.close()	

def CloseCompareResultsFile():
	_compareResultsFile.close()
	
def JoinNewParcelsFeatureLayerToImportedTable():
	arcpy.AddJoin_management("cleanCompareResultsTable", "RelatedID", "parcelsNewCompare", "ObjectID", "KEEP_COMMON")

def ImportFormattedCSVIntoGDBForJoining():
	#work around to ensure that table has OID's for joining
	formattedCSVTablePath = arcpy.env.scratchWorkspace + os.path.sep + _formattedCSVFileName
	defaultGDBPath = arcpy.env.scratchWorkspace + os.path.sep + _defaultGDBName
	outTable = defaultGDBPath + os.path.sep + "FormattedCompareResults"
	
	arcpy.CopyRows_management(formattedCSVTablePath, outTable)
	arcpy.MakeTableView_management(outTable, "cleanCompareResultsTable")
	
def GenerateOutputReportTable():
	
	#Because the compare results are a text file using the python built in functions. The BaseValue and TestValue fields can contain both strings and doubles and the arcpy search cursor assuming the input was a table
	#was interpreting the field type based on the first few rows result. This meant that that in some cases BaseValue and TestValue were appearing as null when in the raw textfile they were populated. This happens in 
	#ArcGIS desktop also.
	
	addMessage("Generating output report table")
	CreateReportCSVTable()
	ImportResultsCSVTableIntoGDBForPopulating()
	WriteNewFeatureIDNotificationsToReportTable()
	WriteRemovedFeatureIDNotificationsToReportTable()
	WriteAttributeChangeNotificationsToReportTable()
	
def CreateReportCSVTable():
	relatedIDFieldName = "ID"
	descriptionFieldName = "Description"
	changeTypeFieldName = "ChangeType"
	statusFieldName = "Status"
	parcelIntentFieldName = "ParcelIntent"
	reportTablePath = arcpy.env.scratchWorkspace + os.path.sep + _reportTableName
	
	global _reportTable
	_reportTable = open(reportTablePath, "a")
	_reportTable.write(relatedIDFieldName + ", " + descriptionFieldName + ", " + changeTypeFieldName + ", " + statusFieldName + ", " + parcelIntentFieldName + "\n")
	_reportTable.close()

def ImportResultsCSVTableIntoGDBForPopulating():
	inTable = arcpy.env.scratchWorkspace + os.path.sep + _reportTableName
	outPath = arcpy.env.scratchWorkspace + os.path.sep + _defaultGDBName
	outTableName = "FormattedResults"
	outTablePath = outPath + os.path.sep + outTableName
	expression = ""
	
	fieldMapIDField = arcpy.FieldMap()
	fieldMapIDField.addInputField(inTable, "ID")
	
	outputFieldIDField = fieldMapIDField.outputField
	outputFieldIDField.name = "ID"
	outputFieldIDField.type = "Integer"
	fieldMapIDField.outputField = outputFieldIDField
	
	fieldMapDescriptionField = arcpy.FieldMap()
	fieldMapDescriptionField.addInputField(inTable, "Description")
	
	fieldMapChangeTypeField = arcpy.FieldMap()
	fieldMapChangeTypeField.addInputField(inTable, "ChangeType")
	
	fieldMapStatusField = arcpy.FieldMap()
	fieldMapStatusField.addInputField(inTable, "Status")
	
	fieldMapParcelIntentField = arcpy.FieldMap()
	fieldMapParcelIntentField.addInputField(inTable, "ParcelIntent")
	
	feildMappings = arcpy.FieldMappings()
	feildMappings.addFieldMap(fieldMapIDField)
	feildMappings.addFieldMap(fieldMapDescriptionField)
	feildMappings.addFieldMap(fieldMapChangeTypeField)
	feildMappings.addFieldMap(fieldMapStatusField)
	feildMappings.addFieldMap(fieldMapParcelIntentField)
		
	arcpy.TableToTable_conversion(inTable, outPath, outTableName, expression, feildMappings)
	arcpy.MakeTableView_management(outTablePath, "formattedResultsTable")
	
def WriteNewFeatureIDNotificationsToReportTable():
	
	insertRows = arcpy.InsertCursor("formattedResultsTable")
	searchRows = arcpy.SearchCursor("addedFeatures")
	
	for searchRow in searchRows:
	
		idValue = searchRow.getValue('id')
		descriptionValue = "ID " + str(idValue) + " has been added since the last supply"
		changeTypeValue = "Addition"
		statusValue = searchRow.getValue('status')
		parcelIntentValue = searchRow.getValue('parcel_intent')
	
		insertRow = insertRows.newRow()
		insertRow.setValue("ID", idValue)
		insertRow.setValue("Description", descriptionValue)
		insertRow.setValue("ChangeType", changeTypeValue)
		insertRow.setValue("Status", statusValue)
		insertRow.setValue("ParcelIntent", parcelIntentValue)
		insertRows.insertRow(insertRow)
		
		del insertRow
		
	del insertRows
	del searchRows

def WriteRemovedFeatureIDNotificationsToReportTable():
		
	insertRows = arcpy.InsertCursor("formattedResultsTable")
	searchRows = arcpy.SearchCursor("addedFeatures")
	
	for searchRow in searchRows:
	
		idValue = searchRow.getValue('id')
		descriptionValue = "ID " + str(idValue) + " has been removed since the last supply"
		changeTypeValue = "Removal"
		statusValue = searchRow.getValue('status')
		parcelIntentValue = searchRow.getValue('parcel_intent')
	
		insertRow = insertRows.newRow()
		insertRow.setValue("ID", idValue)
		insertRow.setValue("Description", descriptionValue)
		insertRow.setValue("ChangeType", changeTypeValue)
		insertRow.setValue("Status", statusValue)
		insertRow.setValue("ParcelIntent", parcelIntentValue)
		insertRows.insertRow(insertRow)
		
		del insertRow
		
	del insertRows
	del searchRows
	
def WriteAttributeChangeNotificationsToReportTable():
	inTable = "cleanCompareResultsTable"
	outPath = arcpy.env.scratchWorkspace + os.path.sep + _defaultGDBName
	outTableName = "FormattedResults"
	outTablePath = outPath + os.path.sep + outTableName
	schemaType = "NO_TEST"
	
	#Needed to for fields based in the join
	parcelsNewCompareDescription = arcpy.Describe("parcelsNewCompare")
	inTableDescription = arcpy.Describe(inTable)
	
	fieldMapIDField = arcpy.FieldMap()
	fieldMapIDField.addInputField(inTable, parcelsNewCompareDescription.name + ".id")
	
	fieldMapDescriptionField = arcpy.FieldMap()
	fieldMapDescriptionField.addInputField(inTable, inTableDescription.name + ".Description")
	
	fieldMapChangeTypeField = arcpy.FieldMap()
	fieldMapChangeTypeField.addInputField(inTable, inTableDescription.name + ".ChangeType")
	
	outputFieldParcelIntentField = fieldMapIDField.outputField
	outputFieldParcelIntentField.name = "ParcelIntent"
	outputFieldParcelIntentField.type = "String"
	
	fieldMapStatusField = arcpy.FieldMap()
	fieldMapStatusField.addInputField(inTable, parcelsNewCompareDescription.name + ".status")
	
	outputFieldStatusField = fieldMapStatusField.outputField
	outputFieldStatusField.name = "Status"
	outputFieldStatusField.type = "String"
	fieldMapStatusField.outputField = outputFieldStatusField
	
	fieldMapParcelIntentField = arcpy.FieldMap()
	fieldMapParcelIntentField.addInputField(inTable, parcelsNewCompareDescription.name + ".parcel_intent")
	
	outputFieldParcelIntentField = fieldMapParcelIntentField.outputField
	outputFieldParcelIntentField.name = "ParcelIntent"
	outputFieldParcelIntentField.type = "String"
	fieldMapParcelIntentField.outputField = outputFieldParcelIntentField
	
	fieldMappings = arcpy.FieldMappings()
	fieldMappings.addFieldMap(fieldMapIDField)
	fieldMappings.addFieldMap(fieldMapDescriptionField)
	fieldMappings.addFieldMap(fieldMapChangeTypeField)
	fieldMappings.addFieldMap(fieldMapStatusField)
	fieldMappings.addFieldMap(fieldMapParcelIntentField)
	
	arcpy.Append_management([inTable], outTablePath, schemaType, fieldMappings)
	
def ExportArtefactsToOutputGeodatabase():
	
	addMessage("Exporting review artefacts and creating relationships")
	ExportNewFeatureClassToOutputGeodatabase()
	ExportOutputFeatureClassToOutputGeodatabase()
	ExportResultsTableFeatureClassToOutputGeodatabase()
	ConstructRelationshipClass(_outputNewFeatureClassName)
	ConstructRelationshipClass(_outputOldFeatureClassName)
	
def ExportNewFeatureClassToOutputGeodatabase():
	arcpy.FeatureClassToFeatureClass_conversion(_newFeatureClass, _outputGeodatabasePath, _outputNewFeatureClassName)	
	
def ExportOutputFeatureClassToOutputGeodatabase():
	arcpy.FeatureClassToFeatureClass_conversion(_oldFeatureClass, _outputGeodatabasePath, _outputOldFeatureClassName)

def ExportResultsTableFeatureClassToOutputGeodatabase():
	arcpy.TableToTable_conversion("formattedResultsTable", _outputGeodatabasePath, _outputResultsTableName)

def ConstructRelationshipClass(relatedFeatureName):
	originTable = _outputGeodatabasePath + os.path.sep + _outputResultsTableName
	destinationTable = _outputGeodatabasePath + os.path.sep + relatedFeatureName
	outRelationshipClass = _outputGeodatabasePath + os.path.sep + "Relate" + _outputResultsTableName + relatedFeatureName
	relationshipType = "SIMPLE"
	forwardLabel = "Attributes from " + relatedFeatureName
	backLabel = "Attributes from " + _outputResultsTableName
	messageDirection = "NONE"
	cardinality = "ONE_TO_MANY"
	attributed = "NONE"
	primaryKey = "ID"
	foreignKey = "ID"
	
	arcpy.CreateRelationshipClass_management(originTable, destinationTable, outRelationshipClass, relationshipType, 
		forwardLabel, backLabel, messageDirection, cardinality, attributed, primaryKey, foreignKey)

def AddArtefactsToMap():
	addMessage("Adding artefacts to display")
	mxd = arcpy.mapping.MapDocument("CURRENT")
	dataFrame = mxd.activeDataFrame
	
	reviewTablePath = _outputGeodatabasePath + os.path.sep + _outputResultsTableName
	reviewTableView = arcpy.mapping.TableView(reviewTablePath)
	arcpy.mapping.AddTableView(dataFrame, reviewTableView)
	
	newFeatureClassPath = _outputGeodatabasePath + os.path.sep + _outputNewFeatureClassName
	newFeatureLayer = arcpy.mapping.Layer(newFeatureClassPath)
	arcpy.mapping.AddLayer(dataFrame, newFeatureLayer)
	
	oldFeatureClassPath = _outputGeodatabasePath + os.path.sep + _outputOldFeatureClassName
	oldFeatureLayer = arcpy.mapping.Layer(oldFeatureClassPath)
	arcpy.mapping.AddLayer(dataFrame, oldFeatureLayer)

try:

	VerifyInParameters()
	DefineScratchWorkspace()
	IdentifyFeatureAdditionsAndRemovals()
	IdentifyAttributeChanges()
	GenerateOutputReportTable();
	ExportArtefactsToOutputGeodatabase()
	AddArtefactsToMap()
	
finally:
	CleanUpScratchWorkspace()