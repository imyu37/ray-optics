#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright © 2019 Michael J. Hayford
""" module to facilitate first order definition of an optical model

.. Created on Thu May 16 19:57:47 2019

.. codeauthor: Michael J. Hayford
"""

#from collections import namedtuple
#
#GUIHandle = namedtuple('GUIHandle', ['poly', 'bbox'])
#""" tuple grouping together graphics entity and bounding box
#
#    Attributes:
#        poly: poly entity for underlying graphics system (e.g. mpl)
#        bbox: bounding box for poly
#"""

import math

from rayoptics.optical.model_enums import (PupilType, FieldType)


class SpecSheet:
    """ Top level description of the optical model

    Lightweight manager class to manage connections between a model and
    a ui view.

    The main function of AppManager is refresh_gui(). This is called after
    a user input to the gui to update the model and call a refresh function
    for each ui view of that model.

    Attributes:
        conjugates: whether the system works at finite or infinite conjugates,
                    either 'Infinite' or 'Finite'

        power: the optical power of the system

        fld_obj:
        fld_img:
        aper_obj:
        aper_img:

    """

    def __init__(self, conjugates='Infinite', cmd_list=None):
        self.set_conjugates(conjugates)

    def set_conjugates(self, conjugates):
        self.conjugates = conjugates
        if conjugates is 'Infinite':
            self.power_str = 'EFL'
            self.fld_obj_str = 'Object angle'
            self.fld_img_str = 'Image height'
            self.aper_obj_str = 'Ent Pupil Diameter'
            self.aper_img_str = 'f/#'
        elif conjugates is 'Finite':
            self.power_str = 'magnification'
            self.fld_obj_str = 'Object height'
            self.fld_img_str = 'Image height'
            self.aper_obj_str = 'Object NA'
            self.aper_img_str = 'NA'

    def do_infinite_conj(self, efl, fld, aper):
        if aper.pupil_type == PupilType.EPD:
            slp0 = aper.value/obj2enp_dist
        if pupil.pupil_type == PupilType.NAO:
            slp0 = n_0*math.tan(math.asin(pupil.value/n_0))
        if pupil.pupil_type == PupilType.FNO:
            slpk = -1./(2.0*pupil.value)
            slp0 = slpk/red
        if pupil.pupil_type == PupilType.NA:
            slpk = n_k*math.tan(math.asin(pupil.value/n_k))
            slp0 = slpk/red
    
            pass

    def do_aperture_spec_to_efl(aper1, aper2):
        n_0 = 1.0
        n_k = 1.0
        if aper1[0] == PupilType.EPD:
            epd = aper1[1]
            if aper2[0] == PupilType.FNO:
                fno = aper2[1]
                efl = epd * fno
            if aper2[0] == PupilType.NA:
                na = aper2[1]
                slpk = n_k*math.tan(math.asin(na/n_k))
                efl = (epd/2.0)/slpk
#        if aper1[0] == PupilType.NAO:
#            nao = aper1[1]
#            slp0 = n_0*math.tan(math.asin(pupil.value/n_0))
#            if aper2[0] == PupilType.FNO:
#                fno = aper2[1]
#                slpk =
#                efl = epd * fno
#            if aper2[0] == PupilType.NA:
#                na = aper2[1]
#                slpk = n_k*math.tan(math.asin(na/n_k))
#                efl = (epd/2.0)/slpk
        if aper1[0] == PupilType.FNO:
            fno = aper1[1]
            if aper2[0] == PupilType.EPD:
                epd = aper2[1]
                efl = epd * fno
        if aper1[0] == PupilType.NA:
            na = aper1[1]
            slpk = n_k*math.tan(math.asin(na/n_k))
            if aper2[0] == PupilType.EPD:
                epd = aper2[1]
                efl = (epd/2.0)/slpk
        return efl

    def get_aperture_spec_from_mag(mag, aper1, aper2):
        n_0 = 1.0
        n_k = 1.0
        if aper1[0] == PupilType.EPD:
            epd = aper1[1]
            if aper2[0] == PupilType.FNO:
                fno = efl/epd
                aper = (PupilType.FNO, fno)
            if aper2[0] == PupilType.NA:
                slpk = -(epd/2.0)/efl
                na = n_k*math.sin(math.atan(slpk/n_k))
                aper = (PupilType.NA, na)
#        if aper1[0] == PupilType.NAO:
#            nao = aper1[1]
#            slp0 = n_0*math.tan(math.asin(pupil.value/n_0))
#            if aper2[0] == PupilType.FNO:
#                fno = aper2[1]
#                slpk = 
#                efl = epd * fno 
#            if aper2[0] == PupilType.NA:
#                na = aper2[1]
#                slpk = n_k*math.tan(math.asin(na/n_k))
#                efl = (epd/2.0)/slpk
        if aper1[0] == PupilType.FNO:
            fno = aper1[1]
            if aper2[0] == PupilType.EPD:
                epd = efl/fno
                aper = (PupilType.EPD, epd)
        if aper1[0] == PupilType.NA:
            na = aper1[1]
            slpk = n_k*math.tan(math.asin(na/n_k))
            if aper2[0] == PupilType.EPD:
                epd = 2*slpk*efl
                aper = (PupilType.EPD, epd)
        return aper

    def get_aperture_spec_from_efl(efl, aper1, aper2):
        n_0 = 1.0
        n_k = 1.0
        if aper1[0] == PupilType.EPD:
            epd = aper1[1]
            if aper2[0] == PupilType.FNO:
                fno = efl/epd
                aper = (PupilType.FNO, fno)
            if aper2[0] == PupilType.NA:
                slpk = -(epd/2.0)/efl
                na = n_k*math.sin(math.atan(slpk/n_k))
                aper = (PupilType.NA, na)
#        if aper1[0] == PupilType.NAO:
#            nao = aper1[1]
#            slp0 = n_0*math.tan(math.asin(pupil.value/n_0))
#            if aper2[0] == PupilType.FNO:
#                fno = aper2[1]
#                slpk = 
#                efl = epd * fno 
#            if aper2[0] == PupilType.NA:
#                na = aper2[1]
#                slpk = n_k*math.tan(math.asin(na/n_k))
#                efl = (epd/2.0)/slpk
        if aper1[0] == PupilType.FNO:
            fno = aper1[1]
            if aper2[0] == PupilType.EPD:
                epd = efl/fno
                aper = (PupilType.EPD, epd)
        if aper1[0] == PupilType.NA:
            na = aper1[1]
            slpk = n_k*math.tan(math.asin(na/n_k))
            if aper2[0] == PupilType.EPD:
                epd = 2*slpk*efl
                aper = (PupilType.EPD, epd)
        return aper

    def do_field_spec_to_efl(fld1, fld2):
        if fld1[0] == FieldType.OBJ_ANG:
            max_fld = fld1[1]
            slpbar0 = math.tan(math.radians(max_fld))
            if fld1[0] == FieldType.IMG_HT:
                img_ht = fld2[1]
                efl = img_ht/slpbar0
        if fld1[0] == FieldType.IMG_HT:
            img_ht = fld1[1]
            if fld2[0] == FieldType.OBJ_ANG:
                max_fld = fld2[1]
                slpbar0 = math.tan(math.radians(max_fld))
                efl = img_ht/slpbar0
        return efl


dispatch = {
  (PupilType.EPD, PupilType.FNO): SpecSheet.do_aperture_spec_to_efl,
  (PupilType.EPD, PupilType.NA): SpecSheet.do_aperture_spec_to_efl,
  (PupilType.NAO, PupilType.FNO): SpecSheet.do_aperture_spec_to_efl,
  (PupilType.NAO, PupilType.NA): SpecSheet.do_aperture_spec_to_efl,
  (FieldType.OBJ_ANG, FieldType.IMG_HT): SpecSheet.do_field_spec_to_efl,
  (FieldType.OBJ_HT, FieldType.IMG_HT): SpecSheet.do_field_spec_to_efl,
  }