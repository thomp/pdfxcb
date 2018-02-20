#!/usr/bin/python
# -*- coding: utf-8 -*-

# (c) 2018 David A. Thompson <pdfxcb.thomp@mailhero.io>
#
# This file is part of pdfxcb
#
# pdfxcb is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# pdfxcb is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with pdfxcb. If not, see <http://www.gnu.org/licenses/>.

import argparse
import imp
import json
import os
import os.path
import signal
import sys
import tempfile
import traceback
import uuid

import logging
import logging.config
# define LG as the generic logger *prior* to loading any
# pdfxcb-specific modules
lg = logging
# and immediately configure the logger format
json_log_format = '%(message)s'
lg.basicConfig(format=json_log_format,stream=sys.stdout)

# internal modules
import barScan
#import bubbles
#import deskew
#import exceptions
import json1
import pdf
import util


# bubbles.py, deskew.py, feature_detect.py, and util.py use numpy
# try:
#     imp.find_module('numpy')
# except ImportError:
#     msg = json1.json_msg_module_not_accessible('numpy')
#     lg.error(msg)
#     lg.info(json1.json_last_log_msg())
#     sys.exit(msg)

try:
    imp.find_module('PyPDF2')
except ImportError:
    msg = json1.json_msg_module_not_accessible('PyPDF2')
    lg.error(msg)
    lg.info(json1.json_last_log_msg())
    sys.exit(msg)
import PyPDF2


# handle external signals requesting termination
def signal_handler(signal, frame):
    msg = json1.json_exit_on_external_request_msg()
    lg.error(msg)
    lg.info(json1.json_last_log_msg())
    sys.exit()

signal.signal(signal.SIGHUP, signal_handler)
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


#
# function definitions
#
def locate_cover_sheets (png_files,containing_dir):
    """
    Given the list of files specified by PNG_FILES and CONTAINING_DIR, identify those files containing a barcode. Return multiple values: a list of the corresponding indices and a list of the corresponding barcodes.
    """
    barcodes = []
    indices = []
    # I: index in IMAGE_FILES
    i = 0
    i_max = len(png_files)
    while (i<i_max):
        image_file_spec = os.path.join(containing_dir,png_files[i])
        lg.debug(image_file_spec)
        scan_region = ([0,0,0.5,0.5])
        maybe_barcode = barScan.barcodeScan(
            image_file_spec,
            scan_region
        )
        if maybe_barcode:
            barcodes.append(maybe_barcode)
            indices.append(i)
        i = i+1
        lg.debug(barcodes)
        lg.debug(indices)
    return barcodes,indices

def executable_sanity_checks (executables):
    """
    Check for availability of executables specified in the list of strings EXECUTABLES.
    """
    lg.debug(util)
    for executable_spec in executables:
        if not util.which(executable_spec):
            msg = json1.json_msg_executable_not_accessible(executable_spec)
            lg.error(msg)
            lg.info(json1.json_last_log_msg())
            sys.exit(msg)

def sanity_checks (dirs,files ):
    required_executables = [
        'gs'
        #'pdftoppm'
    ]
    executable_sanity_checks(required_executables)
    directory_sanity_checks (dirs,True)
    file_sanity_checks (files,True)
    required_modules = [
        #'cv2'
    ]
    module_sanity_checks (required_modules,True)

def pdfxcb (pdf_file_spec,output_dir):
    """
    Given the file specified by PDF_FILE_SPEC, look for cover sheets and split the PDF at each coversheet. Name output file(s) based on cover sheet content. Write files to directory specified by OUTPUT_DIR.
    """
    global lg
    # sanity checks
    sanity_checks([output_dir],[pdf_file_spec])
    # split PDF
    png_files = split_pdf_to_png_files(pdf_file_spec,output_dir)
    # locate cover sheets
    cover_sheet_barcodes, cover_sheet_indices = locate_cover_sheets(png_files,output_dir)
    lg.debug("000")
    lg.debug(cover_sheet_barcodes)
    lg.debug(cover_sheet_indices)
    lg.debug("001")
    # write PDFs
    #
    return True


# if IGNORE_PAGE_P is True, skip the scanned page following the pages of each test (for double-sided scanning with a test with an odd number of pages)

# OLD: PDF_FILE_SPEC is either a list of strings (specifying multiple pdf files) or a string specifying a single file.

# NEW: PDF_FILE_SPEC is a string specifying a single PDF file (any 'concatenation' of multiple PDF files must be handled elsewhere...)
def busca_using_png_gen(pdf_file_spec, xy_file, ignore_page_p):
    """Deskew and perform OMR on bubbles in file or files specified by PDF_FILE_SPEC, using XY_FILE as guide to bubble locations. Write OMR results, as files of type 'bsc', to the directory holding the file specified by PDF_FILE_SPEC. Note that the file specified by PDF_FILE_SPEC may hold scans for multiple responses/tests from multiple users."""
    global lg
    lg.debug("BUSCA.00 (busca_using_png_gen)")
    # DEBUGP should be either True or False (any other value will interpreted as False)
    debugp = False
    blank_page_triggers_error_p = True
    sanity_checks(ignore_page_p,xy_file)
    pages_in_test = busca_pages_in_test(xy_file)
    scanset_pngs_generator = pdf.pdf_to_pngs_generator(pdf_file_spec,pages_in_test,ignore_page_p)
    scanSets=[]
    loop_p = True
    while loop_p:
        try:
            # numbering of pages begins at 1
            png_files,first_page_number,last_page_number = scanset_pngs_generator.next()
            lg.debug("BUSCA.60 %s %s %s",png_files,first_page_number,last_page_number)
            scanset = {
                'bscPath': None,
                'pdfPageStart': first_page_number,
                'pdfPageEnd': last_page_number,
                'pdfPath': pdf_file_spec,
                'pngPaths': png_files,
                'deskewPaths': [],
                'deskewStatus': None,
                'gradeitStatus': None,
                'instid': None,
                'score': None,
            }
            scanSets.append( scanset )
            # handle deskewing
            busca_deskew_scanset(scanset,blank_page_triggers_error_p,debugp)
            busca_handle_scoring(scanset,xy_file)
            # offer consumer of log data the opportunity to deal with scansets as they become available
            lg.info(json1.json_scanset(scanset))
        except StopIteration:
            lg.debug("BUSCA.A0")
            loop_p = False
    scanSets_json = json1.json_scansets(scanSets)
    lg.info(scanSets_json)
    return True



def busca_deskew_scanset (scanSet,blank_page_triggers_error_p,debugp):
    page_numbers = [n for n in range(scanSet['pdfPageStart'],scanSet['pdfPageEnd']+1)]
    png_files = scanSet['pngPaths']
    for page_number, png_file in zip(page_numbers,png_files):
        lg.debug("png_file: %s", png_file)
        # if png_file is None, we treat it as an indication to ignore that position in png_files
        if png_file:
            try:
                # deskew_img_file returns None on an apparent blank page
                deskew_file = deskew.deskew_img_file(png_file, debugp)
                if (blank_page_triggers_error_p and deskew_file == None):
                    scanSet['deskewStatus'] = { 'code': 121, 'message': "encountered blank page on attempt to deskew", 'file': png_file }
                    lg.info(json1.json_blank_page_on_deskew(png_file))
                else:
                    scanSet['deskewStatus'] = { 'code': 20, 'message': "successful deskew", 'file': png_file }
                    lg.info(json1.json_successful_deskew(png_file))
            except AssertionError as e:
                lg.debug("BUSCA_DESKEW_SCANSET.A0: %s %s %s %s",e,e.__doc__,e.message,e.args)
                raise e
            except exceptions.CalibrationMarkNotDetected as e:
                lg.debug("BUSCA_DESKEW_SCANSET.A10: %s %s %s", e, e.__doc__, e.args)
                lg.debug("BUSCA_DESKEW_SCANSET.A11: %s", e.message)
                lg.debug("BUSCA_DESKEW_SCANSET.A12: %s", e.diagnostic_file)
                lg.debug("BUSCA_DESKEW_SCANSET.A13: %s", e.additional_notes)
                comments = [ e.message ]
                if e.additional_notes:
                    comments.extend(e.additional_notes)
                lg.error(json1.json_failed_to_deskew(e.diagnostic_file, page_number, comments))
                scanSet['deskewStatus'] = { 'code': 120, 'message': "failed to deskew", 'file': png_file, 'page': page_number }
                # as long as we log the above, it's desirable to tuck this aside and process everything else
                # sys.exit("failed to deskew file"+file);
                # FIXME: do we want this? or do we simply want to not append None below?
                deskew_file = None
            except Exception as e:
                lg.debug("BUSCA_DESKEW_SCANSET.A2: %s %s %s %s", e, e.__doc__, e.message, e.args)
                lg.error(json1.json_failed_to_deskew(png_file, page_number, e.message))
                scanSet['deskewStatus'] = { 'code': 120, 'message': "failed to deskew", 'file': png_file, 'page': page_number }
                # as long as we log the above, it's desirable to tuck this aside and process everything else
                # sys.exit("failed to deskew file"+file);
                # FIXME: do we want this? or do we simply want to not append None below?
                deskew_file = None
        else:
            deskew_file = None
            lg.debug("deskew_file: %s", deskew_file)
        scanSet['deskewPaths'].append(deskew_file)
    lg.debug("BUSCA.B0")
    if (not (scanSet['deskewPaths'] and len(scanSet['deskewPaths'])>0)):
        lg.error(json1.json_failed_to_deskew('', '', 'Failed to generate deskew file(s) from PNG files -- this should not happen -- all deskew failures should be handled on a per-file basis...'))
        lg.info(json1.json_last_log_msg())
        sys.exit("Aborted busca -- see the system log")

def busca_handle_scoring (scanSet,xy_file):
    deskew_file_set = scanSet['deskewPaths']
    lg.debug("DESKEW_FILE_SET: %s", deskew_file_set)
    # anticipate possibility that deskew failed for one or more files in the set
    if None in deskew_file_set:
        pass
    # if None isn't present, assume deskewing was successful
    else:
        lg.debug("BUSCA.D0")
        page_scores = []
        # this is where we want to catch an issue with a single scanset -- e.g., if bubbles can't be located
        try:
            barcodes = bubbles.barcodes_on_pages(deskew_file_set)
            lg.debug("BUSCA.D1: barcodes: %s",barcodes)
            # FIXME: 2015-09-24 -- something in bubbles.score_pages(...) was dying w/o error
            page_scores,bubble_detection_failed_p,diagnosticFiles = bubbles.score_pages(deskew_file_set, xy_file)
            lg.debug("BUSCA.D2: %s %s",bubble_detection_failed_p,diagnosticFiles)
            if bubble_detection_failed_p:
                messageString="Failed to locate anticipated bubbles -- see diagnostic file(s) at"
                for diagnosticFile in diagnosticFiles:
                    messageString=messageString+" "+diagnosticFile
                scanSet['gradeitStatus'] = { 'code': 61, 'message':  messageString, 'files': diagnosticFiles, 'page': ''}
            lg.debug("BUSCA.D3")
        except bubbles.LocateBubbleError as e:
            lg.debug("BUSCA LocateBubbleError: %s",e)
            # note: this is generated by bubbles.score_bubbles --> maybe better to have it caught at calling function so page can be specified?
            messageString="Failed to locate anticipated bubbles -- see diagnostic file(s) at"
            for efile in e.files:
                messageString = messageString+" "+efile
            scanSet['gradeitStatus'] = { 'code': 61, 'message':  messageString, 'files': e.files, 'page': ''}
        except:
            # !! if this occurs, something needs to be debugged -> don't ignore it; ensure this shows up in the log irrespective of other considerations
            msg = 'Unexpected error: {}'.format(sys.exc_info()[0])
            traceback_string = traceback.format_exc()
            lg.critical(msg)
            lg.critical(traceback_string)
            lg.critical(json1.json_msg(255, msg, False,None))
        lg.debug("BUSCA.E0")
        input_file_sans_suffix, input_file_suffix = os.path.splitext(scanSet['pdfPath'])
        # FIXME: this only scales well up to 999 responses
        index_format_string = "{0:0>03d}"
        index_string = str.format(index_format_string,scanSet['pdfPageStart'])
        if page_scores:
            bsc_file_suffix = 'bsc'
            bsc_file = input_file_sans_suffix + index_string + "." + bsc_file_suffix
            write_page_scores(page_scores, bsc_file)
            scanSet['bscPath'] = bsc_file
        scanSet['barcodes'] = barcodes
        paths_file = input_file_sans_suffix + index_string + ".paths"
        write_paths(deskew_file_set, paths_file)

def busca_pages_in_test (xy_file):
    try:
        # FIXME: rename as pages_per_set ?
        pages_in_test = bubbles.xy_to_page_number(xy_file)
    except Exception as e:
        lg.error(json1.json_failed_to_parse_file(e,xy_file))
        lg.info(json1.json_last_log_msg())
        sys.exit("No point in proceeding if we can't parse the XY file to determine the number of pages... " + xy_file)
    if pages_in_test < 1:
        lg.error(json1.json_zero_page_test(xy_file))
        lg.info(json1.json_last_log_msg())
        sys.exit("Doesn't make much sense to scan a test that is composed of zero pages...")
    return pages_in_test



def calc_start_pages (total_scanned_pages, pages_in_set):
    """Return a list of integers representing page numbers where tests begin (page numbering begins with 0)."""
    start_pages = [ i for i in range(0, total_scanned_pages) if i % pages_in_set == 0 ]
    return start_pages

def directory_sanity_check (directory_spec,exitp):
    if not os.path.isdir(directory_spec):
        lg.error(json1.json_file_not_found(directory_spec))
        lg.info(json1.json_last_log_msg())
        if exitp:
            sys.exit("Directory " + directory_spec + " not found.")

def directory_sanity_checks (directories,exitp):
    for directory_spec in directories:
        directory_sanity_check(directory_spec,True)

def file_sanity_check (file,exitp):
    if not os.path.isfile(file):
        lg.error(json1.json_file_not_found(file))
        lg.info(json1.json_last_log_msg())
        if exitp:
            sys.exit("File " + file + " not found.")

def file_sanity_checks (files,exitp):
    for file in files:
        file_sanity_check(file,True)

def module_sanity_checks (module_names,exitp):
    """MODULE_NAMES is a sequence of strings"""
    for module_name in module_names:
        module_sanity_check (module_name,exitp)

def module_sanity_check (module_name,exitp):
    """MODULE_NAME is a string"""
    # check for presence of module which might not be installed/accessible
    try:
        imp.find_module(module_name)
    except ImportError:
        msg = json1.json_msg_module_not_accessible(module_name)
        lg.error(msg)
        lg.info(json1.json_last_log_msg())
        if exitp:
            sys.exit(msg)

def split_pdf_to_png_files (pdf_file_spec,output_dir):
    """Split PDF file specified by PDF_FILE_SPEC into a series of files, each representing a single page as a PNG image. Write files to directory specified by OUTPUT_DIR."""
    try:
        # sanity check
        assert os.path.isabs(pdf_file_spec)
        lg.debug(100)
        #util.assert_file_exists_p(path)
        png_files = pdf.pdf_to_pngs(pdf_file_spec,output_dir)
    except Exception as e:
        msg = json1.json_failed_to_convert_pdf(e,pdf_file_spec)
        lg.error(msg)
        print "failed to convert PDF file(s): %s" % pdf_file_spec
        print "e: %s" % e
        lg.info(json1.json_last_log_msg())
        sys.exit(msg)
    finally:
        lg.info(json1.json_pdf_to_pngs_success(pdf_file_spec,png_files))
        return png_files

def write_page_scores(page_scores, output_file):
    f = open(output_file, 'w')
    for page in page_scores:
        for row in page:
            for datum in row:
                f.write(str(datum))
                f.write(' ')
            f.write('\n')
        f.write('\n')
    f.close()

def write_paths(paths, output_file):
    f = open(output_file, 'w')
    for path in paths:
        f.write(path)
        f.write('\n')
    f.close()

def main():
    """Handle command-line invocation of pdfxcb.py."""
    global lg
    parser = argparse.ArgumentParser(description="This is pdfxcb")
    parser.add_argument("-f",
                        help="absolute path to log file",
                        action="store",
                        dest="log_file",
                        type=str)
    parser.add_argument("-p",
                        help="identifier for a specific instance of pdfxcb",
                        action="store",
                        dest="identifier",
                        type=str)
    parser.add_argument("-l",
                        help="integer between 0 (verbose) and 51 (terse) defining logging",
                        action="store",
                        dest="log_level",
                        type=int)
    #parser.add_argument('-v', '--version', action='version', version=version.version)
    parser.add_argument("input_file", help="an input (PDF) file",
                        nargs=1,
                        type=str)
    args = parser.parse_args()
    #
    # define logging (level, file, message format, ...)
    #
    log_level = args.log_level
    if isinstance(log_level, int) and log_level >= 0 and log_level <= 51:
        log_level = log_level
    else:
        # since this function doesn't necessarily exit quickly
        log_level = logging.INFO
    if args.log_file:
        logfile = args.log_file
    else:
        logfile = 'busca.log'
    json_log_format = '%(message)s'
    for handler in lg.getLogger().handlers:
        lg.getLogger().removeHandler(handler)
    formatter = logging.Formatter(json_log_format)
    file_handler = logging.FileHandler(logfile,'w')
    file_handler.setFormatter(formatter)
    lg.getLogger().addHandler(file_handler)
    lg.getLogger().setLevel(log_level)
    lg.debug("args: %s", args)
    lg.debug("sys.argv: %s",sys.argv)
    if args.identifier:
        identifier = args.identifier
    else:
        identifier = str(uuid.uuid1())
    lg.info(json1.json_first_log_msg(identifier))
    ignore_page_offset = args.ignore_page_offset
    pdf_files = args.input_file
    lg.debug("pdf_files: %s", pdf_files)
    ignore_page_p = False
    if ( ignore_page_offset > 0 ):
        ignore_page_p = True
    pdfxcb(pdf_file_spec)
    # busca_using_png_gen(pdf_files[0], xy_file, ignore_page_p)
    lg.info(json1.json_last_log_msg())

if __name__ == "__main__":
    main()
