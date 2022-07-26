#!/usr/bin/env python3
# -*- coding: utf-8 -*-


# HISTORY
#    Feb 2022 - Vr. 1.0: Completed initial version
#    Jul 2022 - Vr. 1.1: Changed keywords to final flight values


"""
This module contains the code for the NIRSpec Multi Shutter Array Target
Acquisition (MSATA) monitor, which monitors the TA offsets, including
the roll for MSATA.

This monitor displays details of individual MSATA stars and details of
fitting and rejection procedure (least square fit).

This monitor also displays V2, V3, and roll offsets over time.

Author
______
    - Maria Pena-Guerrero
    
Use
---
    This module can be used from the command line as follows:
    python msata_monitor.py
    
"""


# general imports
import os
import logging
import numpy as np
import pandas as pd
from datetime import datetime
from astropy.io import fits
from random import randint
from bokeh.io import output_file
from bokeh.plotting import figure, show, save
from bokeh.models import ColumnDataSource, Range1d
from bokeh.models.tools import HoverTool
from bokeh.layouts import gridplot
from bokeh.models import Span, Label

# jwql imports
from jwql.utils.logging_functions import log_info, log_fail
from jwql.utils import monitor_utils
from jwql.database.database_interface import session
from jwql.database.database_interface import NIRSpecTAQueryHistory, NIRSpecTAStats
from jwql.jwql_monitors import monitor_mast


class MSATA():
    """ Class for executint the NIRSpec MSATA monitor.

    This class will search for new MSATA current files in the file systems
    for NIRSpec and will run the monitor on these files. The monitor will
    extract the TA information from the fits file headers and perform all
    statistical measurements. Results will be saved to the MSATA database.

    Attributes
    ----------
    output_dir : str
        Path into which outputs will be placed.

    data_dir : str
        Path into which new dark files will be copied to be worked on.

    aperture : str
        Name of the aperture used for the dark current (i.e.
        "NRS_FULL_MSA", "NRS_S1600A1_SLIT")

    query_start : float
        MJD start date to use for querying MAST.

    query_end : float
        MJD end date to use for querying MAST.

    """


    def __init__(self):
        """ Initialize an instance of the MSATA class """


    def get_tainfo_from_fits(self, fits_file):
        """ Get the TA information from the fits file
        Parameters
        ----------
        fits_file: str
            This is the fits file for a specific MSATA

        Returns
        -------
        msata_info: list, contains main header, and TA extension header and data
        """
        msata = False
        with fits.open(fits_file) as ff:
            # make sure this is a MSATA file
            for hdu in ff:
                if 'MSA_TARG_ACQ' in hdu.name:
                    msata = True
                    break
            if not msata:
                print('\n WARNING! This file is not MSATA: ', fits_file)
                print('  Exiting msata_monitor.py  \n')
                exit()
            main_hdr = ff[0].header
            ta_hdr = ff['MSA_TARG_ACQ'].header
            ta_table = ff['MSA_TARG_ACQ'].data
        msata_info = [main_hdr, ta_hdr, ta_table]
        return msata_info


    def get_msata_data(self, new_filenames):
        """ Get the TA information from the MSATA text table
        Parameters
        ----------
        new_filenames: list
            List of MSATA file names to consider

        Returns
        -------
        msata_df: data frame object
            Pandas data frame containing all MSATA data
        """
        # structure to define required keywords to extract and where they live
        keywds2extract = {'DATE-OBS': {'loc': 'main_hdr', 'alt_key': None, 'name': 'date_obs'},
                          'OBS_ID':  {'loc': 'main_hdr', 'alt_key': None, 'name': 'visit_id'},
                          'FILTER':  {'loc': 'main_hdr', 'alt_key': 'FWA_POS', 'name': 'tafilter'},
                          'DETECTOR':  {'loc': 'main_hdr', 'alt_key': None, 'name': 'detector'},
                          'READOUT':  {'loc': 'main_hdr', 'alt_key': 'READPATT', 'name': 'readout'},
                          'SUBARRAY':  {'loc': 'main_hdr', 'alt_key': None, 'name': 'subarray'},
                          'NUMREFST':  {'loc': 'ta_hdr', 'alt_key': None, 'name': 'num_refstars'},
                          'TASTATUS':  {'loc': 'ta_hdr', 'alt_key': None, 'name': 'ta_status'},
                          'STAT_RSN':  {'loc': 'ta_hdr', 'alt_key': None, 'name': 'status_rsn'},
                          'V2HFOFFS':  {'loc': 'ta_hdr', 'alt_key': None, 'name': 'v2halffacet'},
                          'V3HFOFFS':  {'loc': 'ta_hdr', 'alt_key': None, 'name': 'v3halffacet'},
                          'V2MSACTR':  {'loc': 'ta_hdr', 'alt_key': None, 'name': 'v2msactr'},
                          'V3MSACTR':  {'loc': 'ta_hdr', 'alt_key': None, 'name': 'v3msactr'},
                          'FITXOFFS':  {'loc': 'ta_hdr', 'alt_key': None, 'name': 'lsv2offset'},
                          'FITYOFFS':  {'loc': 'ta_hdr', 'alt_key': None, 'name': 'lsv3offset'},
                          'OFFSTMAG':  {'loc': 'ta_hdr', 'alt_key': None, 'name': 'lsoffsetmag'},
                          'FITROFFS':  {'loc': 'ta_hdr', 'alt_key': None, 'name': 'lsrolloffset'},
                          'FITXSIGM':  {'loc': 'ta_hdr', 'alt_key': None, 'name': 'lsv2sigma'},
                          'FITYSIGM':  {'loc': 'ta_hdr', 'alt_key': None, 'name': 'lsv3sigma'},
                          'ITERATNS':  {'loc': 'ta_hdr', 'alt_key': None, 'name': 'lsiterations'},
                          'GUIDERID':  {'loc': 'ta_hdr', 'alt_key': None, 'name': 'guidestarid'},
                          'IDEAL_X':  {'loc': 'ta_hdr', 'alt_key': None, 'name': 'guidestarx'},
                          'IDEAL_Y':  {'loc': 'ta_hdr', 'alt_key': None, 'name': 'guidestary'},
                          'IDL_ROLL':  {'loc': 'ta_hdr', 'alt_key': None, 'name': 'guidestarroll'},
                          'SAM_X':  {'loc': 'ta_hdr', 'alt_key': None, 'name': 'samx'},
                          'SAM_Y':  {'loc': 'ta_hdr', 'alt_key': None, 'name': 'samy'},
                          'SAM_ROLL':  {'loc': 'ta_hdr', 'alt_key': None, 'name': 'samroll'},
                          'box_peak_value':  {'loc': 'ta_table', 'alt_key': None, 'name': 'box_peak_value'},
                          'reference_star_mag':  {'loc': 'ta_table', 'alt_key': None, 'name': 'reference_star_mag'},
                          'convergence_status':  {'loc': 'ta_table', 'alt_key': None, 'name': 'convergence_status'},
                          'reference_star_number':  {'loc': 'ta_table', 'alt_key': None, 'name': 'reference_star_number'},
                          'lsf_removed_status':  {'loc': 'ta_table', 'alt_key': None, 'name': 'lsf_removed_status'},
                          'lsf_removed_reason':  {'loc': 'ta_table', 'alt_key': None, 'name': 'lsf_removed_reason'},
                          'lsf_removed_x':  {'loc': 'ta_table', 'alt_key': None, 'name': 'lsf_removed_x'},
                          'lsf_removed_y':  {'loc': 'ta_table', 'alt_key': None, 'name': 'lsf_removed_y'},
                          'planned_v2':  {'loc': 'ta_table', 'alt_key': None, 'name': 'planned_v2'},
                          'planned_v3':  {'loc': 'ta_table', 'alt_key': None, 'name': 'planned_v3'}
                         }
        # fill out the dictionary to create the dataframe
        msata_dict = {}
        for fits_file in new_filenames:
            msata_info = self.get_tainfo_from_fits(fits_file)
            main_hdr, ta_hdr, ta_table = msata_info
            for key, key_dict in keywds2extract.items():
                key_name = key_dict['name']
                if key_name not in msata_dict:
                    msata_dict[key_name] = []
                ext = main_hdr
                if key_dict['loc'] == 'ta_hdr':
                    ext = ta_hdr
                if key_dict['loc'] == 'ta_table':
                    ext = ta_table
                try:
                    val = ext[key]
                except:
                    val = ext[key_dict['alt_key']]
                """ UNCOMMENTED THIS BLOCK IN CASE WE DO WANT TO GET RID OF the 999.0 values
                # remove the 999 values for arrays
                if isinstance(val, np.ndarray):
                    if val.dtype.char == 'd' or val.dtype.char == 'f':
                        val = np.where(abs(val) != 999.0, val, 0.0)
                # remove the 999 from single values
                elif not isinstance(val, str):
                    if float(abs(val)) == 999.0:
                        val = 0.0
                """
                msata_dict[key_name].append(val)
        # create the pandas dataframe
        msata_df = pd.DataFrame(msata_dict)
        msata_df.index = msata_df.index + 1
        return msata_df


    def plt_slewsize_vs_time(self, data):
        """ Plot the slew size versus time
        Parameters
        ----------
        data: pandas data frame
            This is the data frame that contains all MSATA.

        Returns
        -------
        plot: bokeh plot object
        """
        # to get the times we need the fits files
        pass


    def plt_status(self, source):
        """ Plot the MSATA status versus time.
        Parameters
        ----------
            source: bokeh data object for plotting
        Returns
        -------
            plot: bokeh plot object
        """
        ta_status, date_obs = source.data['ta_status'], source.data['date_obs']
        # bokeh does not like to plot strings, turn  into binary type
        bool_status, time_arr, status_colors = [], [], []
        for tas, do_str in zip(ta_status, date_obs):
            if 'success' in tas.lower():
                bool_status.append(1)
                status_colors.append('blue')
            else:
                bool_status.append(0)
                status_colors.append('red')
            # convert time string into an array of time (this is in UT)
            t = datetime.fromisoformat(do_str)
            time_arr.append(t)
        # add these to the bokeh data structure
        source.data["time_arr"] = time_arr
        source.data["ta_status_bool"] = bool_status
        source.data["status_colors"] = status_colors
        # create a new bokeh plot
        plot = figure(title="MSATA Status [Succes=1, Fail=0]", x_axis_label='Time',
                      y_axis_label='MSATA Status', x_axis_type='datetime',)
        limits = [-0.5, 1.5]
        plot.circle(x='time_arr', y='ta_status_bool', source=source,
                    color='status_colors', size=7, fill_alpha=0.5)
        hover = HoverTool()
        hover.tooltips=[('Visit ID', '@visit_id'),
                        ('TA status', '@ta_status'),
                        ('Filter', '@tafilter'),
                        ('Readout', '@readout'),
                        ('Date-Obs', '@date_obs'),
                        ('Subarray', '@subarray')
                        ]
        plot.add_tools(hover)
        return plot


    def plt_residual_offsets(self, source):
        """ Plot the residual Least Squares V2 and V3 offsets
        Parameters
        ----------
            source: bokeh data object for plotting
        Returns
        -------
            plot: bokeh plot object
        """
        # create a new bokeh plot
        plot = figure(title="MSATA Least Squares Residual V2-V3 Offsets",
                      x_axis_label='Least Squares Residual V2 Offset',
                      y_axis_label='Least Squares Residual V3 Offset')
        plot.circle(x='lsv2offset', y='lsv3offset', source=source,
                    color="purple", size=7, fill_alpha=0.5)
        plot.x_range = Range1d(-0.5, 0.5)
        plot.y_range = Range1d(-0.5, 0.5)
        # mark origin lines
        vline = Span(location=0, dimension='height', line_color='black', line_width=0.7)
        hline = Span(location=0, dimension='width', line_color='black', line_width=0.7)
        plot.renderers.extend([vline, hline])
        hover = HoverTool()
        hover.tooltips=[('Visit ID', '@visit_id'),
                        ('Filter', '@tafilter'),
                        ('Readout', '@readout'),
                        ('Date-Obs', '@date_obs'),
                        ('Subarray', '@subarray'),
                        ('LS roll offset', '@lsrolloffset'),
                        ('LS V2 offset', '@lsv2offset'),
                        ('LS V3 offset', '@lsv3offset')
                        ]
        plot.add_tools(hover)
        return plot


    def plt_v2offset_time(self, source):
        """ Plot the residual V2 versus time
        Parameters
        ----------
            source: bokeh data object for plotting
        Returns
        -------
            plot: bokeh plot object
        """
        # create a new bokeh plot
        plot = figure(title="MSATA Least Squares V2 Offset vs Time", x_axis_label='Time',
                      y_axis_label='Least Squares Residual V2 Offset', x_axis_type='datetime')
        plot.circle(x='time_arr', y='lsv2offset', source=source,
                    color="blue", size=7, fill_alpha=0.5)
        plot.y_range = Range1d(-0.5, 0.5)
        # mark origin line
        hline = Span(location=0, dimension='width', line_color='black', line_width=0.7)
        plot.renderers.extend([hline])
        hover = HoverTool()
        hover.tooltips=[('Visit ID', '@visit_id'),
                        ('Filter', '@tafilter'),
                        ('Readout', '@readout'),
                        ('Date-Obs', '@date_obs'),
                        ('Subarray', '@subarray'),
                        ('LS roll offset', '@lsrolloffset'),
                        ('LS V2 offset', '@lsv2offset'),
                        ('LS V3 offset', '@lsv3offset')
                        ]
        plot.add_tools(hover)
        return plot


    def plt_v3offset_time(self, source):
        """ Plot the residual V3 versus time
        Parameters
        ----------
            source: bokeh data object for plotting
        Returns
        -------
            plot: bokeh plot object
        """
        # create a new bokeh plot
        plot = figure(title="MSATA Least Squares V3 Offset vs Time", x_axis_label='Time',
                      y_axis_label='Least Squares Residual V3 Offset', x_axis_type='datetime')
        plot.circle(x='time_arr', y='lsv3offset', source=source,
                    color="blue", size=7, fill_alpha=0.5)
        plot.y_range = Range1d(-0.5, 0.5)
        # mark origin line
        hline = Span(location=0, dimension='width', line_color='black', line_width=0.7)
        plot.renderers.extend([hline])
        hover = HoverTool()
        hover.tooltips=[('Visit ID', '@visit_id'),
                        ('Filter', '@tafilter'),
                        ('Readout', '@readout'),
                        ('Date-Obs', '@date_obs'),
                        ('Subarray', '@subarray'),
                        ('LS roll offset', '@lsrolloffset'),
                        ('LS V2 offset', '@lsv2offset'),
                        ('LS V3 offset', '@lsv3offset')
                        ]
        plot.add_tools(hover)
        return plot


    def plt_lsv2v3offsetsigma(self, source):
        """ Plot the residual Least Squares V2 and V3 sigma offsets
        Parameters
        ----------
            source: bokeh data object for plotting
        Returns
        -------
            plot: bokeh plot object
        """
        # create a new bokeh plot
        plot = figure(title="MSATA Least Squares Residual V2-V3 Sigma Offsets",
                      x_axis_label='Least Squares Residual V2 Sigma Offset',
                      y_axis_label='Least Squares Residual V3 Sigma Offset')
        plot.circle(x='lsv2sigma', y='lsv3sigma', source=source,
                    color="purple", size=7, fill_alpha=0.5)
        plot.x_range = Range1d(-0.1, 0.1)
        plot.y_range = Range1d(-0.1, 0.1)
        # mark origin lines
        vline = Span(location=0, dimension='height', line_color='black', line_width=0.7)
        hline = Span(location=0, dimension='width', line_color='black', line_width=0.7)
        plot.renderers.extend([vline, hline])
        hover = HoverTool()
        hover.tooltips=[('Visit ID', '@visit_id'),
                        ('Filter', '@tafilter'),
                        ('Readout', '@readout'),
                        ('Date-Obs', '@date_obs'),
                        ('Subarray', '@subarray'),
                        ('LS roll offset', '@lsrolloffset'),
                        ('LS V2 offset', '@lsv2offset'),
                        ('LS V2 sigma', '@lsv2sigma'),
                        ('LS V3 offset', '@lsv3offset'),
                        ('LS V3 sigma', '@lsv3sigma')
                        ]
        plot.add_tools(hover)
        return plot


    def plt_res_offsets_corrected(self, source):
        """ Plot the residual Least Squares V2 and V3 offsets corrected by the half-facet
        Parameters
        ----------
            source: bokeh data object for plotting
        Returns
        -------
            plot: bokeh plot object
        """
        # create a new bokeh plot
        lsv2offset, lsv3offset = source.data['lsv2offset'], source.data['lsv3offset']
        v2halffacet, v3halffacet = source.data['v2halffacet'], source.data['v3halffacet']
        v2_half_fac_corr = lsv2offset + v2halffacet
        v3_half_fac_corr = lsv3offset + v3halffacet
        # add these to the bokeh data structure
        source.data["v2_half_fac_corr"] = v2_half_fac_corr
        source.data["v3_half_fac_corr"] = v3_half_fac_corr
        plot = figure(title="MSATA Least Squares Residual V2-V3 Offsets Half-facet corrected",
                      x_axis_label='Least Squares Residual V2 Offset + half-facet',
                      y_axis_label='Least Squares Residual V3 Offset + half-facet')
        plot.circle(x='v2_half_fac_corr', y='v3_half_fac_corr', source=source,
                    color="purple", size=7, fill_alpha=0.5)
        plot.x_range = Range1d(-0.5, 0.5)
        plot.y_range = Range1d(-0.5, 0.5)
        # mark origin lines
        vline = Span(location=0, dimension='height', line_color='black', line_width=0.7)
        hline = Span(location=0, dimension='width', line_color='black', line_width=0.7)
        plot.renderers.extend([vline, hline])
        hover = HoverTool()
        hover.tooltips=[('Visit ID', '@visit_id'),
                        ('Filter', '@tafilter'),
                        ('Readout', '@readout'),
                        ('Date-Obs', '@date_obs'),
                        ('Subarray', '@subarray'),
                        ('LS roll offset', '@lsrolloffset'),
                        ('LS V2 offset', '@lsv2offset'),
                        ('LS V3 offset', '@lsv3offset'),
                        ('V2 half-facet', '@v2halffacet'),
                        ('V3 half-facet', '@v3halffacet')
                        ]
        plot.add_tools(hover)
        return plot


    def plt_v2offsigma_time(self, source):
        """ Plot the residual Least Squares V2 sigma Offset versus time
        Parameters
        ----------
            source: bokeh data object for plotting
        Returns
        -------
            plot: bokeh plot object
        """
        # create a new bokeh plot
        plot = figure(title="MSATA Least Squares V2 Sigma Offset vs Time", x_axis_label='Time',
                      y_axis_label='Least Squares Residual V2 Sigma Offset', x_axis_type='datetime')
        plot.circle(x='time_arr', y='lsv2sigma', source=source,
                    color="blue", size=7, fill_alpha=0.5)
        plot.y_range = Range1d(-0.1, 0.1)
        # mark origin line
        hline = Span(location=0, dimension='width', line_color='black', line_width=0.7)
        plot.renderers.extend([hline])
        hover = HoverTool()
        hover.tooltips=[('Visit ID', '@visit_id'),
                        ('Filter', '@tafilter'),
                        ('Readout', '@readout'),
                        ('Date-Obs', '@date_obs'),
                        ('Subarray', '@subarray'),
                        ('LS V2 offset', '@lsv2offset'),
                        ('LS V2 sigma', '@lsv2sigma')
                        ]
        plot.add_tools(hover)
        return plot


    def plt_v3offsigma_time(self, source):
        """ Plot the residual Least Squares V3 Offset versus time
        Parameters
        ----------
            source: bokeh data object for plotting
        Returns
        -------
            p: bokeh plot object
        """
        # create a new bokeh plot
        plot = figure(title="MSATA Least Squares V3 Sigma Offset vs Time", x_axis_label='Time',
                      y_axis_label='Least Squares Residual V3 Sigma Offset', x_axis_type='datetime')
        plot.circle(x='time_arr', y='lsv3sigma', source=source,
                    color="blue", size=7, fill_alpha=0.5)
        plot.y_range = Range1d(-0.1, 0.1)
        # mark origin line
        hline = Span(location=0, dimension='width', line_color='black', line_width=0.7)
        plot.renderers.extend([hline])
        hover = HoverTool()
        hover.tooltips=[('Visit ID', '@visit_id'),
                        ('Filter', '@tafilter'),
                        ('Readout', '@readout'),
                        ('Date-Obs', '@date_obs'),
                        ('Subarray', '@subarray'),
                        ('LS roll offset', '@lsrolloffset'),
                        ('LS V3 offset', '@lsv3offset'),
                        ('LS V3 sigma', '@lsv3sigma')
                        ]
        plot.add_tools(hover)
        return plot


    def plt_roll_offset(self, source):
        """ Plot the residual Least Squares roll Offset versus time
        Parameters
        ----------
            source: bokeh data object for plotting
        Returns
        -------
            plot: bokeh plot object
        """
        # create a new bokeh plot
        plot = figure(title="MSATA Least Squares Roll Offset vs Time", x_axis_label='Time',
                      y_axis_label='Least Squares Residual Roll Offset', x_axis_type='datetime')
        plot.circle(x='time_arr', y='lsrolloffset', source=source,
                    color="blue", size=7, fill_alpha=0.5)
        plot.y_range = Range1d(-25.0, 25.0)
        # mark origin line
        hline = Span(location=0, dimension='width', line_color='black', line_width=0.7)
        plot.renderers.extend([hline])
        hover = HoverTool()
        hover.tooltips=[('Visit ID', '@visit_id'),
                        ('Filter', '@tafilter'),
                        ('Readout', '@readout'),
                        ('Date-Obs', '@date_obs'),
                        ('Subarray', '@subarray'),
                        ('LS roll offset', '@lsrolloffset'),
                        ('LS V2 offset', '@lsv2offset'),
                        ('LS V3 offset', '@lsv3offset')
                        ]
        plot.add_tools(hover)
        return plot


    def plt_lsoffsetmag(self, source):
        """ Plot the residual Least Squares Total Slew Magnitude Offset versus time
        Parameters
        ----------
            source: bokeh data object for plotting
        Returns
        -------
            plot: bokeh plot object
        """
        # create a new bokeh plot
        plot = figure(title="MSATA Least Squares Total Magnitude of the Linear V2, V3 Offset Slew vs Time", x_axis_label='Time',
                   y_axis_label='sqrt((V2_off)**2 + (V3_off)**2)', x_axis_type='datetime')
        plot.circle(x='time_arr', y='lsoffsetmag', source=source,
                 color="blue", size=7, fill_alpha=0.5)
        plot.y_range = Range1d(-0.5, 0.5)
        # mark origin line
        hline = Span(location=0, dimension='width', line_color='black', line_width=0.7)
        plot.renderers.extend([hline])
        hover = HoverTool()
        hover.tooltips=[('Visit ID', '@visit_id'),
                        ('Filter', '@tafilter'),
                        ('Readout', '@readout'),
                        ('Date-Obs', '@date_obs'),
                        ('Subarray', '@subarray'),
                        ('LS roll offset', '@lsrolloffset'),
                        ('LS slew mag offset', '@lsoffsetmag'),
                        ('LS V2 offset', '@lsv2offset'),
                        ('LS V3 offset', '@lsv3offset')
                        ]
        plot.add_tools(hover)
        return plot


    def plt_tot_number_of_stars(self, source):
        """ Plot the total number of stars used versus time
        Parameters
        ----------
            source: bokeh data object for plotting
        Returns
        -------
            plot: bokeh plot object
        """
        # get the number of stars per array
        visit_id, reference_star_number = source.data['visit_id'], source.data['reference_star_number']
        date_obs, time_arr = source.data['date_obs'], source.data['time_arr']
        # create the list of color per visit and tot_number_of_stars
        colors_list, tot_number_of_stars = [], []
        for i, _ in enumerate(visit_id):
            tot_stars = len(reference_star_number[i])
            tot_number_of_stars.append(tot_stars)
            ci = '#%06X' % randint(0, 0xFFFFFF)
            colors_list.append(ci)
        # add these to the bokeh data structure
        source.data["tot_number_of_stars"] = tot_number_of_stars
        source.data["colors_list"] = colors_list
        # create a new bokeh plot
        plot = figure(title="Total Number of Stars vs Time", x_axis_label='Time',
                      y_axis_label='Total number of stars', x_axis_type='datetime')
        plot.circle(x='time_arr', y='tot_number_of_stars', source=source,
                    color='colors_list', size=7, fill_alpha=0.5)
        hover = HoverTool()
        hover.tooltips=[('Visit ID', '@visit_id'),
                        ('Filter', '@tafilter'),
                        ('Readout', '@readout'),
                        ('Date-Obs', '@date_obs'),
                        ('Subarray', '@subarray'),
                        ('LS roll offset', '@lsrolloffset'),
                        ('LS slew mag offset', '@lsoffsetmag'),
                        ('LS V2 offset', '@lsv2offset'),
                        ('LS V3 offset', '@lsv3offset')
        ]
        plot.add_tools(hover)
        return plot


    def plt_mags_time(self, source):
        """ Plot the star magnitudes versus time
        Parameters
        ----------
            source: bokeh data object for plotting
        Returns
        -------
            plot: bokeh plot object
        """
        visit_id = source.data['visit_id']
        lsf_removed_status = source.data['lsf_removed_status']
        lsf_removed_reason = source.data['lsf_removed_reason']
        lsf_removed_x = source.data['lsf_removed_x']
        lsf_removed_y = source.data['lsf_removed_y']
        planned_v2 = source.data['planned_v2']
        planned_v3 = source.data['planned_v3']
        reference_star_number = source.data['reference_star_number']
        visits_stars_mags = source.data['reference_star_mag']
        box_peak_value = source.data['box_peak_value']
        date_obs, time_arr = source.data['date_obs'], source.data['time_arr']
        # create the list of color per visit
        colors_list = []
        # create the structure matching the number of visits and reference stars
        vid, dobs, tarr, star_no, status = [], [], [], [], []
        peaks, visit_mags, stars_v2, stars_v3 = [], [], [], []
        for i, _ in enumerate(visit_id):
            mags, v, d, t, c, s, x, y  = [], [], [], [], [], [], [], []
            ci = '#%06X' % randint(0, 0xFFFFFF)
            for j in range(len(reference_star_number[i])):
                # calculate the pseudo magnitude
                m = -2.5 * np.log(box_peak_value[i][j])
                mags.append(m)
                v.append(visit_id[i])
                d.append(date_obs[i])
                t.append(time_arr[i])
                c.append(ci)
                if 'not_removed' in lsf_removed_status[i][j]:
                    s.append('SUCCESS')
                    x.append(planned_v2[i][j])
                    y.append(planned_v3[i][j])
                else:
                    s.append(lsf_removed_reason[i][j])
                    x.append(lsf_removed_x[i][j])
                    y.append(lsf_removed_y[i][j])
            vid.extend(v)
            dobs.extend(d)
            tarr.extend(t)
            star_no.extend(reference_star_number[i])
            status.extend(s)
            visit_mags.extend(mags)
            colors_list.extend(c)
            stars_v2.extend(x)
            stars_v3.extend(y)
            peaks.extend(box_peak_value[i])
        # now create the mini ColumnDataSource for this particular plot
        mini_source={'vid': vid, 'star_no': star_no, 'status': status,
                     'dobs': dobs, 'tarr': tarr, 'visit_mags': visit_mags,
                     'peaks': peaks, 'colors_list': colors_list,
                     'stars_v2': stars_v2, 'stars_v3': stars_v2
                    }
        mini_source = ColumnDataSource(data=mini_source)
        # create a the bokeh plot
        plot = figure(title="MSATA Star Pseudo Magnitudes vs Time", x_axis_label='Time',
                   y_axis_label='Star  -2.5*log(box_peak)', x_axis_type='datetime')
        plot.circle(x='tarr', y='visit_mags', source=mini_source,
                 color='colors_list', size=7, fill_alpha=0.5)
        plot.y_range.flipped = True
        # add count saturation warning lines
        loc1 = -2.5 * np.log(45000.0)
        loc2 = -2.5 * np.log(50000.0)
        loc3 = -2.5 * np.log(60000.0)
        hline1 = Span(location=loc1, dimension='width', line_color='green', line_width=3)
        hline2 = Span(location=loc2, dimension='width', line_color='yellow', line_width=3)
        hline3 = Span(location=loc3, dimension='width', line_color='red', line_width=3)
        plot.renderers.extend([hline1, hline2, hline3])
        label1 = Label(x=time_arr[-1], y=loc1, y_units='data', text='45000 counts')
        label2 = Label(x=time_arr[-1], y=loc2, y_units='data', text='50000 counts')
        label3 = Label(x=time_arr[-1], y=loc3, y_units='data', text='60000 counts')
        plot.add_layout(label1)
        plot.add_layout(label2)
        plot.add_layout(label3)
        # add hover
        hover = HoverTool()
        hover.tooltips=[('Visit ID', '@vid'),
                        ('Star No.', '@star_no'),
                        ('LS Status', '@status'),
                        ('Date-Obs', '@dobs'),
                        ('Box peak', '@peaks'),
                        ('Pseudo mag', '@visit_mags'),
                        ('Measured V2', '@stars_v2'),
                        ('Measured V3', '@stars_v3')
                        ]
        plot.add_tools(hover)
        return plot


    def mk_plt_layout(self):
        """Create the bokeh plot layout"""
        source = self.msata_data
        source = ColumnDataSource(data=source)
        output_file("msata_layout.html")
        p1 = self.plt_status(source)
        p2 = self.plt_residual_offsets(source)
        p3 = self.plt_res_offsets_corrected(source)
        p4 = self.plt_v2offset_time(source)
        p5 = self.plt_v3offset_time(source)
        p6 = self.plt_lsv2v3offsetsigma(source)
        p7 = self.plt_v2offsigma_time(source)
        p8 = self.plt_v3offsigma_time(source)
        p9 = self.plt_roll_offset(source)
        p10 = self.plt_lsoffsetmag(source)
        p11 = self.plt_mags_time(source)
        p12 = self.plt_tot_number_of_stars(source)
        # make grid
        grid = gridplot([p1, p2, p3, p4, p5, p6, p7, p8, p9, p10, p11, p12],
                        ncols=2, merge_tools=False)
        #show(grid)
        save(grid)


    def most_recent_search(self):
        """Query the query history database and return the information
        on the most recent query for the given 'aperture_name' where
        the msata monitor was executed.

        Returns
        -------
        query_result : float
            Date (in MJD) of the ending range of the previous MAST query
            where the msata monitor was run.
        """
        query = session.query(self.query_table).filter(self.query_table.aperture == self.aperture)

        dates = np.zeros(0)
        for instance in query:
            dates = np.append(dates, instance.end_time_mjd)

        query_count = len(dates)
        if query_count == 0:
            query_result = 59607.0  # a.k.a. Jan 28, 2022 == First JWST images (MIRI)
            logging.info(('\tNo query history for {}. Beginning search date will be set to {}.'
                         .format(self.aperture, query_result)))
        else:
            query_result = np.max(dates)

        return query_result


    @log_fail
    @log_info
    def run(self):
        """The main method. See module docstrings for further details."""
        
        logging.info('Begin logging for msata_monitor')
        
        # Get the output directory and setup a directory to store the data
        self.output_dir = os.path.join(get_config()['outputs'], 'msata_monitor')
        ensure_dir_exists(os.path.join(self.output_dir, 'data'))

        # Use the current time as the end time for MAST query
        self.query_end = Time.now().mjd
        
        # define MSATA variables
        self.instrument = "nirspec"
        self.aperture = "NRS_FULL_MSA"
        
        # Locate the record of the most recent MAST search
        self.query_start = self.most_recent_search()
        logging.info('\tQuery times: {} {}'.format(self.query_start, self.query_end))

        # Query MAST using the aperture and the time of the
        # most recent previous search as the starting time
        new_entries = monitor_utils.mast_query_ta(self.instrument, self.aperture, self.query_start, self.query_end)
        msata_entries = len(new_entries)
        logging.info('\tMAST query has returned {} new MSATA files for {}, {} to run the MSATA monitor.'.format(msata_entries, self.instrument, self.aperture))
        
        # Get full paths to the files
        new_filenames = []
        for file_entry in new_entries:
            try:
                new_filenames.append(filesystem_path(file_entry['filename']))
            except FileNotFoundError:
                logging.warning('\t\tUnable to locate {} in filesystem. Not including in processing.'.format(file_entry['filename']))
        
        # get the data
        self.msata_data = self.get_msata_data(new_filenames)
    
        # make the plots
        self.mk_plt_layout()

        # Update the query history
        new_entry = {'instrument': 'nirspec',
                    'aperture': self.aperture,
                    'start_time_mjd': self.query_start,
                    'end_time_mjd': self.query_end,
                    'files_found': len(new_entries),
                    'entry_date': datetime.now()}
        self.query_table.__table__.insert().execute(new_entry)
        logging.info('\tUpdated the query history table')

        logging.info('MSATA Monitor completed successfully.')

                
if __name__ == '__main__':

    module = os.path.basename(__file__).strip('.py')
    start_time, log_file = monitor_utils.initialize_instrument_monitor(module)

    monitor = MSATA()
    monitor.run()

    monitor_utils.update_monitor_table(module, start_time, log_file)
