"""Split a PDF document based on the locations of barcodes
"""

# Author: David A. Thompson

import argparse
import imp
import json
import os
import os.path
import re
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
    # Ensure receipt of signal is logged prior to terminating
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
def locate_cover_sheets (png_file_tuples,containing_dir,match_re,scan_region):
    """
    Given the list of files specified by PNG_FILE_TUPLES (tuples where the first member specifies the name of the PNG file) and CONTAINING_DIR,
    identify those files containing a barcode. Return multiple values: a list of the
    corresponding barcodes and a list of the corresponding indices.
    """
    barcodes = []
    indices = []
    # I: index in IMAGE_FILES
    i = 0
    i_max = len(png_file_tuples)
    while (i<i_max):
        # log progress by default (otherwise, this can be a long period of silence...)
        lg.info(json1.json_progress("looking for barcode on " + str(i) + " of " + str(i_max) + " PNG files"))
        image_file_spec = os.path.join(containing_dir,png_file_tuples[i][0])
        lg.debug(image_file_spec)
        maybe_barcode = barScan.barcodeScan(
            image_file_spec,
            scan_region         # None
        )
        # don't ignore barcode if consider is true
        consider = True
        if maybe_barcode:
            if match_re:
                consider = match_re.match(maybe_barcode)
            if consider:
                barcodes.append(maybe_barcode)
                indices.append(i)
        i = i+1
        #lg.debug(barcodes)
        #lg.debug(indices)
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

def generate_output_file_names(cover_sheet_barcodes,cover_sheet_indices,output_dir):
    file_names = []
    for cover_sheet_barcode,cover_sheet_index in zip(cover_sheet_barcodes,cover_sheet_indices):
        cover_sheet_index_as_string = str.format("{0:0>03d}", cover_sheet_index)
        version = -1
        # sanity check on version (completely arbitrary at this point)
        max_version = 99
        while (not version >= max_version and (version < 0 or os.path.exists(path))):
            version = version + 1
            file_name = cover_sheet_barcode + "-" + cover_sheet_index_as_string + "-" + str(version) + ".pdf"
            path = os.path.join(output_dir,file_name)
        file_names.append(path)
    return file_names

def generate_page_ranges(cover_sheet_indices,png_file_page_number_tuples,number_of_pages):
    """
    Calling code must guarantee that tuples in
    PNG_FILE_PAGE_NUMBER_TUPLES are ordered (ascending) with respect
    to page numbers. COVER_SHEET_INDICES is an array of integers, each
    an index value identifying a member of PNG_FILE_PAGE_NUMBER_TUPLES
    which corresponds to a cover sheet.
    """
    # to capture last set of pages, tag on an imaginary cover sheet at the end
    cover_sheet_indices.append(
        len(png_file_page_number_tuples)
    )
    png_file_page_number_tuples.append((None,number_of_pages+1))
    page_ranges = []
    for cover_sheet_index, next_cover_sheet_index in zip(cover_sheet_indices[:-1],cover_sheet_indices[1:]):
        page_ranges.append(
            (png_file_page_number_tuples[cover_sheet_index][1],
             png_file_page_number_tuples[next_cover_sheet_index][1]-1))
    return page_ranges

def sanity_checks (dirs,files):
    lg.debug(files)
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

def pdfxcb (pdf_file_spec,output_dir,match_re,rasterize_p):
    """
    Given the file specified by PDF_FILE_SPEC, look for cover sheets
    and split the PDF at each coversheet. Name output file(s) based on
    cover sheet content. Write files to directory specified by
    OUTPUT_DIR. Return True. If MATCH_RE is defined, ignore barcodes
    unless the corresponding string matches the regex MATCH_RE. Use
    RASTERIZE_P = False if the PDF does not contain vector graphics
    but is solely bitmap data (e.g., the PDF was generated from a
    scanned document).
    """
    global lg
    sanity_checks([output_dir],[pdf_file_spec])
    # If confident that the PDF under analysis is derived from a scan
    # (i.e., contains only bitmap data), then the images embedded in
    # the PDF can be analyzed directly. If the PDF may contain vector
    # data on the cover sheet pages, then rasterization is indicated.
    # See doc/optimization.md for notes on time implications.

    # PNG_FILE_PAGE_NUMBER_TUPLES is an array where each member has
    # the form (<PNG file name>, <PDF page number>). There is no
    # guarantee that all pages in the original PDF document are
    # represented. Furthermore, there may be multiple PNG images per
    # PDF page -- i.e., the array might include ("flurpies.png",1) and
    # ("glurpies.png",1).

    # FIXME: consider having a single call here -- FOO -- that specializes on rasterize_p
    if rasterize_p:
        # extract PDF pages as image data (PNG files)
        png_file_page_number_tuples = split_pdf_to_png_files(pdf_file_spec,output_dir)
        # Once rasterized pages are generated, optionally scan for cue marks
        # CUE_INDICES = array where each member is an integer indicating index of member of png_file_page_number_tuples where the corresponding bitmap has a cue mark
        # cue_indices = scan_for_cue_marks(png_file_page_number_tuples) <-- use urh_corner_mean w/reasonable threshold (10? 20? 50?) for "black" 
    else:
        # extract images directly from PDF
        png_file_page_number_tuples = invoke_pdfimages_on(pdf_file_spec,output_dir)
    # Code below expects png_file_page_number_tuples to be ordered with respect to page number.
    # Note that sorted default is ascending order.
    png_file_page_number_tuples = sorted(png_file_page_number_tuples,
                                         key=lambda tuple: tuple[1])
    #
    # locate cover sheets
    #
    if rasterize_p:
        # possibilities:
        # 1. png files represent rasterized pages
        scan_region = ([0,0,0.7,0.5])
    else:
        # 2. png files represent images from PDF (via pdfimages)
        scan_region = None # None is not treated as the equivalent of ([0,0,1,1]). ([0,0,1,1]) triggers cropping by barcodeScan.
    cover_sheet_barcodes, cover_sheet_indices = locate_cover_sheets(png_file_page_number_tuples,output_dir,match_re,scan_region)
    print(cover_sheet_barcodes)
    lg.debug(cover_sheet_barcodes)
    lg.debug(cover_sheet_indices)
    # Setting to False supports debugging/development. This should be set to True in production.
    clean_up_png_files = False # False # True
    if clean_up_png_files:
        for png_file_tuple in png_file_page_number_tuples:
            os.remove(os.path.join(output_dir,png_file_tuple[0]))
    # write PDFs
    pdf_length = pdf.pdf_number_of_pages(pdf_file_spec) # len(png_files) only works if PNGs are rasterized pages
    page_ranges = generate_page_ranges(cover_sheet_indices,png_file_page_number_tuples,pdf_length)
    output_file_names = generate_output_file_names(cover_sheet_barcodes,cover_sheet_indices,output_dir)
    lg.debug(output_file_names)
    pdf.pdf_split(pdf_file_spec,output_file_names,page_ranges)
    lg.info(json1.json_msg(40,
             ['Analysis and burst completed'],
             False,
             files=output_file_names,
             data={
                 'barcodes': cover_sheet_barcodes,
                 'indices': cover_sheet_indices
             }
    ))
    return True

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

def invoke_pdfimages_on (pdf_file_spec,output_dir):
    """
    Extract images in PDF file specified by PDF_FILE_SPEC into a
    series of files, each representing a single PNG image. Write files
    to directory specified by OUTPUT_DIR.

    Returns a list of tuples where each tuple has the structure
    (png_file,png_file_page_number) png_file_page_number is an
    integer. The list is an ordered sequence with respect to page
    number - low to high.
    """
    png_file_page_number_tuples = None
    try:
        # sanity check
        if not os.path.isabs(pdf_file_spec):
            msg = "The input PDF must be specified as an absolute file path"
            lg.error(json1.json_msg(108,[msg],False,files=[pdf_file_spec]))
            sys.exit(msg)
        else:
            png_file_page_number_tuples = pdf.pdfimages(pdf_file_spec,output_dir)
    except Exception as e:
        lg.debug(str(e))
        msg = json1.json_failed_to_convert_pdf(e,pdf_file_spec)
        lg.error(msg)
        lg.info(json1.json_last_log_msg())
        sys.exit(msg)
    else:
        # Is it really import to log png files? (Need to dig them out of tuples...)
        lg.info(json1.json_pdf_to_pngs_success(pdf_file_spec,
                                               None #png_files
        ))
        return png_file_page_number_tuples

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
    """
    Split the PDF file specified by PDF_FILE_SPEC into a series of
    files, each representing a single page as a PNG image. Write files
    to directory specified by OUTPUT_DIR.
    """
    png_files = None
    try:
        # sanity check
        if not os.path.isabs(pdf_file_spec):
            msg = "The input PDF must be specified as an absolute file path"
            lg.error(json1.json_msg(108,[msg],False,files=[pdf_file_spec]))
            sys.exit(msg)
        else:
            # array of (<file_name>,<page_number>) tuples
            png_specs = pdf.pdf_to_pngs(pdf_file_spec,output_dir)
    except Exception as e:
        msg = json1.json_failed_to_convert_pdf(e,pdf_file_spec)
        lg.error(msg)
        print "failed to convert PDF file(s): %s" % pdf_file_spec
        print "e: %s" % e
        lg.info(json1.json_last_log_msg())
        sys.exit(msg)
    else:
        lg.info(json1.json_pdf_to_pngs_success(pdf_file_spec,png_specs))
        return png_specs

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
    parser.add_argument("-d",
                        help="absolute path to output directory",
                        action="store",
                        dest="output_dir",
                        type=str)
    parser.add_argument("-m",
                        help="match barcodes to regex (ignore if no match)",
                        action="store",
                        dest="match_re_string",
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
    parser.add_argument("input_files", help="an input (PDF) file",
                        # keep nargs as we may want to accept multiple PDFs as input at some point
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
    # sanity check for existence of log file directory
    if (os.path.dirname(logfile) and
        not os.path.exists(os.path.dirname(logfile))):
        raise Exception(str.format("log file directory {0} not present",
                                   os.path.dirname(logfile)))
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
    # 1000[0-9][0-9][0-9]$ matches on tt user id
    match_re_string = args.match_re_string
    lg.debug(match_re_string)
    match_re = None
    if match_re_string:
        match_re = re.compile(match_re_string)
    pdf_file_spec = args.input_files[0]
    lg.debug(pdf_file_spec)
    lg.info(json1.json_first_log_msg(identifier, files = [pdf_file_spec] ))
    rasterize_p = False
    # generic debugging
    lg.debug(os.getcwd())         # current/working directory
    # might also want to import platform to get architecture, other details...
    try:
        pdfxcb(pdf_file_spec,args.output_dir,match_re,rasterize_p)
    except Exception as e:
        lg.error("Crash and burn")
        lg.error(sys.exc_info()[0])
        raise
    lg.info(json1.json_last_log_msg())

if __name__ == "__main__":
    main()
