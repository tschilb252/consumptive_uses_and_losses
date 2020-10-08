
###############################################################################################
###############################################################################################

# Name:             CUL_Monthly.py
# Author:           Methodology by Caleb Mccurry, USBR and Troy Wirth, USBR; code by Kelly Meehan, USBR 
# Created:          20200804
# Updated:          20201008 
# Version:          Created using Python 3.6.8 

# Requires:         ArcGIS Pro 

# Notes:            This script is intended to be used for a Script Tool within ArcGIS Pro; it is not intended as a stand-alone script
#                   Precipitation Directory should have Free Water Surface .bil rasters: FWS_Monthly_MM.bil, where MM is a two digit month reference from 01 - 12
#                   Evapotranspiration Directory should have PRISM .bil rasters named: PRISM_YYYYMM.bil
#                   All input data should be in same projection

# Description:      This tool calculates stockpond consumptive use by multiplying net evapotranspiration by stockpond acreage

#----------------------------------------------------------------------------------------------

# Tool setup:       The script tool's properties can be set as follows: 
#
#                      Parameters tab:    
#                           Output Geodatabase              Workspace (Data Type) > Required (Type) > Input (Direction)                  
#                           Precipitation Directory         Workspace (Data Type) > Required (Type) > Input (Direction)                  
#                           State-HUC8 Feature Class        Feature Class (Data Type) > Required (Type) > Input (Direction)                    
#                           Evapotranspiration Directory    Workspace (Data Type) > Required (Type) > Input (Direction)

###############################################################################################
###############################################################################################

# This script will:

# 0. Set-up
# 1. Calculate monthly mean precipitation per State-HUC8 for time period
# 2. Calculate mean evapotranspiration rate per State-HUC8 
# 3. Calculate monthly net evapotranspiration (in) per State-HUC per time period using the formula: net evapotranspiration = (evapotranspiration (mm) - precipitation)/25.4 

#----------------------------------------------------------------------------------------------

# 0. Set-up

# 0.0 Install necessary packages
import arcpy, os, fnmatch, re

#--------------------------------------------

# 0.1 Read in tool parameters

# User selects output directory file geodatabase
geodatabase = arcpy.GetParameterAsText(0) 

# User selects directory with monthly PRISM rasters
path_precip_directory = arcpy.GetParameterAsText(1)

# User selects State-HUC8 feature class
fc_huc8_original = arcpy.GetParameterAsText(2)

# User selects directory with monthly evapotranspiration rasters (Estimated Mean Monthly Evapotranspiration rasters) from https://cida.usgs.gov/thredds/ncss/mows/pe/dataset.html
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

# 1. Copy State-HUC8 feature class into geodatabase

fc_huc8 = os.path.join(geodatabase, os.path.splitext(os.path.basename(fc_huc8_original))[0])
arcpy.CopyFeatures_management(in_features = fc_huc8_original, out_feature_class = fc_huc8)

#----------------------------------------------------------------------------------------------

# 2. Calculate mean precipitation per State-HUC8 per monthly raster

# Create list of rasters using list comprehension 
list_precip_rasters = [os.path.join(dirpath, i)
    for dirpath, dirnames, filenames in os.walk(path_precip_directory)
    for i in fnmatch.filter(filenames, '*.bil')]

# Set snap raster environment setting (otherwise Extract by Mask may shift raster)
arcpy.env.snapRaster = list_precip_rasters[0]

# Generate a table of mean precipitation by State-HUC8 zone for each year; join values to State-HUC8 reprojected feature class

for r in list_precip_rasters:
    date = re.split('[_.]', os.path.basename(r))[1]
    table_mean_precip = os.path.join(geodatabase, 'PRISM_' + date + '_Mean_Zonal_Precipitation')
    arcpy.sa.ZonalStatisticsAsTable(in_zone_data = fc_huc8, zone_field = 'OBJECTID', in_value_raster = r, out_table = table_mean_precip, statistics_type = 'MEAN') 
    arcpy.JoinField_management(in_data = fc_huc8, in_field = 'OBJECTID', join_table = table_mean_precip, join_field = 'OBJECTID_1', fields = 'MEAN')
    arcpy.AddField_management(in_table = fc_huc8, field_name = 'ppt_' + date, field_type = 'FLOAT')
    arcpy.CalculateField_management(in_table = fc_huc8, field = 'ppt_' + date, expression = "!MEAN!", expression_type = 'PYTHON3')
    arcpy.DeleteField_management(in_table = fc_huc8, drop_field = 'MEAN')
    arcpy.Delete_management(table_mean_precip)

#----------------------------------------------------------------------------------------------

# 2. Calculate mean evapotranspiration rate per State-HUC8 for each calendar month

# Create list of rasters by using a list comprehension to collect the yearly average raster while iterating through nested directories recursively
list_evap_rasters = [os.path.join(dirpath, e)
    for dirpath, dirnames, filenames in os.walk(path_evap_directory)
    for e in fnmatch.filter(filenames, '*.bil')]

# Extract cell size from precipitation rasters

cell_size_x_result = arcpy.GetRasterProperties_management(in_raster = list_precip_rasters[0], property_type = 'CELLSIZEX')
cell_size_x = cell_size_x_result.getOutput(0)
cell_size_y_result = arcpy.GetRasterProperties_management(in_raster = list_precip_rasters[0], property_type = 'CELLSIZEY')
cell_size_y = cell_size_y_result.getOutput(0)
size_x_y = cell_size_x + ' ' + cell_size_y

# Resample the twelve calendar month evapotranspiration rasters using cell size of precipitation rasters

for j in list_evap_rasters:
    
    # Clip each monthly evap raster   
    raster_evap_clipped = os.path.join(geodatabase, os.path.splitext(os.path.basename(j))[0] + '_clipped')  
    out_evap_clipped = arcpy.sa.ExtractByMask(in_raster = j, in_mask_data = fc_huc8)
    out_evap_clipped.save(raster_evap_clipped)
    
    # Resample each raster    
    raster_evap_resampled = os.path.join(geodatabase, os.path.splitext(os.path.basename(j))[0] + '_resampled')
    arcpy.Resample_management(in_raster = out_evap_clipped, out_raster = raster_evap_resampled, cell_size = size_x_y, resampling_type = 'BILINEAR')

    # Generate a table of evapotranspiration rates per State-HUC8; join values to State-HUC8 reprojected feature class
    table_mean_evap = os.path.join(geodatabase, 'Evap_Mean_Rate')
    arcpy.sa.ZonalStatisticsAsTable(in_zone_data = fc_huc8, zone_field = 'OBJECTID', in_value_raster = raster_evap_resampled, out_table = table_mean_evap, statistics_type = 'MEAN') 

    # Join data
    arcpy.JoinField_management(in_data = fc_huc8, in_field = 'OBJECTID', join_table = table_mean_evap, join_field = 'OBJECTID_1', fields = 'MEAN')
    month = re.split('[., _]', os.path.basename(j))[2]
    field_evapotranspiration = 'evap_' + month
    arcpy.AddField_management(in_table = fc_huc8, field_name = field_evapotranspiration, field_type = 'FLOAT')
    arcpy.CalculateField_management(in_table = fc_huc8, field = field_evapotranspiration, expression = "!MEAN!", expression_type = 'PYTHON3')
    arcpy.DeleteField_management(in_table = fc_huc8, drop_field = 'MEAN')

#----------------------------------------------------------------------------------------------

# 3. Calculate monthly net evapotranspiration (inches) per State-HUC8 from 1970 - 2018 using the formula: net evapotranspiration = (evapotranspiration (millimeters) - precipitation)/25.4 

fields_prism = [field.name for field in arcpy.ListFields(dataset = fc_huc8, wild_card = 'ppt_*')]
fields_evap = [field.name for field in arcpy.ListFields(dataset = fc_huc8, wild_card = 'evap_*')]

def calculate_net_evap_inches():
    for i in fields_prism:
        date = re.split('[_]', i)[1]
        month_precip = re.split('[_]', i)[1][-2:]
        field_net_evap = 'net_evap_' + date
        if arcpy.ListFields(dataset = fc_huc8, wild_card = field_net_evap):
            arcpy.DeleteField_management(in_table = fc_huc8, drop_field = field_net_evap)
        arcpy.AddField_management(in_table = fc_huc8, field_name = field_net_evap, field_type = 'FLOAT')
        for j in fields_evap:
            month_evap = re.split('[_]', j)[1]
            fields_in_iteration = [field_net_evap, j, i]
            with arcpy.da.UpdateCursor(in_table = fc_huc8, field_names = fields_in_iteration) as cursor: 
                for row in cursor:
                    if row[1] is not None and row[2] is not None:
                        if month_evap == month_precip:
                            row[0] = (row[1] - row[2])/25.4 # Divide by 25.4 to convert from milimeters to inches
                    cursor.updateRow(row)

calculate_net_evap_inches()            

# Export attribute table of feature class to csv
arcpy.management.CopyRows(in_rows = fc_huc8, out_table = 'net_monthly_evapotranspiration.csv')

