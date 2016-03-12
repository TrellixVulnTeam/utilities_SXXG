#!/usr/local/bin/python
# -*- coding: utf-8 -*-

#TODO: Better documentation
#TODO: Support multiple nested sessions within a single archive

"""
SciTran NIMS and SDM archive to folder Reaper conversion utility.

This code will convert a NIMS v1.0 or an SDM tar file (including the DICOMS) to a folder
tree that the SciTran folder_reaper can ingest.

Users can optionally pass in group, project, and subject arguments. If these
arguments are not passed in they are gleaned from the folder structure within
the NIMS archive.

example usage:
    archive_to_folder_reaper.py /path/to/sometar.tar /path/to/place/the/output

"""

import os
import sys
import time
import glob
import gzip
import dicom
import shutil
import zipfile
import tarfile
import logging
import argparse
import subprocess


logging.basicConfig(
            format='%(asctime)s %(levelname)8.8s %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S',
                )
log = logging.getLogger()


def extract_subject_id(root_path, args):
    '''
    If no subjectID is provided as input, we will attempt to extract the ID from a dicom.
    If there are no dicom files then we use the name of the session folder to create a subject ID.
    If there is a dicom file, we read it and use the field that was passed in - if no field was
    passed in then we use values from the following fields, in order: PatientID, PatientName,
    StudyID ('ex' + StudyID).
    '''
    log.info('No subjectID provided - Attempting to extract subject ID from dicom...')
    subject_id = None

    (file_paths, dir_paths) = get_paths(root_path)
    dicom_dirs = [d for d in dir_paths if d.endswith('dicom')]

    # Read the dicom file and return an id from (PatientID - PatientName - StudyDate+StudyTime)
    if dicom_dirs:
        dicom_files = [d for d in file_paths if d.startswith(dicom_dirs[0])]
        dcm = dicom.read_file(dicom_files[0])

        # Use the field that was passed in
        if args.subject_id_field and dcm.get(args.subject_id_field):
            subject_id = dcm.get(args.subject_id_field)

        # Use the PatientID field
        else:
            if dcm.PatientID and not dcm.PatientID == args.group: # Some users put the group in this field
                subject_id = dcm.PatientID
                if subject_id.split('@')[0]:# Check for Reaper sorting string. If there, then split at the '@'
                    subject_id = subject_id.split('@')[0]
                    if subject_id.find(args.group + '/') > 1:# If the group/is still in the name then no subjectID was entered
                        subject_id = None

        # Use the PatientName field
        if not subject_id and dcm.PatientName:
            subject_id = dcm.PatientName.replace('^',' ')
            if subject_id[0] == ' ': # If the first char is a space, remove it
                subject_id = subject_id[1:]
            # FIXME: This could be a proper name (remove it)

        # Use StudyID
        if not subject_id:
            if dcm.StudyID:
                subject_id = 'ex' + dcm.StudyID

    # No dicoms - use the session folder name
    if not subject_id: # This is empty b/c there are no dicoms, or the id field set failed
        log.info('... subjectID could not be extraced from DICOM header - setting subjectID  from session label')
        subject_id = 'sub_' + os.path.basename(dir_paths[3]).replace(' ', '_').replace(':','')

    log.info('... subjectID set to %s' % subject_id)
    return subject_id


def screen_save_montage(dirs):
    screen_saves = [f for f in dirs if f.endswith('Screen_Save')]
    if screen_saves:
        log.info('... %s screen saves to process' % str(len(screen_saves)))
        for d in screen_saves:
            pngs = glob.glob(d + '/*.png')
            montage_name = pngs[0][:-5] + 'montage.png'
            # Build the montage (requires imagemagick)
            os.system('montage -geometry +4+4 ' + " ".join(pngs) + ' ' + montage_name)
            # Move the contents of this folder to the correct acquitision directory
            ss_num = os.path.basename(d).split('_')[0][-2:] # This is the acquisition number we need
            if ss_num[0] == '0': # Drop the leading zero if it's the first char
                ss_num = ss_num[1:]
            for target in dirs:
                if os.path.basename(target).startswith(ss_num + '_'):
                    target_dir = target
                    break
            shutil.move(montage_name, target_dir)
            shutil.rmtree(d) # Remove the screen save folder
        log.info('... done')
    else:
        log.info('... 0 screen saves found')


def extract_dicoms(files, dbtype):
    dicom_arcs = [f for f in files if f.endswith('_dicoms.tgz') or f.endswith('_dicom.tgz')]
    if dicom_arcs:
        log.info('... %s dicom archives to extract' % str(len(dicom_arcs)))
        for f in dicom_arcs:
            utd = untar(f, os.path.dirname(f))
            del_files = ['DIGEST.txt', 'METADATA.json', 'metadata.json', 'digest.txt']
            for df in del_files:
                [os.remove(d) for d in glob.glob(utd + '/' + df)]
            os.rename(utd, os.path.join(os.path.dirname(utd), 'dicom'))
            os.remove(f)
        log.info('... done')
    else:
        log.info('... 0 dicom archives found')


def extract_pfiles(files):
    pfile_arcs = [f for f in files if f.endswith('_pfile.tgz')]
    if pfile_arcs:
        log.info('... %s pfile archives to extract' % str(len(pfile_arcs)))
        for f in pfile_arcs:
            utd = untar(f, os.path.dirname(f))
            [_files, _dirs] = get_paths(utd)
            for p in _files:
                if p.endswith('.7'):
                    gzfile = create_gzip(p, p + '.gz')
                    shutil.move(gzfile, os.path.dirname(utd))
                    shutil.rmtree(utd)
            os.remove(f)
        log.info('... done')
    else:
        log.info('... 0 pfile archives found')


def extract_and_zip_physio(files):
    physio_arcs = [f for f in files if f.endswith('_physio.tgz')]
    if physio_arcs:
        log.info('... %s physio archives to extract' % str(len(physio_arcs)))
        for f in physio_arcs:
            utd = untar(f, os.path.dirname(f))
            create_archive(utd, utd)
            os.rename(utd + '.zip', utd + '.gephysio.zip')
            shutil.rmtree(utd)
            os.remove(f)
    else:
        log.info('... 0 physio archives found')


def extract_physio(files):
    physio_arcs = [f for f in files if f.endswith('.csv.gz')]
    if physio_arcs:
        log.info('... %s physio regressor file(s) to extract' % str(len(physio_arcs)))
        for f in physio_arcs:
            with gzip.open(f, 'rb') as in_file:
                s = in_file.read()
                with open(f[:-3], 'w') as a:
                    a.write(s)
            os.remove(f)
    else:
        log.info('... 0 physio regressors found')


###### UTILITIES ######

def get_paths(root_path):
    file_paths = []
    dir_paths = []
    for (root, dirs, files) in os.walk(root_path):
        for name in files:
            file_paths.append(os.path.join(root, name))
        for name in dirs:
            dir_paths.append(os.path.join(root, name))
    return (file_paths, dir_paths)


def untar(fname, path):
    tar = tarfile.open(fname)
    tar.extractall(path)
    untar_dir = os.path.join(path, (tar.getnames()[0])) # The 0 item is the directory within the tar_file
    tar.close()
    return untar_dir


def create_archive(content, arcname):
    path = content + '.zip'
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED, allowZip64=True) as zf:
        zf.write(content, arcname)
        for fn in os.listdir(content):
            zf.write(os.path.join(content, fn), os.path.join(os.path.basename(arcname), fn))
    return path


def create_gzip(in_file, gz_file):
    if not gz_file:
        gz_file = in_file + '.gz'
    with open(in_file, 'rb') as f_in, gzip.open(gz_file, 'wb') as f_out:
        shutil.copyfileobj(f_in, f_out)
    return gz_file


######################################################################################
def main():
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument('tar_file', help='NIMS Tar File', type=str)
    arg_parser.add_argument('output_path', help='path for untar data', type=str)
    arg_parser.add_argument('-d', '--dbtype', help='Database Type (nims, sdm)', type=str, default='')
    arg_parser.add_argument('-g', '--group', help='Group', type=str, default='')
    arg_parser.add_argument('-p', '--project', help='project', type=str, default='')
    arg_parser.add_argument('-s', '--subject', help='Subject Code', type=str, default='')
    arg_parser.add_argument('-i', '--subject_id_field', help='Look here for the subject id', type=str, default='')
    arg_parser.add_argument('-l', '--loglevel', default='info', help='log level [default=info]')

    args = arg_parser.parse_args()

    log.setLevel(getattr(logging, args.loglevel.upper()))
    log.debug(args)

    # Output directory will be named with the current date and time
    output_path = os.path.join(os.path.realpath(args.output_path), time.strftime('%Y-%m-%d_%H_%M_%S'))


    ## 1. Make the output directory where the tar file will be extracted
    os.mkdir(output_path)


    ## 2. Extract the nims tar file
    log.info('Extracting %s to %s' % (args.tar_file, output_path))
    untar(args.tar_file, output_path)


    ## 3. Generate file paths and directory paths
    log.info('Extracting path and file info in %s' % output_path)
    (file_paths, dir_paths) = get_paths(output_path)


    ## 4. Handle missing arguments
    if not args.dbtype:
        args.dbtype = os.path.basename(dir_paths[0]).lower()
        log.info('No dbtype provided... %s detected' % os.path.basename(dir_paths[0]))
    if not args.group:
        args.group = os.path.basename(dir_paths[1])
    if not args.project:
        args.project = os.path.basename(dir_paths[2])
    if not args.subject:
        get_subject_id = True
    else:
        get_subject_id = False


    ## 5. Remove the 'qa.json' files (UI can't read them)
    for f in file_paths:
        if f.endswith('qa.json'):
            os.remove(f)


    ## 6. Rename: qa file to [...].qa.png and montage to .montage.zip
    for f in file_paths:
        if f.endswith('_qa.png'):
            new_name = f.replace('_qa.png', '.qa.png')
            os.rename(f, new_name)
        if f.endswith('_montage.zip'):
            new_name = f.replace('_montage.zip', '.montage.zip')
            os.rename(f, new_name)


    ## 7. Extract physio regressors (_physio_regressors.csv.gz)
    log.info('Extracting physio regressors...')
    extract_physio(file_paths)


    ## 8. Move _physio.tgz files to gephsio and zip (removing digest .txt)
    log.info('Extracting and repackaging physio data...')
    extract_and_zip_physio(file_paths)


    ## 9. Extract pfiles and remove the digest and metadata files and gzip the file
    log.info('Extracting and repackaging pfiles...')
    extract_pfiles(file_paths)


    ## 10. Extract all the dicom archives and rename to 'dicom'
    log.info('Extracting dicom archives...')
    extract_dicoms(file_paths, args.dbtype)


    ## 11. Create a montage of the screen saves and move them to the correct acquisition
    log.info('Processing screen saves...')
    screen_save_montage(dir_paths)


    ## 12. Get the subjectID (if not passed in)
    if get_subject_id:
        args.subject = extract_subject_id(output_path, args)


    ## 13. Make the folder hierarchy and move the session to it's right place
    log.info('Organizing final file structure...')
    target_path = os.path.join(output_path, args.group, args.project, args.subject)
    os.makedirs(target_path)
    shutil.move(dir_paths[3], target_path) # Move the session to the target
    shutil.rmtree(dir_paths[0]) # Remove the NIMS folder


    log.info("Done.")
    print output_path


if __name__ == '__main__':
    main()
