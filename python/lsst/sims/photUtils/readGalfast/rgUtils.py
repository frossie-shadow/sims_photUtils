# -*- coding: utf-8 -*-
"""
Created on Wed Feb 25 14:07:03 2015

@author: Bryce Kalmbach
"""
import numpy as np
import eups
import os
import re

from lsst.sims.photUtils.Sed import Sed
from lsst.sims.photUtils.Bandpass import Bandpass
from lsst.sims.catalogs.measures.instance.fileMaps import SpecMap

__all__ = ["rgBase", "rgStar", "rgGalaxy"]

class rgBase():

    """
    This class is designed to provide methods that will be useful to both selectStarSED and selectGalaxySED.
    """

    def calcMagNorm(self, objectMags, sedObj, photObj, redshift = None, stepSize = 0.01, 
                    initBand = 0, filtRange = None):

        """
        This will find the magNorm value that gives the closest match to the magnitudes of the object
        using the matched SED.

        @param [in] objectMags are the magnitude values for the object with extinction matching that of
        the SED object. In the normal case using the selectSED routines above it will be dereddened mags.

        @param [in] sedObj is an Sed class instance that is set with the wavelength and flux of the
        matched SED

        @param [in] photObj is a PhotometryBase class instance with the Bandpasses set to those
        for the magnitudes given for the catalog object

        @param [in] redshift is the redshift of the object if the magnitude is observed

        @param [in] stepSize is the accuracy you want to match your magNorm within

        @param [in] initBand is the number of the bandpass in the magnitude array that you will use for
        the first naive match guess. Since imsimbandpass uses 500nm the best option is to use that closest to
        or encompassing 500 nm. If filtRange below is not None, then this is ignored and filtRange[0] is
        used in its place.

        @param [in] filtRange is a selected range of filters specified by their indices in the bandpassList
        to match up against. Used when missing data in some magnitude bands.

        @param [out] bestMagNorm is the magnitude normalization for the given magnitudes and SED
        """

        sedTest = Sed()
        sedTest.setSED(sedObj.wavelen, flambda = sedObj.flambda)
        if redshift is not None:
            sedTest.redshiftSED(redshift)
        imSimBand = Bandpass()
        imSimBand.imsimBandpass()
        #Use the object's magnitude in the index marked by initband as a naive estimate
        if filtRange is None:
            testMagNorm = objectMags[initBand]
        else:
            testMagNorm = objectMags[filtRange[0]]
        testFluxNorm = sedTest.calcFluxNorm(testMagNorm, imSimBand)
        normedSED = Sed()
        norm_wavelen, norm_fnu = sedTest.multiplyFluxNorm(testFluxNorm, wavelen = sedTest.wavelen,
                                                          fnu = sedTest.fnu)
        normedSED.setSED(norm_wavelen, fnu = norm_fnu)
        sedMags = np.array(photObj.manyMagCalc_list(normedSED))
        if filtRange is not None:
            sedMags = sedMags[filtRange]
            objectMags = objectMags[filtRange]
        diff = np.sort(objectMags - sedMags)
        diffSq = np.sum(diff**2, dtype=np.float64)
        diffSqPrev = np.sum(diff**2, dtype=np.float64)
        #Search either downward or upward along magNorm axis based upon greatest difference
        if diff[np.argmax(np.abs(diff))] < 0:
            alphaAdd = -stepSize
        else:
            alphaAdd = stepSize
        #Recursively adjust the magNorm until you reach a minimum in the sum squared error of the mags

        bestMagNorm = testMagNorm
        bestDiffSq = diffSq
        while diffSq - diffSqPrev < 1.0e-10:
            diffSqPrev = np.sum(diff**2, dtype=np.float64)
            testMagNorm += alphaAdd
            testFluxNorm = sedTest.calcFluxNorm(testMagNorm, imSimBand)
            norm_wavelen, norm_fnu = sedTest.multiplyFluxNorm(testFluxNorm, wavelen = sedTest.wavelen,
                                                              fnu = sedTest.fnu)
            normedSED.setSED(norm_wavelen, fnu = norm_fnu)
            sedMags = np.array(photObj.manyMagCalc_list(normedSED))
            if filtRange is not None:
                sedMags = sedMags[filtRange]
            diff = np.sort(objectMags - sedMags)
            diffSq = np.sum(diff**2, dtype=np.float64)
            if diffSq < bestDiffSq:
                bestMagNorm = testMagNorm
                bestDiffSq = diffSq

        return bestMagNorm

    def calcBasicColors(self, sedList, photObj, makeCopy = False):
        
        """
        This will calculate a set of colors from a list of SED objects when there is no need to redshift
        the SEDs.
        
        @param [in] sedList is the set of spectral objects from the models SEDs provided by loaders in
        rgStar or rgGalaxy. NOTE: Since this uses photometryBase.manyMagCalc_list the SED objects
        will be changed.
        
        @param [in] photObj is a PhotometryBase class instance with the Bandpasses set to those
        for the magnitudes given for the catalog object

        @param [in] makeCopy indicates whether or not to operate on copies of the SED objects in sedList 
        since this method will change the wavelength grid.
        
        @param [out] modelColors is the set of colors in the Bandpasses provided for the given sedList.
        """

        modelColors = []

        for specObj in sedList:
            if makeCopy==True:
                fileSED = Sed()
                fileSED.setSED(wavelen = specObj.wavelen, flambda = specObj.flambda)
                sEDMags = photObj.manyMagCalc_list(fileSED)
            else:
                sEDMags = photObj.manyMagCalc_list(specObj)
            colorInfo = []
            for filtNum in range(0, len(photObj.bandpassDict)-1):
                colorInfo.append(sEDMags[filtNum] - sEDMags[filtNum+1])
            modelColors.append(colorInfo)

        return modelColors
        
    def deReddenMags(self, ebvVals, catMags, extCoeffs):
        
        """
        This will correct for extinction effects in a set of catalog Magnitudes.
        
        @param [in] ebvVals is a list of ebv Values from calculateEBV in ebv.py or given by user that
        correspond to the same set of objects as the set of magnitudes.
        
        @param [in] catMags is an array of the magnitudes of the catalog objects.
        
        @param [in] extCoeffs is a list of the coefficients which should come
        from Schlafly and Finkbeiner (2011) (ApJ, 737, 103) for the same filters and in the same order
        as the catalog mags.
        
        @param [out] deRedMags is the array of corrected magnitudes.
        """

        deRedMags = catMags - np.outer(np.array(ebvVals), np.array(extCoeffs))

        return deRedMags

class rgStar(rgBase):

    """
    This class provides loading routines for the star SEDs currently in sims_sed_library. 
    To load one's own SED library, the user can subclass this and add their own loader following 
    the format of those included here.
    """

    def __init__(self, sEDDir = None, kuruczDir = None, mltDir = None, wdDir = None):

        """
        @param [in] sEDDir is a place to specify a different path to a directory that follows the same
        directory structure as SIMS_SED_LIBRARY. For instance, a different version of the LSST
        SIMS_SED_LIBRARY.

        @param [in] kuruczDir is a place to specify a different path to kurucz SED files than the
        files in the LSST sims_sed_library. If set to None it will default to the LSST library.
        Will probably be most useful for those who want to use loadGalfast without downloading the
        entire LSST sims_sed_library which contains much more than just the star SEDs.

        @param [in] mltDir is the same as kuruczPath except that it specifies a directory for the
        mlt SEDs
        
        @param [in] wdDir is the same as the previous two except that it specifies a path to an
        alternate white dwarf SED directory.                                 
        """

        if sEDDir is None:
            self.sEDDir = eups.productDir('sims_sed_library')
        else:
            self.sEDDir = sEDDir
        #Use SpecMap to pull the directory locations
        specMap = SpecMap()
        specMapDict = {}
        specFileStart = ['kp', 'burrows', 'bergeron'] #The beginning of filenames of different SED types
        specFileTypes = ['kurucz', 'mlt', 'wd']
        for specStart, specKey in zip(specFileStart, specFileTypes):
            for key, val in sorted(specMap.subdir_map.iteritems()):
                if re.match(key, specStart):
                    specMapDict[specKey] = str(val)
        
        if kuruczDir is None:
            self.kuruczDir = str(self.sEDDir + '/' + specMapDict['kurucz'] + '/')
        else:
            self.kuruczDir = kuruczDir

        if mltDir is None:
            self.mltDir = str(self.sEDDir + '/' + specMapDict['mlt'] + '/')
        else:
            self.mltDir = mltDir

        if wdDir is None:
            self.wdDir = str(self.sEDDir + '/' + specMapDict['wd'] + '/')
        else:
            self.wdDir = wdDir

    def loadKuruczSEDs(self, subset = None):
        """
        By default will load all seds in kurucz directory. The user can also define a subset of
        what's in the directory and load only those SEDs instead. Will skip over extraneous
        files in sed folder.

        @param [in] subset is the list of the subset of files wanted if one doesn't want all files
        in the kurucz directory.

        @param [out] sedList is the set of model SED spectra objects to be passed onto the matching
        routines.
        """
        files = []

        if subset is None:
            for fileName in os.listdir(self.kuruczDir):
                files.append(fileName)
        else:
            for fileName in subset:
                files.append(fileName)

        numFiles = len(files)
        numOn = 0

        sedList = []

        for fileName in files:
            if numOn % 100 == 0:
                print 'Loading %i of %i: Kurucz SEDs' % (numOn, numFiles)
 
            try:
                spec = Sed()
                spec.readSED_flambda(str(self.kuruczDir + '/' + fileName))

                logZTimesTen, temp, gravity, fineTemp = [x.split(".")[0] for x in fileName.split("_")]

                if logZTimesTen[1] == 'm':
                    spec.logZ = -1.0 * float(logZTimesTen[2:]) * 0.1
                else:
                    spec.logZ = float(logZTimesTen[2:]) * 0.1

                spec.logg = float(gravity[1:]) * 0.1
                spec.temp = float(fineTemp)
                spec.name = fileName

            except:
                continue

            sedList.append(spec)

            numOn += 1

        return sedList

    def loadmltSEDs(self, subset = None):

        """
        By default will load all seds in mlt directory. The user can also define a subset of
        what's in the directory and load only those SEDs instead. Will skip over extraneous
        files in sed folder.

        @param [in] subset is the list of the subset of files wanted if one doesn't want all files
        in the mlt directory.

        @param [out] sedList is the set of model SED spectra objects to be passed onto the matching
        routines.
        """

        files = []

        if subset is None:
            for fileName in os.listdir(self.mltDir):
                files.append(fileName)
        else:
            for fileName in subset:
                files.append(fileName)

        numFiles = len(files)
        numOn = 0

        sedList = []

        for fileName in files:
            if numOn % 100 == 0:
                print 'Loading %i of %i: MLT SEDs' % (numOn, numFiles)
 
            try:
                spec = Sed()
                spec.readSED_flambda(str(self.mltDir + '/' + fileName))
                spec.name = fileName

            except:
                continue

            sedList.append(spec)

            numOn += 1

        return sedList


    def loadwdSEDs(self, subset = None):

        """
        By default will load all seds in wd directory. The user can also define a subset of                                                                           
        what's in the directory and load only those SEDs instead. Will skip over extraneous
        files in sed folder.

        @param [in] subset is the list of the subset of files wanted if one doesn't want all files
        in the kurucz directory.

        @param [out] sedListH is the set of model SED spectra objects for Hydrogen WDs to be passed onto
        the matching routines.
        
        @param [out] sedListHE is the set of model SED spectra objects for Helium WDs to be passed onto
        the matching routines.
        """
        files = []

        if subset is None:
            for fileName in os.listdir(self.wdDir):
                files.append(fileName)
        else:
            for fileName in subset:
                files.append(fileName)

        numFiles = len(files)
        numOn = 0

        sedListH = []
        sedListHE = []

        for fileName in files:
            if numOn % 100 == 0:
                print 'Loading %i of %i: WD SEDs' % (numOn, numFiles)
 
            try:
                spec = Sed()
                spec.readSED_flambda(str(self.wdDir + '/' + fileName))
                spec.name = fileName                
                if fileName.split("_")[1] == 'He':      
                    sedListHE.append(spec)
                else:
                    sedListH.append(spec)

            except:
                continue

            numOn += 1

        return sedListH, sedListHE

class rgGalaxy(rgBase):

    """
    This class provides loading routines for the galaxy SEDs currently in sims_sed_library. 
    To load one's own SED library, the user can subclass this and add their own loader following 
    the format of those included here.
    """

    def __init__(self, galDir = None):
        
        """
        @param [in] galDir is the directory where the galaxy SEDs are stored
        """

        if galDir is None:
            #Use SpecMap to pull in directory's location in LSST Stack
            specMap = SpecMap()
            specFileStart = 'Exp' #Start of sample BC03 name in sims_sed_library
            for key, val in sorted(specMap.subdir_map.iteritems()):
                if re.match(key, specFileStart):
                    galSpecDir = str(val)
            self.galDir = str(eups.productDir('sims_sed_library') + '/' + galSpecDir)            
        else:
            self.galDir = galDir    
    
    def loadBC03(self, subset = None):

        """
        This loads the Bruzual and Charlot SEDs that are currently in the SIMS_SED_LIBRARY.
        If the user wants to use different SEDs another loading method can be created and used in place
        of this.
        
        @param [in] subset is the list of the subset of files in the galDir that the user
        can specify if using all the SEDs in the directory is not desired.

        @param [out] sedList is the set of model SED spectra objects to be passed onto the matching routines.
        """

        files = []

        if subset is None:
            for fileName in os.listdir(self.galDir):
                files.append(fileName)
        else:
            for fileName in subset:
                files.append(fileName)

        numFiles = len(files)
        numOn = 0

        sedList = []

        for fileName in files:
            if numOn % 100 == 0:
                print 'Loading %i of %i: BC Galaxy SEDs' % (numOn, numFiles)
 
            try:
                spec = Sed()
                spec.readSED_flambda(str(self.galDir + '/' + fileName))
                spec.name = fileName
                fileNameAsList = fileName.split('.')
                spec.type = fileNameAsList[0]
                spec.age = float(fileNameAsList[1])
                metallicity = fileNameAsList[2].split('Z')[0]
                #Final form is z/zSun
                spec.metallicity = float(metallicity) * (10 ** ((len(metallicity)-1)*-1))

            except:
                continue

            sedList.append(spec)

            numOn += 1

        return sedList
