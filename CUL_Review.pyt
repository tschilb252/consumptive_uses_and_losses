# -*- coding: utf-8 -*-

###############################################################################################
###############################################################################################

# Name:             CUL_Review.pyt
# Author:           Methodology developed by Caleb Mccurry, USBR and Troy Wirth, USBR; code by Kelly Meehan, USBR 
# Created:          20200804
# Updated:          20200812 
# Version:          Created using Python 3.6.8 

# Requires:         ArcGIS Pro 

# Notes:            This is a Python Toolbox to be run within ArcGIS Pro; it is not intended as a stand-alone script.

# Description:      This tool toolbox holds tools for calculating various calculations for consumptive uses and losses.
                
###############################################################################################
###############################################################################################

# Tools within this CUL_Review Python toolbox:
    # I. Calculate_Annual_Net_Evapotranspiration_by_State_HUC8
        # 0. Set-up
        # 1. Calculate annual mean precipitation per State-HUC8
        # 2. Calculate mean evapotranspiration rate per State-HUC8 
        # 3. Calculate annual net evapotranspiration (in) per State-HUC8 using the formula: net evapotranspiration = (evapotranspiration (mm) - precipitation)/25.4 

#----------------------------------------------------------------------------------------------
        
import arcpy

class Toolbox(object):
    def __init__(self):
        """Define the toolbox (the name of the toolbox is the name of the
        .pyt file)."""
        self.label = "CUL_Review"
        self.alias = "CUL_Review"

        # List of tool classes associated with this toolbox
        self.tools = [Calculate_Annual_Net_Evapotranspiration_by_State_HUC8]

# I. Calculate_Annual_Net_Evapotranspiration_by_State_HUC8

class Calculate_Annual_Net_Evapotranspiration_by_State_HUC8(object):
    def __init__(self):
        """Define the tool (tool name is the name of the class)."""
        self.label = "Calculate_Annual_Net_Evapotranspiration_by_State_HUC8"
        self.description = ""
        self.canRunInBackground = False
        
    def getParameterInfo(self):
        """Define parameter definitions"""
        
        geodatabase = arcpy.Parameter(
            displayName="Output Geodatabase",
            name="Output Geodatabase",
            datatype="DEWorkspace",
            parameterType="Required",
            direction="Input")
        
        path_prism_directory = arcpy.Parameter(
            displayName="PRISM Directory",
            name="PRISM_Directory",
            datatype="DEWorkspace",
            parameterType="Required",
            direction="Input")
        
        fc_huc8_original = arcpy.Parameter(
            displayName="State-HUC8 Feature Class",
            name="State-HUC8_Feature_Class",
            datatype="DEFeatureClass",
            parameterType="Required",
            direction="Input")
                
        raster_evap_original = arcpy.Parameter(
            displayName="Evapotranspiration Raster",
            name="Evapotranspiration_Raster",
            datatype="DERasterDataset",
            parameterType="Required",
            direction="Input")
                 
        parameters = [geodatabase, path_prism_directory, fc_huc8_original, raster_evap_original]
        
        return parameters

    def isLicensed(self):
        """Set whether tool is licensed to execute."""
        return True

    def updateParameters(self, parameters):
        """Modify the values and properties of parameters before internal
        validation is performed.  This method is called whenever a parameter
        has been changed."""
        return

    def updateMessages(self, parameters):
        """Modify the messages created by internal validation for each tool
        parameter.  This method is called after internal validation."""
        return

    def execute(self, parameters, messages):
        """The source code of the tool."""
        
        geodatabase = parameters[0].valueAsText
        path_prism_directory = parameters[1].valueAsText
        fc_huc8_original = parameters[2].valueAsText
        raster_evap_original = parameters[3].valueAsText
        
        #--------------------------------------------
        
        # 0. Set-up
        
        # 0.0 Install necessary packages
        import arcpy, os, fnmatch, re
      
        #--------------------------------------------
        
        # 0.1 Set environment settings
        
        # Set workspace to output directory
        arcpy.env.workspace = geodatabase
                
        # Overwrite output
        arcpy.env.overwriteOutput = True
        
        # 0.2 Check out Spatial Analyst Extension
        arcpy.CheckOutExtension('Spatial')
        
        # 0.3 Change working directory to output directory
        os.chdir(geodatabase)
        
        #----------------------------------------------------------------------------------------------
        
        # 1. Calculate annual mean precipitation per State-HUC8
        
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
        arcpy.env.snapRaster = raster_evap_original
        
        # Extract Raster by Mask
        
        raster_evap_clipped = os.path.join(geodatabase, os.path.splitext(os.path.basename(raster_evap_original))[0] + '_clipped')  
        out_evap_clipped = arcpy.sa.ExtractByMask(in_raster = raster_evap_original, in_mask_data = state_HUC8_NAD83_UTM12N_buffered)
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
        
        # Export attribute table of State_HUC8 reprojected feature class to directory storing Output Geodatabase
        arcpy.management.CopyRows(in_rows = state_HUC8_NAD83_UTM12N, out_table = 'net_evapotranspiration.csv')
        
