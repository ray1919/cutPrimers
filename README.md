# cutPrimers
curPrimers is a tool for trimming primer sequences from amplicon based NGS reads

**This is a fork of the original git**

## Requirements
### Linux
cutPrimers works on the Python3+ and requires the following packages:
* **Biopython** - you can install it with: `sudo apt-get install python3-biopython` or download it from http://biopython.org/wiki/Download and install it locally with `python3 setup.py install --user`
* **regex** - you can install it with: `sudo apt-get install python3-regex`  or download it from https://pypi.python.org/pypi/regex/ and install it locally with `python3 setup.py install --user`
* **argparse** - you can install it with: `sudo pip3 install argparse` or download it from https://pypi.python.org/pypi/argparse and install it locally with `python3 setup.py install --user`

### Windows
For use on windows download and install python3.6 from www.python.org/downloads/ (**Attention! Remember to check "Add Python 3.6 to PATH" in the bottom of the installation window!**). After installation, restart your computer.

After that, install the followong packages with respective commands in command line (to run command line, search in Start menu "cmd" and run "cmd.exe"):
* **Biopython** - with: `pip install biopython`. If you do not have Visual Studio C++ already installed, pip will show an error. In that case, download and install it from landinghub.visualstudio.com/visual-cpp-build-tools/
* **regex** - you can install it with: `pip install regex`
* **argparse** - you can install it with: `pip install argparse`

### Mac OS
For use on Mac OS download and install python3.6 from www.python.org/downloads/

After that install the followong packages with respective commands in command line:
* **Biopython** - with: `pip install biopython`
* **regex** - you can install it with: `pip install regex`
* **argparse** - you can install it with: `pip install argparse`

## Installation
cutPrimers does not require any installations

## Use
You can see all parameters with 
```
python3 cutPrimers.py -h
```

## Example of use
As an example you can use files from directory "examples". Trim them with the following commands:

Before using cutPrimers we recommend to use cutadapt for removing adaptor sequences from 3'-ends of reads. In this case, you will get more reliable results. You can use cutPrimers with Trimmomatic with the following commands:
```
mkdir example_trimmed
cutadapt -q 15 --trim-n -j 1 \
    -A CTGAGTCGGAGACACGCAGGGATGAGATGG \
    -a AATCACCGACTGCCCATAGAGAGGAAAGCGGAG \
    -o example_trimmed/trimmed_R1.fq.gz \
    -p example_trimmed/trimmed_R2.fq.gz \
    example/1_S1_L001_R1_001.fastq.gz \
    example/1_S1_L001_R2_001.fastq.gz

python3 cutPrimers.py -r1 example_trimmed/trimmed_R1.fq.gz \
    -r2 example_trimmed/trimmed_R2.fq.gz \
    -pr example/primers.fa \
    -tr1 example_trimmed/trimmed.trimmed_R1.fq.gz \
    -tr2 example_trimmed/trimmed.trimmed_R2.fq.gz \
    -utr1 example_trimmed/trimmed.untrimmed_R1.fq.gz \
    -utr2 example_trimmed/trimmed.untrimmed_R2.fq.gz \
    --primer-location-buffer 0 \
    --error-number 3 \
    -insa example_trimmed/nsa.txt \
    --identify-dimers example_trimmed/dimer.txt \
    --primersStatistics example_trimmed/primersStatistics.txt \
    -t 2 --primer3-absent
```

## Parameters
```
-h, --help - show this help message and exit
    -h, --help            show this help message and exit
  --readsFile_r1 READSFILE1, -r1 READSFILE1
                        file with R1 reads of one sample
  --readsFile_r2 READSFILE2, -r2 READSFILE2
                        file with R2 reads of one sample
  --primersFile PRIMERSFILE, -pr PRIMERSFILE
                        fasta-file with sequences of primers on the
                        5'(forward)-ends of R1 and R2 reads, paired primers
                        should be written interleaved as >forward_primer_1
                        >reverse_primer_1 >forward_primer_2 >reverse_primer_2
  --trimmedReadsR1 TRIMMEDREADSR1, -tr1 TRIMMEDREADSR1
                        name of file for trimmed R1 reads
  --trimmedReadsR2 TRIMMEDREADSR2, -tr2 TRIMMEDREADSR2
                        name of file for trimmed R2 reads
  --untrimmedReadsR1 UNTRIMMEDREADSR1, -utr1 UNTRIMMEDREADSR1
                        name of file for untrimmed R1 reads. If you want to
                        write reads that has not been trimmed to the same file
                        as trimmed reads, type the same name
  --untrimmedReadsR2 UNTRIMMEDREADSR2, -utr2 UNTRIMMEDREADSR2
                        name of file for untrimmed R2 reads. If you want to
                        write reads that has not been trimmed to the same file
                        as trimmed reads, type the same name
  --primersStatistics PRIMERSSTATISTICS, -stat PRIMERSSTATISTICS
                        name of file for statistics of errors in primers. This
                        works only for paired-end reads with primers at 3'-
                        and 5'-ends
  --error-number ERRNUMBER, -err ERRNUMBER
                        number of errors (substitutions, insertions,
                        deletions) that allowed during searching primer
                        sequence in a read sequence. Default: 5
  --primer-location-buffer PRIMERLOCBUF, -plb PRIMERLOCBUF
                        Buffer of primer location in the read from the end.
                        Default: 10
  --min-primer3-length MINPRIMER3LEN, -primer3len MINPRIMER3LEN
                        Minimal length of primer on the 3'-end to trim. Use
                        this parameter, if you are ready to trim only part of
                        primer sequence of the 3'-end of read
  --primer3-absent, -primer3
                        if primer at the 3'-end may be absent, use this
                        parameter
  --identify-dimers IDIMER, -idimer IDIMER
                        use this parameter if you want to get statistics of
                        homo- and heterodimer formation. Choose file to which
                        statistics of primer-dimers will be written. This
                        parameter may slightly decrease the speed of analysis
  --identify-nsa INSA, -insa INSA
                        use this parameter if you want to get statistics of
                        primers non-specific amplification products. Choose
                        file to which statistics will be written. This
                        parameter may slightly decrease the speed of analysis
  --threads THREADS, -t THREADS
                        number of threads
```
## Citation
**cutPrimers: A New Tool for Accurate Cutting of Primers from Reads of Targeted Next Generation Sequencing**. Kechin A, Boyarskikh U, Kel A, Filipenko M, 2017, Journal of Computational Biology, 2017 Jul 17. doi: 10.1089/cmb.2017.0096 (https://www.ncbi.nlm.nih.gov/pubmed/28715235)
