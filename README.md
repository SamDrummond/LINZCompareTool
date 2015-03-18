# LINZ Compare Tool #

This script has been custom built to allow users to compare updates from the LINZ Cadastral Parcel Fabric using **ArcMap**.  The tool will look for the following changes:

- Features added to the latest supply (newly created parcels)
- Features missing from the latest supply (newly removed parcels)
- Feature attributes that have changed in the latest supply (updated parcels)

The script will create five output artefacts including:

- A tabular report with a record for every type of change
- A copy of the input 'OLD' feature class
- A copy of the input 'NEW' feature class
- A relationship class joining the changes in the tabular report to the features in the 'OLD' feature class this allows analysts to navigate to the specific parcels have been removed in the latest supply
- A relationship class joining the changes in the tabular report to the features in the 'NEW' feature class this allows analysts to navigate to the newly added and modified parcels 

**Developed By:** Sam Drummond (Sam Drummond Consulting)

**Source:** None

**Requirements:** ArcGIS Desktop 10.2.2, ArcPy, Python 2.7

	 



