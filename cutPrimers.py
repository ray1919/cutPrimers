#!/usr/bin/env python3
# v13 - added checking of heterodimer formation of primers
# v14 - added ability to read and write to gzipped files; speed of processing was increased 10-times
# v15 - added ability to write untrimmed and trimmed reads to one file. Also added possibility that 3'-primer may be absent
# v16 - added ability to trim on the 3'-end only part of primer sequence
# fork original code from https://github.com/aakechin/cutPrimers/blob/master/cutPrimers.py
# v17 - rewrite code to use single 5p primers input file
#       added ability to check non-specific product as new feature
#       added ability to check similar primers which edit distance less than min-errors
# v18 - discard reads length < 20 after primer-trimming
# v19 - added ability to label each record with 5p primer name at the end of each fastq description
#     - fix bug that some dimers might be also detected as non-specfic amplicons
# v20 - added ability to cutprimer with reverse strand pairs of primers, F/5p primer in reverse strand, and R/3p primer in forward primer
# v21 - added ability to reserve nsa amplicons, 2018-05-04
# v22 - fix bug in determing 3' primer matching, 2018-6-2

# Section of importing modules
import os
import sys
from Bio import SeqIO
from Bio.Seq import Seq
from Bio import pairwise2
import glob,gzip
import regex
import time
from multiprocessing import Pool,Queue
import argparse
import time,math
from itertools import repeat
from operator import itemgetter
import hashlib
import editdistance

__version__ = '1.22.0'

def makeHashes(seq,k):
    # k is the length of parts
    h=[]
    lens=set([k])
    for i in range(len(seq)-k+1):
        h.append(hashlib.md5(seq[i:i+k].encode('utf-8')).hexdigest())
    return(h,lens)

def initializer(maxPrimerLen2,primerLocBuf2,errNumber2,primersR1_52,primersR1_32,primersR2_52,primersR2_32,
                primerR1_5_hashes2,primerR1_5_hashLens2,primerR2_5_hashes2,primerR2_5_hashLens2,
                readsFileR22,primersStatistics2,idimer2,primer3absent2,minPrimer3Len2):
    global primersR1_5,primersR1_3,primersR2_5,primersR2_3,readsFileR2
    global trimmedReadsR1,trimmedReadsR2,untrimmedReadsR1,untrimmedReadsR2
    global maxPrimerLen,q4,errNumber,primerLocBuf,readsPrimerNum,primersStatistics
    global primerR1_5_hashes,primerR2_5_hashes,primerR1_5_hashLens,primerR2_5_hashLens,primer3absent,idimer
    maxPrimerLen=maxPrimerLen2
    primerLocBuf=primerLocBuf2
    errNumber=errNumber2
    primersR1_5=primersR1_52
    primersR1_3=primersR1_32
    primersR2_5=primersR2_52
    primersR2_3=primersR2_32
    primerR1_5_hashes=primerR1_5_hashes2; primerR1_5_hashLens=primerR1_5_hashLens2;
    primerR2_5_hashes=primerR2_5_hashes2; primerR2_5_hashLens=primerR2_5_hashLens2
    readsFileR2=readsFileR22
    primersStatistics=primersStatistics2
    idimer=idimer2
    primer3absent=primer3absent2
    minPrimer3Len=minPrimer3Len2

# Section of functions
def showPercWork(done,allWork):
    percDoneWork=round((done/allWork)*100,2)
    sys.stdout.write("\r"+str(percDoneWork)+"%")
    sys.stdout.flush()

def revComplement(nuc):
    return(str(Seq(nuc).reverse_complement()))

def countDifs(s1,s2):
    a=pairwise2.align.globalms(s1,s2,2,-1,-1.53,0)
    maxSum=0
    k=0
    for i,b in enumerate(a):
        left=len(b[1])-len(b[1].lstrip('-'))+len(b[0])-len(b[0].lstrip('-'))
        right=len(b[1])-len(b[1].rstrip('-'))+len(b[0])-len(b[0].rstrip('-'))
        if left+right>maxSum:
            maxSum=left+right
            k=i
    ins=a[k][1].strip('-').count('-')
    dels=a[k][0].strip('-').count('-')
    left=max(len(a[k][1])-len(a[k][1].lstrip('-')),len(a[k][0])-len(a[k][0].lstrip('-')))
    right=max(len(a[k][1])-len(a[k][1].rstrip('-')),len(a[k][0])-len(a[k][0].rstrip('-')))
    if right==0:
        mism=sum(b!=c and c!='-' and b!='-' for b,c in zip(a[k][0][left:],a[k][1][left:]))
        return((mism,ins,dels,a[k][0][left:]))
    else:
        mism=sum(b!=c and c!='-' and b!='-' for b,c in zip(a[k][0][left:-right],a[k][1][left:-right]))
        return((mism,ins,dels,a[k][0][left:-right]))

def getErrors(s1,s2):
    # This function calculates number of errors between designed and sequenced primer sequences
    # s1 - initial sequence of primer
    # s2 - sequenced sequece of primer
    # Align them
    a=pairwise2.align.localms(s1,s2,2,-1,-1.53,0)
    maxSum=0
    k=0
    # First of all we detect the best alignment
    # and coordinates in range of which we will get mutations
    for i,b in enumerate(a):
        left=len(b[1])-len(b[1].lstrip('-'))+len(b[0])-len(b[0].lstrip('-'))
        right=len(b[1])-len(b[1].rstrip('-'))+len(b[0])-len(b[0].rstrip('-'))
        if left+right>maxSum:
            maxSum=left+right
            k=i
    poses=[] # poses - list of positions in sequences with mutations
    muts=[] # muts - mutations
    if right==0:
        s3=a[k][0][left:]
        s4=a[k][1][left:]
    else:
        s3=a[k][0][left:-right]
        s4=a[k][1][left:-right]
    for i,(b,c) in enumerate(zip(s3,s4)):
        if b!=c:
            poses.append(i+left+1)
            muts.append(b+'/'+c)
    return(poses,muts)

def interleavedPrimerNum(x):
    return 1 - (x % 2) + int(x/2)*2

def hamming2(s1, s2):
    """Calculate the Hamming distance between two bit strings"""
    if len(s1) != len(s2):
        return -1
    return sum(c1 != c2 for c1, c2 in zip(s1, s2))

def trimPrimers(data):
    # This function get two records from both read files (R1 and R2)
    # and trim them
    # As a result it returns list
    #[trimmedReads,untrimmedReads]
    # resList is a variable with trimmed read sequences (0) and untrimmed read sequences (1)
    resList=[[None,None],[None,None]]
    r1,r2=data
    # skip short reads less than 30bp
#   if len(r1) < maxPrimerLen+primerLocBuf or len(r2) < maxPrimerLen+primerLocBuf:
#       return([[None,None],[r1,r2]],[],False)
    # check r1 & r2 is paired
    if hamming2(r1.description, r2.description) != 1:
        return([[None,None],[None,None]],[],False)
    # Find primer at the 5'-end of R1 read
    readHashes=set()
    for l in primerR1_5_hashLens:
        hashes,lens=makeHashes(str(r1.seq[:maxPrimerLen+primerLocBuf]),l)
        readHashes.update(hashes)
    matchedPrimers={}
    for rh in readHashes:
        if rh in primerR1_5_hashes.keys():
            for a in primerR1_5_hashes[rh]:
                if a not in matchedPrimers.keys():
                    matchedPrimers[a]=1
                else:
                    matchedPrimers[a]+=1
    bestPrimer=None
    bestPrimerValue=None
    goodPrimers=[]
    goodPrimerNums=[]
    # loop down the best rated primers, save adjacent results as good primers
    for key,item in sorted(matchedPrimers.items(),key=itemgetter(1),reverse=True):
        if bestPrimer==None:
            bestPrimer=key
            bestPrimerValue=item
            continue
        if item>=bestPrimerValue-1:
            goodPrimers.append(primersR1_5[key])
            goodPrimerNums.append(key)
        else: break
    if bestPrimer!=None:
        m1=regex.search(r''+primersR1_5[bestPrimer]+'{e<='+errNumber+'}',str(r1.seq[:maxPrimerLen+primerLocBuf]),flags=regex.BESTMATCH)
    else:
        return([[None,None],[r1,r2]],[],False)
##    m1=regex.search(r'(?:'+'|'.join(primersR1_5)+'){e<='+errNumber+'}',str(r1.seq[:maxPrimerLen+primerLocBuf]),flags=regex.BESTMATCH)
    # Use result of searching 5'-primer
    if m1==None:
        if len(goodPrimers)>0:
            m1=regex.search(r'(?:'+'|'.join(goodPrimers)+'){e<='+errNumber+'}',str(r1.seq[:maxPrimerLen+primerLocBuf]),flags=regex.BESTMATCH)
            if m1==None:
                # Save this pair of reads to untrimmed sequences
                return([[None,None],[r1,r2]],[],False)
            else:
                primerNum=goodPrimerNums[list(m1.groups()).index(m1[0])]
        else:
            return([[None,None],[r1,r2]],[],False)
    else:
        primerNum=bestPrimer
    # Find primer at the 5'-end of R2 read
    if readsFileR2:
        # asign paired primer num to primerPairNum, because all primers are interleaved in primer file
        primerPairNum = interleavedPrimerNum(primerNum)
        m3=regex.search(r'(?:'+primersR2_5[primerPairNum]+'){e<='+errNumber+'}',str(r2.seq[:maxPrimerLen+primerLocBuf]),flags=regex.BESTMATCH)
        if m3==None:
            # If user wants to identify hetero- and homodimers of primers
            if idimer or insa:
                readHashes=set()
                for l in primerR2_5_hashLens:
                    hashes,lens=makeHashes(str(r2.seq[:maxPrimerLen+primerLocBuf]),l)
                    readHashes.update(hashes)
                matchedPrimers={}
                for rh in readHashes:
                    if rh in primerR2_5_hashes.keys():
                        for a in primerR2_5_hashes[rh]:
                            if a not in matchedPrimers.keys():
                                matchedPrimers[a]=1
                            else:
                                matchedPrimers[a]+=1
                bestPrimer=None
                bestPrimerValue=None
                goodPrimers=[]
                goodPrimerNums=[]
                for key,item in sorted(matchedPrimers.items(),key=itemgetter(1),reverse=True):
                    if bestPrimer==None:
                        bestPrimer=key
                        bestPrimerValue=item
                        continue
                    if item>=bestPrimerValue-1:
                        goodPrimers.append(primersR2_5[key])
                        goodPrimerNums.append(key)
                    else: break
                if bestPrimer!=None:
                    m3=regex.search(r''+primersR2_5[bestPrimer]+'{e<='+errNumber+'}',str(r2.seq[:maxPrimerLen+primerLocBuf]),flags=regex.BESTMATCH)
                else:
                    return([[None,None],[r1,r2]],[],False)
##                    m3=regex.search(r'(?:'+'|'.join(primersR2_5)+'){e<='+errNumber+'}',str(r2.seq[:maxPrimerLen+primerLocBuf]),flags=regex.BESTMATCH)
                # Use result of searching 5'-primer
                if m3==None:
                    if len(goodPrimers)>0:
                        m3=regex.search(r'(?:'+'|'.join(goodPrimers)+'){e<='+errNumber+'}',str(r2.seq[:maxPrimerLen+primerLocBuf]),flags=regex.BESTMATCH)
                        if m3==None:
                            # Save this pair of reads to untrimmed sequences
                            return([[None,None],[r1,r2]],[],False)
                        else:
                            primerNum2=goodPrimerNums[list(m3.groups()).index(m3[0])]
                    else:
                        return([[None,None],[r1,r2]],[],False)
                else:
                    primerNum2=bestPrimer
                if not rnsa:
                    # If we found two different, two primer must be paired correctly
                    if abs(primerNum - primerNum2) != 1 or max(primerNum, primerNum2) % 2 == 0:
                        return([[None,None],[r1,r2]],[],[primerNum,primerNum2])
            else:
                # Save this pair of reads to untrimmed sequences
                return([[None,None],[r1,r2]],[],False)
        else:
            primerNum2=primerPairNum
    # Find primer at the 3'-end of R1 read
    # errNumber in 3p end
    errNumberDescreased=int(int(errNumber)*minPrimer3Len/len(primersR1_3[primerNum2][:-2]))
    m2=regex.search(r'(?:'+primersR1_3[primerNum2][:minPrimer3Len]+')){e<='+str(errNumberDescreased)+'}',str(r1.seq[-maxPrimerLen-primerLocBuf:]),flags=regex.BESTMATCH)
    if m2!=None:
        lenR1_3primer=maxPrimerLen+primerLocBuf-m2.span()[0]
        if lenR1_3primer > len(primersR1_3[primerNum2]) - 2:
            m2=None
        else:
            hd2=hamming2(r1.seq[-lenR1_3primer:],primersR1_3[primerNum2][1:1+lenR1_3primer])
            errNumberDescreased2=int(int(errNumber)*lenR1_3primer/len(primersR1_3[primerNum2][:-2]))
            if hd2 > int(errNumberDescreased2):
                m2=None
    if not primer3absent and m2==None:
        # Save this pair of reads to untrimmed sequences
        return([[None,None],[r1,r2]],[],[primerNum,primerNum2])
    # Find primer at the 3'-end of R2 read
    if readsFileR2:
        errNumberDescreased=int(round(int(errNumber)*minPrimer3Len/len(primersR2_3[primerNum][:-2])))
        m4=regex.search(r'(?:'+primersR2_3[primerNum][:minPrimer3Len]+')){e<='+str(errNumberDescreased)+'}',str(r2.seq[-maxPrimerLen-primerLocBuf:]),flags=regex.BESTMATCH)
        if m4!=None:
            lenR2_3primer=maxPrimerLen+primerLocBuf-m4.span()[0]
            if lenR2_3primer > len(primersR2_3[primerNum]) - 2:
                m4=None
            else:
                hd4=hamming2(r2.seq[-lenR2_3primer:],primersR2_3[primerNum][1:1+lenR2_3primer])
                errNumberDescreased4=int(int(errNumber)*lenR2_3primer/len(primersR2_3[primerNum][:-2]))
                if hd4 > int(errNumberDescreased4):
                    m4=None
        if not primer3absent and m4==None:
            # Save this pair of reads to untrimmed sequences
            return([[None,None],[r1,r2]],[],[primerNum,primerNum2])
    # If all primers were found
    # Trim sequences of primers and write them to result file
    if m2!=None:
        resList[0][0]=r1[m1.span()[1]:len(r1.seq)-maxPrimerLen-primerLocBuf+m2.span()[0]]
    else:
        resList[0][0]=r1[m1.span()[1]:]
    resList[0][0].description += " " + primersR1_5_names[primerNum]
    if readsFileR2:
        if m4!=None:
            resList[0][1]=r2[m3.span()[1]:len(r2.seq)-maxPrimerLen-primerLocBuf+m4.span()[0]]
        else:
            resList[0][1]=r2[m3.span()[1]:]
        resList[0][1].description += " " + primersR2_5_names[primerNum2]
    # discard reads length < 20 after primer-trimming
    if len(resList[0][0].seq) < 20 or len(resList[0][1].seq) < 20:
        return([[None,None],[r1,r2]],[],[primerNum,primerNum2])
    # Save number of errors and primers sequences
    # [number of primer,difs1,difs2,difs3,difs4,]
    # Each dif is a set of (# of mismatches,# of insertions,# of deletions,primer_seq)
    if primersStatistics:
        difs1=countDifs(m1[0],primersR1_5[primerNum][1:-1])
        if m2!=None: difs2=countDifs(m2[0],primersR1_3[primerNum2][1:-1])
        else: difs2=(0,0,0,'')
        if readsFileR2: difs3=countDifs(m3[0],primersR2_5[primerNum2][1:-1])
        else: difs3=(0,0,0,'')
        if readsFileR2 and m4!=None: difs4=countDifs(m4[0],primersR2_3[primerNum][1:-1])
        else: difs4=(0,0,0,'')
        return (resList,[[primerNum,primerNum2],difs1,difs2,difs3,difs4],False)
    else:
        return (resList,[],False)
    
if __name__ == "__main__":    
    # Section of reading arguments
    par=argparse.ArgumentParser(description='This script cuts primers from reads sequences')
    par.add_argument('--readsFile_r1','-r1',dest='readsFile1',type=str,help='file with R1 reads of one sample',required=True)
    par.add_argument('--readsFile_r2','-r2',dest='readsFile2',type=str,help='file with R2 reads of one sample',required=False)
    par.add_argument('--primersFile','-pr',dest='primersFile',type=str,help='fasta-file with sequences of primers on the 5\'(forward)-ends of R1 and R2 reads, paired primers should be written interleaved as >forward_primer_1 >reverse_primer_1 >forward_primer_2 >reverse_primer_2',required=True)
    par.add_argument('--trimmedReadsR1','-tr1',dest='trimmedReadsR1',type=str,help='name of file for trimmed R1 reads',required=True)
    par.add_argument('--trimmedReadsR2','-tr2',dest='trimmedReadsR2',type=str,help='name of file for trimmed R2 reads',required=False)
    par.add_argument('--untrimmedReadsR1','-utr1',dest='untrimmedReadsR1',type=str,help='name of file for untrimmed R1 reads. If you want to write reads that has not been trimmed to the same file as trimmed reads, type the same name',required=True)
    par.add_argument('--untrimmedReadsR2','-utr2',dest='untrimmedReadsR2',type=str,help='name of file for untrimmed R2 reads. If you want to write reads that has not been trimmed to the same file as trimmed reads, type the same name',required=False)
    par.add_argument('--primersStatistics','-stat',dest='primersStatistics',type=str,help='name of file for statistics of errors in primers. This works only for paired-end reads with primers at 3\'- and 5\'-ends',required=False)
    par.add_argument('--error-number','-err',dest='errNumber',type=int,help='number of errors (substitutions, insertions, deletions) that allowed during searching primer sequence in a read sequence. Default: 5',default=5)
    par.add_argument('--primer-location-buffer','-plb',dest='primerLocBuf',type=int,help='Buffer of primer location in the read from the end. Default: 10',default=10)
    par.add_argument('--min-primer3-length','-primer3len',dest='minPrimer3Len',type=int,help="Minimal length of primer on the 3'-end to trim. Use this parameter, if you are ready to trim only part of primer sequence of the 3'-end of read",default=6)
    par.add_argument('--primer3-absent','-primer3',dest='primer3absent',action='store_true',help="if primer at the 3'-end may be absent, use this parameter")
    par.add_argument('--identify-dimers','-idimer',dest='idimer',type=str,help='use this parameter if you want to get statistics of homo- and heterodimer formation. Choose file to which statistics of primer-dimers will be written. This parameter may slightly decrease the speed of analysis')
    par.add_argument('--identify-nsa','-insa',dest='insa',type=str,help='use this parameter if you want to get statistics of primers non-specific amplification products. Choose file to which statistics will be written. This parameter may slightly decrease the speed of analysis')
    par.add_argument('--nsa-reserve','-rnsa',dest='rnsa',action='store_true',help="if want to reserve non-specific amplcons, use this parameter")
    par.add_argument('--threads','-t',dest='threads',type=int,help='number of threads',default=2)
    par.add_argument('--version','-v',action='version',help='print version information',version="cutPrimers version " + __version__ +", https://github.com/ray1919/cutPrimers")
    args=par.parse_args()
    print('The command was:\n',' '.join(sys.argv))
    readsFileR1=args.readsFile1
    readsFileR2=args.readsFile2
    primersFile=args.primersFile
    primer3absent=args.primer3absent
    minPrimer3Len=args.minPrimer3Len+1
    errNumber=str(args.errNumber)
    primerLocBuf=args.primerLocBuf
    primersStatistics=args.primersStatistics
    idimer=args.idimer
    insa=args.insa
    rnsa=args.rnsa
    try:
        if args.trimmedReadsR1[-3:]!='.gz':
            trimmedReadsR1=open(args.trimmedReadsR1,'w')
        else:
            trimmedReadsR1=gzip.open(args.trimmedReadsR1,'wt')
    except FileNotFoundError:
        print('########')
        print('ERROR! Could not create file:',args.trimmedReadsR1)
        print('########')
        exit(1)
    if args.trimmedReadsR2:
        try:
            if args.trimmedReadsR2[-3:]!='.gz':
                trimmedReadsR2=open(args.trimmedReadsR2,'w')
            else:
                trimmedReadsR2=gzip.open(args.trimmedReadsR2,'wt')
        except FileNotFoundError:
            print('########')
            print('ERROR! Could not create file:',args.trimmedReadsR2)
            print('########')
            exit(1)
        if args.untrimmedReadsR1==args.trimmedReadsR1:
            untrimmedReadsR1=trimmedReadsR1
        else:
            try:
                if args.untrimmedReadsR1[-3:]!='.gz':
                    untrimmedReadsR1=open(args.untrimmedReadsR1,'w')
                else:
                    untrimmedReadsR1=gzip.open(args.untrimmedReadsR1,'wt')
            except FileNotFoundError:
                print('########')
                print('ERROR! Could not create file:',args.untrimmedReadsR1)
                print('########')
                exit(1)
    if args.untrimmedReadsR2:
        if args.untrimmedReadsR2==args.trimmedReadsR2:
            untrimmedReadsR2=trimmedReadsR2
        else:
            try:
                if args.untrimmedReadsR2[-3:]!='.gz':
                    untrimmedReadsR2=open(args.untrimmedReadsR2,'w')
                else:
                    untrimmedReadsR2=gzip.open(args.untrimmedReadsR2,'wt')
            except FileNotFoundError:
                print('########')
                print('ERROR! Could not create file:',args.untrimmedReadsR2)
                print('########')
                exit(1)
    if (idimer or insa) and not readsFileR2:
#   if idimer and not readsFileR2:
        print('Warning! You did not provide R2-file so parameter "-idimer/insa" will be ignored')
        idimer=None
        insa=None
    if idimer:
        try:
            idimerFile=open(idimer,'w')
        except FileNotFoundError:
            print('########')
            print('ERROR! Could not create file:',idimer)
            print('########')
            exit(1)
        primerDimers={}
    if insa:
        try:
            insaFile=open(insa,'w')
        except FileNotFoundError:
            print('########')
            print('ERROR! Could not create file:',insa)
            print('########')
            exit(1)
        primerNSAs={}
    if primersStatistics:
        primersStatistics=open(args.primersStatistics,'w')
        primersStatisticsPos=open(args.primersStatistics[:-4]+'_poses.tab','w')
        primersStatisticsType=open(args.primersStatistics[:-4]+'_types.tab','w')
    threads=int(args.threads)

    # Read fasta-files with sequences of primers
    print('Reading files of primers...')
    lastPrimerNum=0
    # maxPrimerLen - variable that contains length of the longest primer
    maxPrimerLen=0
    # primers in R1 on the 5'-end
    primersR1_5=[]
    primersR1_5_names=[]
    primerR1_5_hashes={}
    primerR1_5_hashLens=set()
    i=0
    try:
        for r in SeqIO.parse(primersFile,'fasta'):
            primersR1_5_names.append(r.name)
            primersR1_5.append('('+str(r.seq).upper()+')')
            partLens=math.floor(len(r.seq)/(int(errNumber)+1))
            hashes,lens=makeHashes(str(r.seq).upper(),partLens)
            primerR1_5_hashLens.update(lens)
            for h in hashes:
                if h in primerR1_5_hashes.keys():
                    primerR1_5_hashes[h].append(i)
                else:
                    primerR1_5_hashes[h]=[i]
            if len(r.seq)>maxPrimerLen:
                maxPrimerLen=len(r.seq)
            i+=1
    except FileNotFoundError:
        print('########')
        print('ERROR! File not found:',primersFile)
        print('########')
        exit(2)
    if not rnsa:
        # chech edit distance between each primer, warn is distance is less than -err setting
        i=1
        for s in primersR1_5[:-1]:
            for t in primersR1_5[i:]:
                newed=editdistance.eval(s, t)
                if newed <= int(errNumber):
                    print('########')
                    print('WARN! similar primers might cause confusion: ', s, '/', t)
                    print('--error-number was set to ', newed - 1 )
                    print('########')
                    errNumber=str(newed - 1)
            i+=1
    # primers in R2 on the 5'-end
    if readsFileR2:
        primersR2_5=primersR1_5
        primersR2_5_names=primersR1_5_names
        primerR2_5_hashes=primerR1_5_hashes
        primerR2_5_hashLens=primerR1_5_hashLens
    else:
        primersR2_5=None
    # primers in R1 on the 3'-end
    primersR1_3_names=[s + '_rc' for s in primersR1_5_names]
    primersR1_3=['('+revComplement(s[1:-1])+')' for s in primersR1_5]
    # primers in R2 on the 3'-end
    if readsFileR2:
        primersR2_3=primersR1_3
        primersR2_3_names=primersR1_3_names
    # Read file with R1 and R2 reads
    try:
        if readsFileR1[-3:]!='.gz':
            allWork=open(readsFileR1).read().count('\n')/4
        else:
            allWork=gzip.open(readsFileR1,'rt').read().count('\n')/4
    except FileNotFoundError:
        print('########')
        print('ERROR! Could not open file:',readsFileR1)
        print('########')
        exit(2)
    print('Reading input FASTQ-file(s)...')
    if readsFileR1[-3:]!='.gz':
        data1=SeqIO.parse(readsFileR1,'fastq')
    else:
        data1=SeqIO.parse(gzip.open(readsFileR1,'rt'),'fastq')
    if readsFileR2:
        try:
            if readsFileR2[-3:]!='.gz':
                data2=SeqIO.parse(readsFileR2,'fastq')
            else:
                data2=SeqIO.parse(gzip.open(readsFileR2,'rt'),'fastq')
        except FileNotFoundError:
            print('########')
            print('ERROR! Could not open file:',readsFileR2)
            print('########')
            exit(2)
    else:
        data2=['']*int(allWork)
    # Create Queue for storing result and Pool for multiprocessing
    primerErrorQ=[]
    p=Pool(threads,initializer,(maxPrimerLen,primerLocBuf,errNumber,primersR1_5,primersR1_3,primersR2_5,primersR2_3,
                                primerR1_5_hashes,primerR1_5_hashLens,primerR2_5_hashes,primerR2_5_hashLens,
                                readsFileR2,primersStatistics,idimer,primer3absent,minPrimer3Len))
    # Cutting primers and writing result immediately
    print('Trimming primers from reads...')
    doneWork=0
    showPercWork(0,allWork)
    for res in p.imap_unordered(trimPrimers,zip(data1,data2),10):
        doneWork+=1
        if doneWork & 500 == 0:
            showPercWork(doneWork,allWork)
        if primersStatistics and res[1]!=[]:
            primerErrorQ.append(res[1])
        if readsFileR2:
            if res[0][0][0] is not None and res[0][0][1] is not None:
                SeqIO.write(res[0][0][0],trimmedReadsR1,'fastq')
                SeqIO.write(res[0][0][1],trimmedReadsR2,'fastq')
            elif res[0][1][0] is not None and res[0][1][1] is not None:
                # If user want to identify primer-dimers
                maxDimerLen=maxPrimerLen*2
                if idimer and res[2] and len(res[0][1][0].seq) < maxDimerLen and len(res[0][1][1].seq) < maxDimerLen:
                    r1partSeq=str(res[0][1][0].seq)
                    r2partSeq=revComplement(str(res[0][1][1].seq))
                    difs=countDifs(r1partSeq,r2partSeq)
                    if sum(difs[0:2])<=int(errNumber):
                        # it is a primer-dimer
                        # and len(difs[3])>=len(primersR1_5[res[2][0]])
                        if primersR1_5_names[res[2][0]]+' & '+primersR2_5_names[res[2][1]] not in primerDimers.keys():
                            primerDimers[primersR1_5_names[res[2][0]]+' & '+primersR2_5_names[res[2][1]]]=1
                        else:
                            primerDimers[primersR1_5_names[res[2][0]]+' & '+primersR2_5_names[res[2][1]]]+=1
                if insa and res[2] and (len(res[0][1][0].seq) >= maxDimerLen or len(res[0][1][1].seq) >= maxDimerLen):
                    if primersR1_5_names[res[2][0]]+' & '+primersR2_5_names[res[2][1]] not in primerNSAs.keys():
                        primerNSAs[primersR1_5_names[res[2][0]]+' & '+primersR2_5_names[res[2][1]]]=1
                    else:
                        primerNSAs[primersR1_5_names[res[2][0]]+' & '+primersR2_5_names[res[2][1]]]+=1
                SeqIO.write(res[0][1][0],untrimmedReadsR1,'fastq')
                SeqIO.write(res[0][1][1],untrimmedReadsR2,'fastq')
            else:
                print('ERROR: nor the 1st item of function result list or 2nd contains anything')
                print('       This might caused by mismatch of read1/read2 names.')
                exit(3)
        else:
            if res[0][0][0] is not None:
                SeqIO.write(res[0][0][0],trimmedReadsR1,'fastq')
            elif res[0][1][0] is not None:
                SeqIO.write(res[0][1][0],untrimmedReadsR1,'fastq')
            else:
                print('ERROR: item of function result list contains nothing')
                print(res)
                exit(3)
    print()
    # primersErrors is a dictionary that contains errors in primers
    if args.primersStatistics:
        primersErrors={}
        # primersErrorsPos is a dictionary that contains statistics about location
        # of errors
        primersErrorsPos={}
        # primersErrorsType is a dictionary that contains statistics about type of error
        primersErrorsType={}
        print('Counting errors...')
        for item in primerErrorQ:
            itemkey = str(item[0][0]) + '+' + str(item[0][1])

            # If key for this primer has not been created, yet
            if not itemkey in primersErrors.keys():
                # For each primer of each pair we will gather the following values:
                # [(0)number of read pairs,
                # (1)number of primers without errors,
                # (2)number of primers with sequencing errors,
                # (3)number of primers with synthesis errors
                # The first item of list - F
                # The second - R
                primersErrors[itemkey]=[[0,0,0,0],[0,0,0,0]]

##          R                           F_reverse_complement
## R1 5'---------________________________---------3'
## R2 5'---------________________________---------3'
##          F                           R_reverse_complement

            # NOTICE: F is R2 5p primer
            # Increase number of read pairs
            primersErrors[itemkey][0][0]+=1
            primersErrors[itemkey][1][0]+=1
            # F-primers of pairs
            # The last variant is a case when we have single-end reads and 3' does not contain primer sequence
            # add to number of read pairs without errors
            if readsFileR2 and item[3][0:3]==(0,0,0):
                primersErrors[itemkey][0][1]+=1
            # If it was overlapping paired-end reads, we try to check if this is sequencing error
            elif item[2][3]!='' and item[3][3]!='':
                # Rererse complement one of primer sequences
                rev=str(Seq(item[2][3]).reverse_complement())
                a=pairwise2.align.globalms(rev,item[3][3],2,-1,-1.53,-0.1)
                # If found sequences are identical, it's a synthesis error
                if list(a[0][0])==list(a[0][1]):
                    primersErrors[itemkey][0][3]+=1
                    # Now we want to save information about error's location
                    poses,muts=getErrors(primersR2_5[item[0][0]][1:-1],item[3][3])
                    for p in poses:
                        if p not in primersErrorsPos.keys():
                            primersErrorsPos[p]=1
                        else:
                            primersErrorsPos[p]+=1
                    for m in muts:
                        if m not in primersErrorsType.keys():
                            primersErrorsType[m]=1
                        else:
                            primersErrorsType[m]+=1
                # Else it's a sequencing error
                else:
                    primersErrors[itemkey][0][2]+=1
            # Else we just save it as sequencing error
            else:
                primersErrors[itemkey][0][2]+=1
            # R-primers of pairs
            # For R-primer we always have sequence at least at 5' end of R1
            if item[1][0:3]==(0,0,0):
                primersErrors[itemkey][1][1]+=1
            # If it was overlapping paired-end reads, we try to check if this is sequencing error
            elif item[4][3]!='' and item[1][3]!='':
                # Rererse complement one of primer sequences
                rev=str(Seq(item[4][3]).reverse_complement())
                a=pairwise2.align.globalms(rev,item[1][3],2,-1,-1.53,-0.1)
                # If found sequences are identical, it's a synthesis error
                try:
                    if list(a[0][0])==list(a[0][1]):
                        primersErrors[itemkey][1][3]+=1
                        # Now we want to save information about error's location
                        poses,muts=getErrors(primersR1_5[item[0][0]][1:-1],item[1][3])
                        for p in poses:
                            if p not in primersErrorsPos.keys():
                                primersErrorsPos[p]=1
                            else:
                                primersErrorsPos[p]+=1
                        for m in muts:
                            if m not in primersErrorsType.keys():
                                primersErrorsType[m]=1
                            else:
                                primersErrorsType[m]+=1
                    # Else it's a sequencing error
                    else:
                        primersErrors[itemkey][1][2]+=1
                except IndexError:
                    print('IndexError!',a)
                    print(item)
                    exit(4)
            # Else we just save it as sequencing error
            else:
                primersErrors[itemkey][0][2]+=1
        #primersStatistics.write('Primer\tTotal_number_of_reads\tNumber_without_any_errors\t'
        #                        'Number_with_sequencing_errors\tNumber_with_synthesis_errors\n')
        primersStatistics.write('Primer_5p\tPrimer_3p\tTotal_number_of_reads_1\tNumber_without_any_errors_1\t'
                                'Number_with_sequencing_errors_1\tNumber_with_synthesis_errors_1\t'
                                'Total_number_of_reads_2\tNumber_without_any_errors_2\t'
                                'Number_with_sequencing_errors_2\tNumber_with_synthesis_errors_2\n')
        for key,item in primersErrors.items():

            item[0]=list(map(str,item[0]))
            item[1]=list(map(str,item[1]))

            (key1,key2) = key.split('+', 2)
            primersStatistics.write(primersR1_5_names[int(key1)]+'\t'+primersR1_5_names[int(key2)]+'\t'+'\t'.join(item[1])+'\t'+'\t'.join(item[0])+'\n')
        primersStatistics.close()

        primersStatisticsPos.write('Position_in_primer\tNumber_of_mutations\n')
        for key,item in primersErrorsPos.items():
            primersStatisticsPos.write(str(key)+'\t'+str(item)+'\n')
        primersStatisticsPos.close()

        primersStatisticsType.write('Error_type\tNumber_of_mutations\n')
        for key,item in primersErrorsType.items():
            primersStatisticsType.write(str(key)+'\t'+str(item)+'\n')
        primersStatisticsType.close()
    if idimer:
        idimerFile.write('Primer-dimer\tNumber of read pairs\n')
        for key,item in sorted(primerDimers.items(),key=itemgetter(1),reverse=True):
            idimerFile.write(key+'\t'+str(item)+'\n')
        idimerFile.close()
    if insa:
        insaFile.write('NSA-pair\tNumber of read pairs\n')
        for key,item in sorted(primerNSAs.items(),key=itemgetter(1),reverse=True):
            insaFile.write(key+'\t'+str(item)+'\n')
        insaFile.close()

    trimmedReadsR1.close()
    untrimmedReadsR1.close()
    if args.trimmedReadsR2:
        trimmedReadsR2.close()
        untrimmedReadsR2.close()


