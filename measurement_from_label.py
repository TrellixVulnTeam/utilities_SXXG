#!/usr/bin/env python
'''
Infer acquisition measurement type by parsing the description label.


Example usage:

    ## Update acquisition measurement in the DB
    labels=list(db.acquisitions.find({},['label']))
    labels_only = []
    for l in labels:
        labels_only.append(l['label'])

    unique_labels = set(labels_only)
    uls = list(unique_labels)

    for l in uls:
        measurement = infer_measurement(l)
        db.acquisitions.update_many({'label': l}, {'$set': {'measurement': measurement}})

'''

import re

# Anatomy, T1
def is_anatomy_t1(label):
    regexes = [
        re.compile('(?=.*t1)(?![inplane])', re.IGNORECASE),
        re.compile('spgr', re.IGNORECASE),
        re.compile('tfl', re.IGNORECASE),
        re.compile('mprage', re.IGNORECASE),
        re.compile('(?=.*mm)(?=.*iso)', re.IGNORECASE),
        re.compile('(?=.*mp)(?=.*rage)', re.IGNORECASE)
    ]
    return regex_search_label(regexes, label)

# Anatomy, T2
def is_anatomy_t2(label):
    regexes = [
        re.compile('t2', re.IGNORECASE)
    ]
    return regex_search_label(regexes, label)

# Aanatomy, Inplane
def is_anatomy_inplane(label):
    regexes = [
        re.compile('inplane', re.IGNORECASE)
    ]
    return regex_search_label(regexes, label)

# Anatomy, other
def is_anatomy(label):
    regexes = [
        re.compile('(?=.*IR)(?=.*EPI)', re.IGNORECASE),
        re.compile('flair', re.IGNORECASE)
    ]
    return regex_search_label(regexes, label)

# Diffusion
def is_diffusion(label):
    regexes = [
        re.compile('dti', re.IGNORECASE),
        re.compile('dwi', re.IGNORECASE),
        re.compile('diff_', re.IGNORECASE),
        re.compile('diffusion', re.IGNORECASE),
        re.compile('(?=.*diff)(?=.*dir)', re.IGNORECASE),
        re.compile('hardi', re.IGNORECASE)
        ]
    return regex_search_label(regexes, label)

# Diffusion - Derived
def is_diffusion_derived(label):
    regexes = [
        re.compile('_ADC$', re.IGNORECASE),
        re.compile('_TRACEW$', re.IGNORECASE),
        re.compile('_ColFA$', re.IGNORECASE),
        re.compile('_FA$', re.IGNORECASE),
        re.compile('_EXP$', re.IGNORECASE)
        ]
    return regex_search_label(regexes, label)

# Functional
def is_functional(label):
    regexes = [
        re.compile('functional', re.IGNORECASE),
        re.compile('fmri', re.IGNORECASE),
        re.compile('bold', re.IGNORECASE),
        re.compile('resting', re.IGNORECASE),
        re.compile('(?=.*rest)(?=.*state)', re.IGNORECASE),
        # NON-STANDARD
        re.compile('go-no-go', re.IGNORECASE),
        re.compile('emoreg', re.IGNORECASE),
        re.compile('conscious', re.IGNORECASE),
        re.compile('^REST$')
        ]
    return regex_search_label(regexes, label)

# Functional, Derived
def is_functional_derived(label):
    regexes = [
        re.compile('mocoseries', re.IGNORECASE),
        re.compile('GLM$', re.IGNORECASE),
        re.compile('t-map', re.IGNORECASE)
        ]
    return regex_search_label(regexes, label)

# Localizer
def is_localizer(label):
    regexes = [
        re.compile('localizer', re.IGNORECASE),
        re.compile('survey', re.IGNORECASE),
        re.compile('loc\.', re.IGNORECASE),
        re.compile(r'\bscout\b', re.IGNORECASE),
        re.compile('(?=.*plane)(?=.*loc)', re.IGNORECASE),
        re.compile('(?=.*plane)(?=.*survey)', re.IGNORECASE),
        re.compile('3-plane', re.IGNORECASE),
        re.compile('^loc*', re.IGNORECASE)
        ]
    return regex_search_label(regexes, label)

# Shim
def is_shim(label):
    regexes = [
        re.compile('(?=.*HO)(?=.*shim)', re.IGNORECASE), # Contians 'ho' and 'shim'
        re.compile(r'\bHOS\b', re.IGNORECASE),
        re.compile('_HOS_', re.IGNORECASE),
        re.compile('.*shim', re.IGNORECASE)
        ]
    return regex_search_label(regexes, label)

# Fieldmap
def is_fieldmap(label):
    regexes = [
        re.compile('(?=.*field)(?=.*map)', re.IGNORECASE)
        ]
    return regex_search_label(regexes, label)

# Calibration
def is_calibration(label):
    regexes = [
        re.compile('(?=.*asset)(?=.*cal)', re.IGNORECASE),
        re.compile('^asset$', re.IGNORECASE),
        re.compile('calibration', re.IGNORECASE)
        ]
    return regex_search_label(regexes, label)

# Coil Survey
def is_coil_survey(label):
    regexes = [
        re.compile('(?=.*coil)(?=.*survey)', re.IGNORECASE)
        ]
    return regex_search_label(regexes, label)

# Perfusion: Arterial Spin Labeling
def is_perfusion(label):
    regexes = [
        re.compile('asl', re.IGNORECASE),
        re.compile('(?=.*blood)(?=.*flow)', re.IGNORECASE),
        re.compile('(?=.*art)(?=.*spin)', re.IGNORECASE)
        ]
    return regex_search_label(regexes, label)

# Proton Density
def is_proton_density(label):
    regexes = [
        re.compile('^PD$'),
        re.compile('(?=.*proton)(?=.*density)', re.IGNORECASE)
        ]
    return regex_search_label(regexes, label)

# Phase Map
def is_phase_map(label):
    regexes = [
        re.compile('(?=.*phase)(?=.*map)', re.IGNORECASE),
        re.compile('^phase$', re.IGNORECASE)
        ]
    return regex_search_label(regexes, label)



# Utility:  Check a list of regexes for truthyness
def regex_search_label(regexes, label):
    if any(regex.search(label) for regex in regexes):
            return True
    else:
            return False

#######TODO#######

# Spectroscopy
def is_spectroscopy(label):
    pass


# Call all functions to determine new label
def infer_measurement(label):
    if is_anatomy_inplane(label):
        measurement = 'anatomy_inplane'
    elif is_diffusion(label):
        measurement = 'diffusion'
    elif is_anatomy_t1(label):
        measurement = 'anatomy_t1w'
    elif is_anatomy_t2(label):
        measurement = 'anatomy_t2w'
    elif is_anatomy(label):
        measurement = 'anatomy_ir'
    elif is_functional(label):
        measurement = 'functional'
    elif is_diffusion_derived(label):
        measurement = 'diffusion_map'
    elif is_localizer(label):
        measurement = 'localizer'
    elif is_fieldmap(label):
        measurement = 'field_map'
    elif is_shim(label):
        measurement = 'high_order_shim'
    elif is_calibration(label):
        measurement = 'Calibration'
    elif is_functional_derived(label):
        measurement = 'functional_map'
    elif is_coil_survey(label):
        measurement = 'coil_survey'
    elif is_proton_density(label):
        measurement = 'anatomy_pd'
    elif is_perfusion(label):
        measurement = 'perfusion'
    elif is_spectroscopy(label):
        measurement = 'spectroscopy'
    elif is_phase_map(label):
        measurement = 'phase_map'
    else:
        measurement = 'unknown'

    # Check the measurement
    #if measurement == 'unknown':
    #    print label.strip('\n') + ' --->>>> ' + measurement
    return measurement

