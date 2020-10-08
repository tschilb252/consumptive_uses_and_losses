
###############################################################################################
###############################################################################################

# Name:             Calculate_Stockpond_Consumptive_Use.py
# Author:           Methodology developed by Caleb Mccurry, USBR and Troy Wirth, USBR; code by Kelly Meehan, USBR 
# Created:          20200804
# Updated:          20201001 
# Version:          Created using Python 3.6.8 

# Requires:         ArcGIS Pro 

# Notes:            This script is intended to be used for a Script Tool within ArcGIS Pro; it is not intended as a stand-alone script.

# Description:      This tool calculates stockpond consumptive use by multiplying net evapotranspiration by stockpond acreage

#----------------------------------------------------------------------------------------------

# Tool setup:       The script tool's properties can be set as follows: 
#
#                      Parameters tab:    
#                           Output Geodatabase              Workspace (Data Type) > Required (Type) > Input (Direction)                  
#                           PRISM Directory                 Workspace (Data Type) > Required (Type) > Input (Direction)                  
#                           State-HUC8 Feature Class        Feature Class (Data Type) > Required (Type) > Input (Direction)                    
#                           Evapotranspiration Raster       Raster Dataset (Data Type) > Required (Type) > Input (Direction)

###############################################################################################
###############################################################################################

# This script will:

# 0. Set-up
# 1. Calculate annual mean precipitation per State-HUC8 from 1970 - 2018
# 2. Calculate mean evapotranspiration rate per State-HUC8 
# 3. Calculate annual net evapotranspiration (in) per State-HUC8 from 1970 - 2018 using the formula: net evapotranspiration = (evapotranspiration (mm) - precipitation)/25.4 

#----------------------------------------------------------------------------------------------

# 0. Set-up

# 0.0 Install necessary packages
import arcpy, os, fnmatch, re

#--------------------------------------------

# 0.1 Read in tool parameters

# User selects output directory file geodatabase
geodatabase = arcpy.GetParameterAsText(0) 

# User selects directory with PRISM rasters
path_prism_directory = arcpy.GetParameterAsText(1)

# User selects original State-HUC8 feature class
fc_huc8_original = arcpy.GetParameterAsText(2)

# User selects directory with monthly evapotranspiration rasters (Estimated Mean Monthly Evapotranspiration 1956 - 1970 raster) from https://cida.usgs.gov/thredds/ncss/mows/pe/dataset.html
path_evap_directory = arcpy.GetParameterAsText(3)

#--------------------------------------------

# 0.2 Set environment settings

# Set workspace to output directory
arcpy.env.workspace = geodatabase

#Overwrite output
arcpy.env.overwriteOutput = True

# 0.3 Check out Spatial Analyst Extension
arcpy.CheckOutExtension('Spatial')

# 0.4 Change working directory to output directory
os.chdir(geodatabase)

#----------------------------------------------------------------------------------------------

# 1. Calculate annual mean precipitation per State-HUC8 from 1970 - 2018

# Reproject State_HUC8 feature class to GCS NAD83 and PCS UTM12N

output_CRS = arcpy.SpatialReference('NAD 1983 UTM Zone 12N')
state_HUC8_NAD83_UTM12N = os.path.join(geodatabase, 'state_HUC8_NAD83_UTM12N')
arcpy.Project_management(in_dataset = fc_huc8_original, out_dataset = state_HUC8_NAD83_UTM12N, out_coor_system = output_CRS) 

# Create a buffered version of the NAD83 UTM12N reprojected feature class

state_HUC8_NAD83_UTM12N_buffered = os.path.join(geodatabase, 'state_HUC8_NAD83_UTM12N_buffered')
arcpy.Buffer_analysis(in_features = state_HUC8_NAD83_UTM12N, out_feature_class = state_HUC8_NAD83_UTM12N_buffered, buffer_distance_or_field = '20000 Meters', dissolve_option = 'ALL')

# Create list of rasters by using a list comprehension to collect the yearly average raster while iterating through nested directories recursively
list_prism_rasters = [os.path.join(dirpath, f)
    for dirpath, dirnames, filenames in os.walk(path_prism_directory)
    for f in fnmatch.filter(filenames, 'PRISM_ppt_stable_4kmM?_????_bil.bil')]

list_prism_reprojected = []

for p in list_prism_rasters:
    year = re.split('[_.]', os.path.basename(p))[4]
    reprojected_raster = os.path.join(geodatabase, 'PRISM_' + year + '_NAD83_UTM12N')
    arcpy.ProjectRaster_management(in_raster = p, out_raster = reprojected_raster, out_coor_system = output_CRS)
    list_prism_reprojected.append(reprojected_raster)

# Generate a table of mean precipitation by State-HUC8 zone for each year; join values to State-HUC8 reprojected feature class

for r in list_prism_reprojected:
    year = re.split('[_.]', os.path.basename(r))[1]
    table_mean_precip = os.path.join(geodatabase, 'PRISM_' + year + '_Mean_Zonal_Precipitation')
    arcpy.sa.ZonalStatisticsAsTable(in_zone_data = state_HUC8_NAD83_UTM12N, zone_field = 'OBJECTID', in_value_raster = r, out_table = table_mean_precip, statistics_type = 'MEAN') 
    arcpy.JoinField_management(in_data = state_HUC8_NAD83_UTM12N, in_field = 'OBJECTID', join_table = table_mean_precip, join_field = 'OBJECTID_1', fields = 'MEAN')
    arcpy.AddField_management(in_table = state_HUC8_NAD83_UTM12N, field_name = 'ppt_mean_' + year, field_type = 'FLOAT')
    arcpy.CalculateField_management(in_table = state_HUC8_NAD83_UTM12N, field = 'ppt_mean_' + year, expression = "!MEAN!", expression_type = 'PYTHON3')
    arcpy.DeleteField_management(in_table = state_HUC8_NAD83_UTM12N, drop_field = 'MEAN')

#----------------------------------------------------------------------------------------------

# 2. Calculate mean evapotranspiration rate per State-HUC8 

# Set snap raster environment setting (otherwise Extract by Mask may shift raster)
arcpy.env.snapRaster = path_evap_directory[0]

# Set spacial reference
spatial_reference = arcpy.SpatialReference(26912)

# Create list of rasters by using a list comprehension to collect the yearly average raster while iterating through nested directories recursively
list_evap_rasters = [os.path.join(dirpath, e)
    for dirpath, dirnames, filenames in os.walk(path_evap_directory)
    for e in fnmatch.filter(filenames, '*.bil')]

# Create a list originally comprised of raw rasters that are replaced if necessary with reprojected ones 
raster_list = list_evap_rasters

for (i, raster) in enumerate(raster_list):
    wkid_raster = arcpy.Describe(raster).spatialReference.factoryCode
    arcpy.AddMessage('The spatial reference of ' + raster + ' has a well-known ID (WKID) of: ' + str(wkid_raster))
    print(raster + 'The spatial reference of ' + raster + ' has a well-known ID (WKID) of: ' + str(wkid_raster))
    
    # If the raster has a projection other than that of Edited Field Borders Shapefile, replace itself with a reprojected version 
    if wkid_raster != 26912:
        arcpy.AddMessage('The spatial reference of ' + raster + ' has a well-known ID (WKID) different from 26912; reprojecting.')
        print('The spatial reference of ' + raster + ' has a well-known ID (WKID) different from 26912; reprojecting.')
        raster_name = os.path.basename(raster)
        reprojected_raster_name = raster_name.rsplit(sep = '.', maxsplit = 1)[0]
        reprojected_raster = os.path.join(geodatabase, reprojected_raster_name)

        # Check if pre-existing raster exists and delete if so
        if arcpy.Exists(reprojected_raster):
            arcpy.Delete_management(in_data = reprojected_raster)
            arcpy.AddMessage('Deleted pre-existing reprojected raster: ' + reprojected_raster)
        
        # Reproject raster
        arcpy.ProjectRaster_management(in_raster = raster, out_raster = reprojected_raster, out_coor_system = spatial_reference)
        arcpy.AddMessage('Generated: ' + reprojected_raster)
        
        # Replace original raster with that of reprojected raster
        raster_list[i] = reprojected_raster
        
    else:
        arcpy.AddMessage(raster + ' projection matches NAD83 UTM12N; reprojection not necessary.')

for r in raster_list:
    # Clip each monthly evap raster   
    raster_evap_clipped = os.path.join(geodatabase, os.path.splitext(os.path.basename(r))[0] + '_clipped')  
    out_evap_clipped = arcpy.sa.ExtractByMask(in_raster = r, in_mask_data = state_HUC8_NAD83_UTM12N_buffered)
    out_evap_clipped.save(raster_evap_clipped)
    
# Reproject evapotranspiration raster to GCS NAD83 and PCS UTM12N

raster_evap_reprojected = os.path.join(geodatabase, 'Evapotranspiration_NAD83_UTM12N')
arcpy.ProjectRaster_management(in_raster = raster_evap_clipped, out_raster = raster_evap_reprojected, out_coor_system = output_CRS)

# Copy evapotranspiration raster to set NoData value to 0

raster_evap_nodata = os.path.join(geodatabase, 'Evapotranspiration_NAD83_UTM12N_NoData')
arcpy.CopyRaster_management(in_raster = raster_evap_reprojected, out_rasterdataset = raster_evap_nodata, nodata_value = 0)

# Resample evapotranspiration raster (otherwise Zonal Statistics as Table will return NULL values as cells would be too large to have a center in zones of small sizes)

raster_evap_resampled = os.path.join(geodatabase, 'Evapotranspiration_NAD83_UTM12N_NoData_Resample')

cell_size_x_result = arcpy.GetRasterProperties_management(in_raster = list_prism_reprojected[0], property_type = 'CELLSIZEX')
cell_size_x = cell_size_x_result.getOutput(0)
cell_size_y_result = arcpy.GetRasterProperties_management(in_raster = list_prism_reprojected[0], property_type = 'CELLSIZEY')
cell_size_y = cell_size_y_result.getOutput(0)
size_x_y = cell_size_x + ' ' + cell_size_y

arcpy.env.snapRaster = list_prism_reprojected[0]

arcpy.Resample_management(in_raster = raster_evap_nodata, out_raster = raster_evap_resampled, cell_size = size_x_y, resampling_type = 'BILINEAR')

# Generate a table of evapotranspiration rates per State-HUC8; join values to State-HUC8 reprojected feature class

table_mean_evap = os.path.join(geodatabase, 'Evapotranspiration_Mean_Rate')

arcpy.sa.ZonalStatisticsAsTable(in_zone_data = state_HUC8_NAD83_UTM12N, zone_field = 'OBJECTID', in_value_raster = raster_evap_resampled, out_table = table_mean_evap, statistics_type = 'MEAN') 

# Join data

arcpy.JoinField_management(in_data = state_HUC8_NAD83_UTM12N, in_field = 'OBJECTID', join_table = table_mean_evap, join_field = 'OBJECTID_1', fields = 'MEAN')
field_evapotranspiration = 'Evapotranspiration_Mean_Rate'
arcpy.AddField_management(in_table = state_HUC8_NAD83_UTM12N, field_name = field_evapotranspiration, field_type = 'FLOAT')
arcpy.CalculateField_management(in_table = state_HUC8_NAD83_UTM12N, field = field_evapotranspiration, expression = "!MEAN!", expression_type = 'PYTHON3')
arcpy.DeleteField_management(in_table = state_HUC8_NAD83_UTM12N, drop_field = 'MEAN')

#----------------------------------------------------------------------------------------------

# 3. Calculate annual net evapotranspiration (inches) per State-HUC8 from 1970 - 2018 using the formula: net evapotranspiration = (evapotranspiration (millimeters) - precipitation)/25.4 

fields_prism = [field.name for field in arcpy.ListFields(dataset = state_HUC8_NAD83_UTM12N, wild_card = 'ppt_mean_*')]

def calculate_net_evap_inches():
    for i in fields_prism:
        year = re.split('[_.]', i)[2]
        field_net_evap = 'net_evap_' + year
        if arcpy.ListFields(dataset = state_HUC8_NAD83_UTM12N, wild_card = field_net_evap):
            arcpy.DeleteField_management(in_table = state_HUC8_NAD83_UTM12N, drop_field = field_net_evap)
        arcpy.AddField_management(in_table = state_HUC8_NAD83_UTM12N, field_name = field_net_evap, field_type = 'FLOAT')
        fields_in_iteration = [field_net_evap, field_evapotranspiration, i]
        with arcpy.da.UpdateCursor(in_table = state_HUC8_NAD83_UTM12N, field_names = fields_in_iteration) as cursor: 
            for row in cursor:
                if row[1] is not None and row[2] is not None:
                    row[0] = (row[1] - row[2])/25.4 # Divide by 25.4 to convert from milimeters to inches
                    cursor.updateRow(row)
            
calculate_net_evap_inches()            

# Export attribute table of State_HUC8 reprojected feature class
arcpy.management.CopyRows(in_rows = state_HUC8_NAD83_UTM12N, out_table = 'net_evapotranspiration.csv')

# TTDL
# subtract prism from appropriate month evap raster instead of static single raster
# Add check for both prism rasters and monthly evap that projection is the same 
# Carry over changes from 
# Make WKID a variable but set default value
# Change name of reprojected raster to be dynamicly named to user defined EPSG code