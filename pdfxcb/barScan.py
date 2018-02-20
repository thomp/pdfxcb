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

import imp
import sys

import json1

# configure logging
import logging
# define logger
lg=logging

#
# this can handle a single PDF sheet w/all sorts of other stuff on it -- as long as it only has a single bar code on the sheet -- no need to identify region with bar code... zbar handles it all... lovely!
#

try:
    imp.find_module('zbar')
except ImportError:
    msg = json1.json_msg_module_not_accessible('zbar')
    lg.error(msg)
    lg.info(json1.json_last_log_msg())
    sys.exit(msg)
import zbar


# Image is provided by PIL or pillow
try:
    imp.find_module('PIL')
except ImportError:
    msg = json1.json_msg_module_not_accessible('PIL')
    lg.error(msg)
    lg.info(json1.json_last_log_msg())
    sys.exit(msg)
from PIL import Image


# internal/busca modules
import json1


# image location
# imagePDFPath = "/home/thomp/computing/javascript/src/dat-ocr/answers.pdf"
# imagePNGPath = "/home/thomp/computing/javascript/src/dat-ocr/answers.png"
# img = PythonMagick.Image()
# img.density("300")
# img.read(imagePDFPath) # read in at 300 dpi
# img.write(imagePNGPath)

# SCAN_REGION specifies two points as x1,y1,x2,y2. These two points (POINT_1 and POINT_2) are pairs (x,y) of percentages (expressed as value between 0 and 1.0) relative to the dimensions of the image; they define the box within which the barcode scan occurs
def barcodeScan(imagePNGPath, scan_region):
    """Return None if a barcode was not found. If a barcode was found, return a string corresponding to the barcode-encoded data. Search within the region defined by POINT_1 and POINT_2"""
    lg.debug("barcodeScan.00: %s",imagePNGPath)
    # create a reader
    scanner = zbar.ImageScanner()
    # configure the reader
    scanner.parse_config('enable')
    # obtain image data
    # PIL origin (0,0) is top left corner
    pil = Image.open(imagePNGPath).convert('L')
    width, height = pil.size
    # relative (percentage) values between 0 and 1
    x_crop_min = min(scan_region[0],scan_region[2])
    x_crop_max = max(scan_region[0],scan_region[2])
    y_crop_min = min(scan_region[1],scan_region[3])
    y_crop_max = max(scan_region[1],scan_region[3])
    cropTop=int(height*y_crop_min)
    cropBottom=int(height*y_crop_max)
    cropLeft=int(height*x_crop_min)
    cropRight=int(height*x_crop_max)
    # crop box is 4-tuple: left,upper,right,lower
    pilCropBox = [cropLeft,cropTop,cropRight,cropBottom]
    pilCropped = pil.crop(pilCropBox)
    pilCroppedWidth,pilCroppedHeight = pilCropped.size
    raw = pilCropped.tobytes()
    # wrap raw image data in zbar.Image
    image = zbar.Image(pilCroppedWidth, pilCroppedHeight, 'Y800', raw)
    # scan the image for barcodes
    scanner.scan(image)
    # extract results
    barcodeString = None
    lg.debug("image: %s",image)
    lg.debug("image dir: %s",dir(image))
    lg.debug("image symbols: %s",image.symbols)
    # image.symbols should hold a zbar.SymbolSet object
    for symbol in image:
        lg.debug("symbol: %s",symbol)
        barcodeString = symbol.data
        if ( not barcodeString ):
            lg.warn(json1.json_barcode_not_found([imagePNGPath]));
        #barcodeType = symbol.type
    lg.debug("barcodeScan.90: %s",barcodeString)
    # clean up (destroy the image object to free up references to the data and symbols)
    # - note: if another image will be scanned, it's also possible to simply recycle the image object
    del(image)
    return barcodeString

if __name__ == "__main__":
    import sys
    # log to console when executing directly
    lg.basicConfig(stream=sys.stderr,level=logging.DEBUG)
    # only intended to be run as python ./barScan.py "/path/to/foo.png"
    lg.debug("%s",sys.argv)
    if len(sys.argv) > 1:
        barcodeScan(sys.argv[1])
    else:
        sys.exit("Must supply a single file as argument")
