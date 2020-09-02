#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright © 2020 Michael J. Hayford
"""

.. Created on Fri Jul 31 15:40:21 2020

.. codeauthor: Michael J. Hayford
"""
import logging
import math
import json
import requests

import rayoptics.optical.opticalmodel as opticalmodel
from rayoptics.optical.model_enums import DimensionType as dt
from rayoptics.optical.model_enums import DecenterType as dec
from rayoptics.elem.surface import (DecenterData, Circular, Rectangular,
                                    Elliptical)
from rayoptics.elem import profiles
from rayoptics.seq.medium import (glass_encode, Medium, Air,
                                  Glass, InterpolatedGlass)
from rayoptics.raytr.opticalspec import Field
from rayoptics.util.misc_math import isanumber
import rayoptics.zemax.zmx2ro as zmx2ro
import rayoptics.oprops.thinlens as thinlens

from opticalglass import glassfactory as gfact
from opticalglass import glasserror

_glass_handler = None
_cmd_not_handled = None
_track_contents = None

class Counter(dict):
    def __missing__(self, key):
        return 0


def read_lens_file(filename, **kwargs):
    ''' given a Zemax .zmx filename, return an OpticalModel  '''
    with filename.open() as file:
        inpt = file.read()

    opt_model, info = read_lens(filename, inpt, **kwargs)

    return opt_model, info


def read_lens_url(url, **kwargs):
    ''' given a url to a Zemax file, return an OpticalModel  '''
    global _track_contents
    r = requests.get(url, allow_redirects=True)

    apparent_encoding = r.apparent_encoding
    r.encoding = r.apparent_encoding
    inpt = r.text

    opt_model, info = read_lens(None, inpt, **kwargs)
    _track_contents['encoding'] = apparent_encoding

    return opt_model, info


def read_lens(filename, inpt, **kwargs):
    ''' given inpt str of a Zemax .zmx file, return an OpticalModel  '''
    global _glass_handler, _cmd_not_handled, _track_contents
    _cmd_not_handled = Counter()
    _track_contents = Counter()
    logging.basicConfig(filename='zmx_read_lens.log',
                        filemode='w',
                        level=logging.DEBUG)

    # create an empty optical model; all surfaces will come from .zmx file
    opt_model = opticalmodel.OpticalModel(do_init=False)

    input_lines = inpt.splitlines()

    _glass_handler = GlassHandler(filename)

    for i, line in enumerate(input_lines):
        process_line(opt_model, line, i+1)

    post_process_input(opt_model, filename, **kwargs)
    _glass_handler.save_replacements()

    opt_model.update_model()

    info = _track_contents, _glass_handler.glasses_not_found
    return opt_model, info


def process_line(opt_model, line, line_no):
    global _glass_handler, _cmd_not_handled, _track_contents
    sm = opt_model.seq_model
    osp = opt_model.optical_spec
    cur = sm.cur_surface
    if not line.strip():
        return
    line = line.strip().split(" ", 1)
    cmd = line[0]
    inputs = len(line) == 2 and line[1] or ""
    if cmd == "UNIT":
        dim = inputs.split()[0]
        if dim == 'MM':
            dim = dt.MM
        elif dim == 'IN' or dim == 'INCH':
            dim = dt.IN
        opt_model.system_spec.dimensions = dim
    elif cmd == "NAME":
        opt_model.system_spec.title = inputs.strip("\"")
    elif cmd == "NOTE":
        opt_model.note = inputs.strip("\"")
    elif cmd == "VERS":
        _track_contents["VERS"] = inputs.strip("\"")
    elif cmd == "SURF":
        s, g = sm.insert_surface_and_gap()
    elif cmd == "CURV":
        s = sm.ifcs[cur]
        if s.z_type != 'PARAXIAL':
            s.profile.cv = float(inputs.split()[0])
    elif cmd == "DISZ":
        g = sm.gaps[cur]
        g.thi = float(inputs)

    elif _glass_handler(sm, cur, cmd, inputs):
        pass

    elif cmd == "DIAM":
        s = sm.ifcs[cur]
        s.set_max_aperture(float(inputs.split()[0]))
    elif cmd == "STOP":
        sm.set_stop()

    elif cmd == "WAVM":  # WAVM 1 0.55000000000000004 1
        sr = osp.spectral_region
        inputs = inputs.split()
        new_wvl = float(inputs[1])*1e+3
        if new_wvl not in sr.wavelengths:
            sr.wavelengths.append(new_wvl)
            sr.spectral_wts.append(float(inputs[2]))  # needs check
    # WAVL 0.4861327 0.5875618 0.6562725
    # WWGT 1 1 1
    elif cmd == "WAVL":
        sr = osp.spectral_region
        sr.wavelengths = [float(i)*1e+3 for i in inputs.split() if i]
    elif cmd == "WWGT":
        sr = osp.spectral_region
        sr.spectral_wts = [float(i)*1e+3 for i in inputs.split() if i]

    elif pupil_data(opt_model, cmd, inputs):
        pass

    elif field_spec_data(opt_model, cmd, inputs):
        pass

    elif handle_types_and_params(opt_model, cur, cmd, inputs):
        pass

    elif cmd in ("OPDX",  # opd
                 "RAIM",  # ray aiming
                 "CONF",  # configurations
                 "PUPD",  # pupil
                 "EFFL",  # focal lengths
                 "MODE",  # mode
                 "HIDE",  # surface hide
                 "MIRR",  # surface is mirror
                 "PARM",  # aspheric parameters
                 "SQAP",  # square aperture?
                 "XDAT", "YDAT",  # xy toroidal data
                 "OBNA",  # object na
                 "PKUP",  # pickup
                 "MAZH", "CLAP", "PPAR", "VPAR", "EDGE", "VCON",
                 "UDAD", "USAP", "TOLE", "PFIL", "TCED", "FNUM",
                 "TOL", "MNUM", "MOFF", "FTYP", "SDMA", "GFAC",
                 "PUSH", "PICB", "ROPD", "PWAV", "POLS", "GLRS",
                 "BLNK", "COFN", "NSCD", "GSTD", "DMFS", "ISNA",
                 "VDSZ", "ENVD", "ZVDX", "ZVDY", "ZVCX", "ZVCY",
                 "ZVAN", "WWGN",
                 "WAVN", "MNCA", "MNEA",
                 "MNCG", "MNEG", "MXCA", "MXCG", "RGLA", "TRAC",
                 "FLAP", "TCMM", "FLOA", "PMAG", "TOTR", "SLAB",
                 "POPS", "COMM", "PZUP", "LANG", "FIMP", "COAT",
                 ):
        logging.info('Line %d: Command %s not supported', line_no, cmd)
    else:
        # don't recognize this cmd, record # of times encountered
        _cmd_not_handled[cmd] += 1


def post_process_input(opt_model, filename, **kwargs):
    global _track_contents
    sm = opt_model.seq_model
    sm.gaps.pop()

    if opt_model.system_spec.title == '' and filename is not None:
        fname_full = str(filename)
        _, cat, fname = fname_full.rsplit('/', 2)
        title = "{:s}: {:s}".format(cat, fname)
        opt_model.system_spec.title = title

    conj_type = 'finite'
    if math.isinf(sm.gaps[0].thi):
        sm.gaps[0].thi = 1e10
        conj_type = 'infinite'
    _track_contents['conj type'] = conj_type

    sm.ifcs[0].label = 'Obj'
    sm.ifcs[-1].label = 'Img'
    _track_contents['# surfs'] = len(sm.ifcs)

    do_post_processing = False
    if do_post_processing:
        if kwargs.get('do_bend', True):
            zmx2ro.apply_fct_to_sm(opt_model, zmx2ro.convert_to_bend)
        if kwargs.get('do_dar', True):
            zmx2ro.apply_fct_to_sm(opt_model, zmx2ro.convert_to_dar)
        if kwargs.get('do_remove_null_sg', True):
            zmx2ro.apply_fct_to_sm(opt_model, zmx2ro.remove_null_sg)
        if kwargs.get('do_collapse_cb', True):
            zmx2ro.apply_fct_to_sm(opt_model, zmx2ro.collapse_coordbrk)

    osp = opt_model.optical_spec
    sr = osp.spectral_region
    if len(sr.wavelengths) > 1:
        if sr.wavelengths[-1] == 550.0:
            sr.wavelengths.pop()
            sr.spectral_wts.pop()
    sr.reference_wvl = len(sr.wavelengths)//2
    _track_contents['# wvls'] = len(sr.wavelengths)

    fov = osp.field_of_view
    _track_contents['fov'] = fov.key

    max_fld, max_fld_idx = fov.max_field()
    fov.fields = [f for f in fov.fields[:max_fld_idx+1]]
    _track_contents['# fields'] = len(fov.fields)
    # switch vignetting definition to asymmetric vly, vuy style
    # need to verify this is how this works
    for f in fov.fields:
        # I think this is probably "has one has all", but we'll test all TBS
        if hasattr(f, 'vcx') and hasattr(f, 'vdx'):
            f.vlx = f.vcx + f.vdx
            f.vux = f.vcx - f.vdx
        if hasattr(f, 'vcy') and hasattr(f, 'vdy'):
            f.vly = f.vcy + f.vdy
            f.vuy = f.vcy - f.vdy


def log_cmd(label, cmd, inputs):
    logging.debug("%s: %s %s", label, cmd, str(inputs))


def handle_types_and_params(optm, cur, cmd, inputs):
    global _track_contents
    if cmd == "TYPE":
        ifc = optm.seq_model.ifcs[cur]
        typ = inputs.split()[0]
        # useful to remember the Type of Zemax surface
        ifc.z_type = typ
        _track_contents[typ] += 1
        if typ == 'EVENASPH':
            cur_profile = ifc.profile
            new_profile = profiles.mutate_profile(cur_profile,
                                                  'EvenPolynomial')
            ifc.profile = new_profile
        elif typ == 'TOROIDAL':
            cur_profile = ifc.profile
            new_profile = profiles.mutate_profile(cur_profile,
                                                  'YToroid')
            ifc.profile = new_profile
        elif typ == 'COORDBRK':
            ifc.decenter = DecenterData(dec.LOCAL)
        elif typ == 'PARAXIAL':
            ifc = thinlens.ThinLens()
            ifc.z_type = typ
            optm.seq_model.ifcs[cur] = ifc
    elif cmd == "CONI":
        _track_contents["CONI"] += 1
        ifc = optm.seq_model.ifcs[cur]
        cur_profile = ifc.profile
        if not hasattr(cur_profile, 'cc'):
            ifc.profile = profiles.mutate_profile(cur_profile, 'Conic')
        ifc.profile.cc = float(inputs.split()[0])
    elif cmd == "PARM":
        ifc = optm.seq_model.ifcs[cur]
        i, param_val = inputs.split()
        i = int(i)
        param_val = float(param_val)
        if ifc.z_type == 'COORDBRK':
            if i == 1:
                ifc.decenter.dec[0] = param_val
            elif i == 2:
                ifc.decenter.dec[1] = param_val
            elif i == 3:
                ifc.decenter.euler[0] = param_val
            elif i == 4:
                ifc.decenter.euler[1] = param_val
            elif i == 5:
                ifc.decenter.euler[2] = param_val
            elif i == 6:
                if param_val != 0:
                    ifc.decenter.self.dtype = dec.REV
            ifc.decenter.update()
        elif ifc.z_type == 'EVENASPH':
            ifc.profile.coefs.append(param_val)
        elif ifc.z_type == 'PARAXIAL':
            if i == 1:
                ifc.optical_power = 1/param_val
        elif ifc.z_type == 'TOROIDAL':
            if i == 1:
                ifc.profile.rR = param_val
            elif i > 1:
                ifc.profile.coefs.append(param_val)
    else:
        return False
    return True


def pupil_data(optm, cmd, inputs):
    # FNUM 2.1 0
    # OBNA 1.5E-1 0
    # ENPD 20
    global _track_contents
    pupil = optm.optical_spec.pupil
    if cmd == 'FNUM':
        pupil.key = 'aperture', 'image', 'f/#'
    elif cmd == 'OBNA':
        pupil.key = 'aperture', 'object', 'NA'
    elif cmd == 'ENPD':
        pupil.key = 'aperture', 'object', 'pupil'
    else:
        return False

    _track_contents['pupil'] = pupil.key

    pupil.value = float(inputs.split()[0])

    log_cmd("pupil_data", cmd, inputs)

    return True


def field_spec_data(optm, cmd, inputs):
    # XFLN 0 0 0 0 0 0 0 0 0 0 0 0
    # YFLN 0 8.0 1.36E+1 0 0 0 0 0 0 0 0 0
    # FWGN 1 1 1 1 1 1 1 1 1 1 1 1
    # VDXN 0 0 0 0 0 0 0 0 0 0 0 0
    # VDYN 0 0 0 0 0 0 0 0 0 0 0 0
    # VCXN 0 0 0 0 0 0 0 0 0 0 0 0
    # VCYN 0 0 0 0 0 0 0 0 0 0 0 0
    # VANN 0 0 0 0 0 0 0 0 0 0 0 0

    # older files (perhaps?)
    # XFLD 0 0 0
    # YFLD 0 35 50
    # FWGT 1 1 1
    global _track_contents

    fov = optm.optical_spec.field_of_view
    if cmd == 'XFLN' or cmd == 'YFLN' or cmd == 'XFLD' or cmd == 'YFLD':
        attr = cmd[0].lower()
    elif cmd == 'FTYP':
        ftyp = int(inputs.split()[0])
        _track_contents["FTYP"] = inputs
        if ftyp == 0:
            fov.key = 'field', 'object', 'angle'
        elif ftyp == 1:
            fov.key = 'field', 'object', 'height'
        elif ftyp == 2:
            fov.key = 'field', 'image', 'height'
        elif ftyp == 3:
            fov.key = 'field', 'image', 'height'
        return True
    elif cmd == 'VDXN' or cmd == 'VDYN':
        attr = 'vd' + cmd[2].lower()
    elif cmd == 'VCXN' or cmd == 'VCYN':
        attr = 'vc' + cmd[2].lower()
    elif cmd == 'VANN':
        attr = 'van'
    elif cmd == 'FWGN' or cmd == 'FWGT':
        attr = 'wt'
    else:
        return False

    inputs = inputs.split()

    if len(fov.fields) != len(inputs):
        fov.fields = [Field() for f in range(len(inputs))]

    for i, f in enumerate(fov.fields):
        f.__setattr__(attr, float(inputs[i]))

    log_cmd("field_spec_data", cmd, inputs)

    return True


class GlassHandler():
    """Handle glass restoration during Zemax import.

    This class handles the GCAT and GLAS commands found in .zmx files. If the
    glass can be matched up with an existing :mod:`opticalglass` catalog, the
    glass is instantiated and entered into the model. If the glass cannot be
    found, a search for a .smx file of the same name as the .zmx file is made.
    If found, it is a JSON file with a dict that provides an eval() string to
    create an instance to replace the missing Zemax glass name. If this file
    isn't found, it is created and contains a JSON template of a dict that has
    the missing glass names as keys; the values are the number of times the
    glass occurs in the file. Thes values should be replaced with the desired
    eval() string to create a replacement glass.
    """

    def __init__(self, filename):
        self.glass_catalogs = []
        self.glasses_not_found = Counter()
        self.filename = None
        if filename:
            self.filename = filename.with_suffix('.smx')
            self.glasses_not_found = self.load_replacements(self.filename)
        self.no_replacements = not self.glasses_not_found

    def load_replacements(self, filename):
        glasses_not_found = Counter()
        if filename.exists():
            with filename.open('r') as file:
                glasses_not_found = json.load(file)
        return glasses_not_found

    def save_replacements(self):
        if self.glasses_not_found and self.filename:
            fname = self.filename.name.rsplit('.', 1)[0]
            fname += '_tmpl.smx'
            self.filename = self.filename.with_name(fname)
            with self.filename.open('w') as file:
                json.dump(self.glasses_not_found, file)

    def __call__(self, sm, cur, cmd, inputs):
        """ process GLAS command for fictitious, catalog glass or mirror"""
        global _track_contents
        if cmd == "GCAT":
            inputs = inputs.split()
            self.glass_catalogs = inputs
            _track_contents["GCAT"] = inputs
            return True
        elif cmd == "GLAS":
            g = sm.gaps[cur]
            inputs = inputs.split()
            name = inputs[0]
            medium = None
            if name == 'MIRROR':
                sm.ifcs[cur].interact_mode = 'reflect'
                g.medium = sm.gaps[cur-1].medium
                _track_contents[name] += 1
                return True
            elif name == '___BLANK':
                nd = float(inputs[3])
                vd = float(inputs[4])
                g.medium = Glass(nd=nd, vd=vd, mat=glass_encode(nd, vd))
                _track_contents[name] += 1
                return True
            elif isanumber(name):
                if len(name) == 6:
                    # process as a 6 digit code, no decimal point
                    nd = 1 + float(name[:3])/1000
                    vd = float(name[3:])/10
                    g.medium = Glass(nd, vd, mat=name)
                    _track_contents['6 digit code'] += 1
                    return True
            else:
                try:
                    medium = gfact.create_glass(name, gfact._cat_names)
                except glasserror.GlassNotFoundError:
                    pass
                else:
                    g.medium = medium
                    _track_contents['glass found'] += 1
                    return True

                medium = self.handle_glass_not_found(name)
                if medium is None:
                    _track_contents['glass not found'] += 1
                    medium = Medium(1.5, 'glass')
                g.medium = medium
                return True
        else:
            return False

    def handle_glass_not_found(self, name):
        """Record missing glasses or create new replacement glass instances."""

        """Import all supported glass catalogs."""
        from opticalglass.cdgm import CDGMGlass
        from opticalglass.hikari import HikariGlass
        from opticalglass.hoya import HoyaGlass
        from opticalglass.ohara import OharaGlass
        from opticalglass.schott import SchottGlass
        from opticalglass.sumita import SumitaGlass
        from opticalglass.buchdahl import Buchdahl

        if self.no_replacements:                # track the number of times
            self.glasses_not_found[name] += 1   # each missing glass is used
            return None

        else:  # create a new instance of the replacement glass
            if name in self.glasses_not_found:
                return eval(self.glasses_not_found[name])
            else:
                return None
