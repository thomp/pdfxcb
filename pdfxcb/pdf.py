# -*- coding: utf-8 -*-

# (c) 2018 David A. Thompson <thompdump@gmail.com>
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

#
# pdf.py
#
#   1. accepts an input file (PDF)
#   2. generates a set of PNG files for the pages in the input file
#
import io
import os
import subprocess
import PyPDF2

# configure logging
import logging
lg=logging

# internal/busca modules
import json1

def pdf_page_to_png(src_pdf, pagenum = 0, resolution = 72):
    """
    Return the specified PDF page as a wand.image.Image png.
    :param PyPDF2.PdfFileReader src_pdf: PDF from which to take pages.
    :param int pagenum: Page number to take.
    :param int resolution: Resolution for resulting png in DPI.
    """
    dst_pdf = PyPDF2.PdfFileWriter()
    dst_pdf.addPage(src_pdf.getPage(pagenum))

    pdf_bytes = io.BytesIO()
    dst_pdf.write(pdf_bytes)
    pdf_bytes.seek(0)

    img = Image(file = pdf_bytes, resolution = resolution)
    img.convert("png")
    return img

def pdf_to_pngs(pdf_file,output_dir):
    """
    Generate PNG files, one corresponding to each page of the PDF file PDF_FILE. Write files to directory specified by OUTPUT_DIR. Return a list of the PNG file names.
    """
    input_file_sans_suffix, input_file_suffix = os.path.splitext(pdf_file)
    maybe_dir, input_file_name_only = os.path.split(input_file_sans_suffix)
    outfile_root = input_file_name_only
    # determine number of pages
    reader = PyPDF2.PdfFileReader(file(pdf_file, "rb"))
    number_of_pages = reader.getNumPages()
    return pdf_to_pngs__gs(pdf_file, number_of_pages, outfile_root, output_dir)

def pdf_to_pngs__gs (pdf_file, number_of_pages, outfile_root, output_dir):
    """Helper relying on Ghostscript"""
    output_dir_and_filename = os.path.join(output_dir,outfile_root)
    # %03d is printf directive directing gs to specify page number as a zero-padded 3-digit sequence
    output_path_spec = output_dir_and_filename + '-%03d.png'
    lg.debug(output_path_spec)
    gs_command = [
        "gs",
        "-q",
        "-dBATCH",
        "-dNOPAUSE",
        "-sDEVICE=pnggray",
        '-r300',                # 300 dpi
        #"-dAutoRotatePages=/PageByPage",
        '-dUseCropBox',
        # use %d as a printf format specification for page number
        # as zero-filled with minimum of three spaces
        "-sOutputFile=%s" % output_path_spec,
        pdf_file
    ]
    lg.debug(gs_command)
    return_code = subprocess.call(gs_command, shell=False)
    # log success/failure
    pdf_to_pngs__gs_log(return_code,number_of_pages)
    # return file names
    return pdf_to_pngs__gs_file_names (number_of_pages,outfile_root)

def pdf_to_pngs__gs_log (return_code,number_of_pages):
    if (return_code == 0):
        for page_number in range(number_of_pages):
            lg.info(json1.json_completed_pdf_to_ppm(page_number,number_of_pages))
    else:
        lg.error(json1.json_failed_to_convert_pdf(None,pdf_file))

def pdf_to_pngs__gs_file_names (number_of_pages,outfile_root):
    png_files=[]
    index_format_string = "{1:0>03d}"
    string_format_string = "{0}-" + index_format_string + ".png"
    for pagenumber in range(number_of_pages):
        png_infile = str.format(
            string_format_string,
            outfile_root,pagenumber+1);
        png_files.append(png_infile)
    return png_files

def pdf_to_pngs__pdftoppm (pdf_file, number_of_pages, outfile_root):
    """
    Helper relying on pdftoppm
    """
    for page_number in range(number_of_pages):
        returncode = subprocess.call(
            ["pdftoppm", "-f", str(page_number), "-l", str(page_number), "-gray", "-png", pdf_file, outfile_root],
            shell=False)
        if (returncode == 0):
            lg.info(json1.json_completed_pdf_to_ppm(page_number,number_of_pages))
        else:
            lg.error(json1.json_failed_to_convert_pdf(None,pdf_file))
    # return file names
    png_files=[]
    # due to the pdftoppm limitations, we have to plan ahead for the file names, anticipating pdftoppm's default non-configurable behavior...
    index_format_string = ""
    if ( number_of_pages < 10 ):
        index_format_string = "{1:d}"
    elif ( number_of_pages < 100 ):
        index_format_string = "{1:0>02d}"
    elif ( number_of_pages < 1000 ):
        index_format_string = "{1:0>03d}"
    else:
        raise Exception('no support (at this point) for page count exceeding 1000 pages')
    string_format_string = "{0}-" + index_format_string + ".png"
    for pagenumber in range(number_of_pages):
        png_infile = str.format(
            string_format_string,
            outfile_root,pagenumber+1);
        png_files.append(png_infile)
    return png_files
