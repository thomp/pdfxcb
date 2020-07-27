# pdfxcb

*Split a PDF using barcodes*

---

*pdfxcb* splits a PDF using pages with barcodes as delimiters.


## How it works

Any page in the input PDF containing a barcode is considered a "barcode sheet". Each barcode sheet, and those pages succeeding that page and preceding the next barcode sheet, comprise a single set of pages output as a discrete PDF file.

Each output file is named, by default, as `<barcode>-<index>.pdf` where <barcode> is the content encoded by the barcode on the barcode sheet and <index> is the page number of the barcode sheet relative to the input PDF. The page number is formatted as a three-digit page number (e.g., 001 or 023) unless the page number exceeds 999. Page numbering begins at one.


## Installing

Ensure dependencies are installed. In Debian,

    sudo apt-get install pdfimages python-pypdf2 python-zbar

Install pdfxcb. For local development, install to `~/.local/bin/pdfxcb` with

    pip install --no-index --upgrade --user .

If you install in this manner, consider, for convenience, adding the default Python executable path to your PATH variable. For example, one might add `export PATH=~/.local/bin:$PATH` to the profile file. Alternatively, copy to `/usr/local/bin` for system-wide access.


## Invoking from the shell

`-d`
absolute path to output directory
						
`-l`
integer between 0 (verbose) and 51 (terse) defining logging

`-f`
absolute path to log file

`-p`
identifier for a specific instance of pdfxcb


Examples:

    ~/.local/bin/pdfxcb -d /home/joejoe/src/pdfxcb/testing-sandbox/pdfxcb -l 20 -f /home/joejoe/src/pdfxcb/testing-sandbox/pdfxcb/pdfxcb.log /home/joejoe/src/pdfxcb/testing-sandbox/pdfxcb/rodriguez--.pdf


    ~/.local/bin/pdfxcb -d /tmp/tstdir/ -l 20 -f /tmp/tstdir/pdfxcb.log -p 57ECE30020D711E89DBF14ABC52D67D9 ~/Google.Drive.thompfpu/academic/courses/physiol--human/scans/2018/mt2/scans4.pdf

    ~/.local/bin/pdfxcb -d ~/Google.Drive.thompfpu/academic/courses/ochem2/scans/2018/mt2/mt2-burst -l 20 -f ~/Google.Drive.thompfpu/academic/courses/ochem2/scans/2018/mt2/mt2-burst/pdfxcb.log ~/Google.Drive.thompfpu/academic/courses/ochem2/scans/2018/mt2/mt2-c-p1.pdf 


## Invoking from within Python

	>>> pdfxcb.lg.getLogger().setLevel(pdfxcb.lg.DEBUG)

	>>> pdfxcb.pdfxcb("/home/joejoe/src/pdfxcb/testing-sandbox/pdfxcb/test-doc-01/test-doc-01.pdf","/home/joejoe/src/pdfxcb/testing-sandbox/pdfxcb/test-doc-01/",None,False)


## Logging

A successful "run" should generate at least 3 log messages, each as a separate line in the log file: an initial log message (code 3), the results of analysis and burst/splitting (code 40), and a final log message (code 2). Examples are below.

    {"microsec": 229757, "message": "Initial log message", "code": 3, "id": "96f08ca4-1746-11e8-936f-9840bb275139", "time": 1519245258}

    {"files": ["/tmp/123ABCabc-001.pdf", "/tmp/1234567890128-003.pdf"], "code": 40, "microsec": 402458, "time": 1520018355, "message": ["Analysis and burst completed"], "data": {"indices": [1, 3, 6], "barcodes": ["123ABCabc", "1234567890128"]}}

    {"microsec": 791009, "message": "Scan and analysis complete", "code": 2, "time": 1519245261}

