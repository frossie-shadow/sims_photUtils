from builtins import zip
from builtins import str
from builtins import range
import unittest
import os
import numpy as np
import lsst.utils
import lsst.utils.tests
from lsst.sims.photUtils.selectStarSED import selectStarSED
from lsst.sims.photUtils.selectGalaxySED import selectGalaxySED
from lsst.sims.photUtils.matchUtils import matchBase
from lsst.sims.photUtils.matchUtils import matchStar
from lsst.sims.photUtils.matchUtils import matchGalaxy
from lsst.sims.photUtils.EBV import EBVbase as ebv
from lsst.sims.photUtils.Sed import Sed
from lsst.sims.photUtils.Bandpass import Bandpass
from lsst.sims.photUtils import BandpassDict
from lsst.utils import getPackageDir
from lsst.sims.utils.CodeUtilities import sims_clean_up


def setup_module(module):
    lsst.utils.tests.init()


class TestMatchBase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):

        cls.galDir = os.path.join(getPackageDir('sims_photUtils'), 'tests/cartoonSedTestData/galaxySed/')
        cls.filterList = ('u', 'g', 'r', 'i', 'z')

    @classmethod
    def tearDownClass(cls):
        sims_clean_up()
        del cls.galDir
        del cls.filterList

    def testCalcMagNorm(self):

        """Tests the calculation of magnitude normalization for an SED with the given magnitudes
        in the given bandpasses."""

        testUtils = matchBase()
        bandpassDir = os.path.join(lsst.utils.getPackageDir('throughputs'), 'sdss')
        testPhot = BandpassDict.loadTotalBandpassesFromFiles(self.filterList,
                                                             bandpassDir = bandpassDir,
                                                             bandpassRoot = 'sdss_')

        unChangedSED = Sed()
        unChangedSED.readSED_flambda(str(self.galDir + os.listdir(self.galDir)[0]))

        imSimBand = Bandpass()
        imSimBand.imsimBandpass()
        testSED = Sed()
        testSED.setSED(unChangedSED.wavelen, flambda = unChangedSED.flambda)
        magNorm = 20.0
        redVal = 0.1
        testSED.redshiftSED(redVal)
        fluxNorm = testSED.calcFluxNorm(magNorm, imSimBand)
        testSED.multiplyFluxNorm(fluxNorm)
        sedMags = testPhot.magListForSed(testSED)
        stepSize = 0.001
        testMagNorm = testUtils.calcMagNorm(sedMags, unChangedSED, testPhot, redshift = redVal)
        # Test adding in mag_errors. If an array of np.ones is passed in we should get same result
        testMagNormWithErr = testUtils.calcMagNorm(sedMags, unChangedSED, testPhot,
                                                   mag_error = np.ones(len(sedMags)), redshift = redVal)
        # Also need to add in test for filtRange
        sedMagsIncomp = sedMags
        sedMagsIncomp[1] = None
        filtRangeTest = [0, 2, 3, 4]
        testMagNormFiltRange = testUtils.calcMagNorm(sedMagsIncomp, unChangedSED, testPhot,
                                                     redshift = redVal, filtRange = filtRangeTest)
        self.assertAlmostEqual(magNorm, testMagNorm, delta = stepSize)
        self.assertAlmostEqual(magNorm, testMagNormWithErr, delta = stepSize)
        self.assertAlmostEqual(magNorm, testMagNormFiltRange, delta = stepSize)

    def testCalcBasicColors(self):

        """Tests the calculation of the colors of an SED in given bandpasses."""

        testUtils = matchBase()
        testSED = Sed()
        bandpassDir = os.path.join(lsst.utils.getPackageDir('throughputs'), 'sdss')
        testPhot = BandpassDict.loadTotalBandpassesFromFiles(self.filterList,
                                                             bandpassDir = bandpassDir,
                                                             bandpassRoot = 'sdss_')

        testSED.readSED_flambda(str(self.galDir + os.listdir(self.galDir)[0]))
        testMags = testPhot.magListForSed(testSED)
        testColors = []
        for filtNum in range(0, len(self.filterList)-1):
            testColors.append(testMags[filtNum] - testMags[filtNum+1])

        testOutput = testUtils.calcBasicColors([testSED], testPhot)
        np.testing.assert_equal([testColors], testOutput)

    def testSEDCopyBasicColors(self):

        """Tests that when makeCopy=True in calcBasicColors the SED object is unchanged after calling
        and that colors are still accurately calculated"""

        testUtils = matchBase()
        testSED = Sed()
        copyTest = Sed()
        bandpassDir = os.path.join(lsst.utils.getPackageDir('throughputs'), 'sdss')
        testPhot = BandpassDict.loadTotalBandpassesFromFiles(self.filterList,
                                                             bandpassDir = bandpassDir,
                                                             bandpassRoot = 'sdss_')
        testSED.readSED_flambda(str(self.galDir + os.listdir(self.galDir)[0]))
        copyTest.setSED(wavelen = testSED.wavelen, flambda = testSED.flambda)
        testLambda = copyTest.wavelen[0]
        testMags = testPhot.magListForSed(testSED)
        testColors = []
        for filtNum in range(0, len(self.filterList)-1):
            testColors.append(testMags[filtNum] - testMags[filtNum+1])
        testOutput = testUtils.calcBasicColors([copyTest], testPhot, makeCopy=True)

        self.assertEqual(testLambda, copyTest.wavelen[0])
        np.testing.assert_equal([testColors], testOutput)

    def testDeReddenMags(self):

        """Test that consistent numbers come out of deReddening procedure"""

        am = 0.5
        coeffs = np.ones(5)
        mags = np.arange(2, -3, -1)

        testDeRed = matchBase().deReddenMags(am, mags, coeffs)

        # Test Output
        np.testing.assert_equal(testDeRed, [mags-(am*coeffs)])


class TestMatchStar(unittest.TestCase):

    @classmethod
    def setUpClass(cls):

        # Left this in after removing loading SEDs so that we can make sure that if the structure of
        # sims_sed_library changes in a way that affects testMatchSEDs we can detect it.

        cls.kmTestName = 'km99_9999.fits_g99_9999'
        cls.mTestName = 'm99.99Full.dat'

        # Set up Test Spectra Directory
        cls.testSpecDir = os.path.join(getPackageDir('sims_photUtils'), 'tests/cartoonSedTestData/starSed/')
        cls.testKDir = str(cls.testSpecDir + 'kurucz/')
        cls.testMLTDir = str(cls.testSpecDir + 'mlt/')
        cls.testWDDir = str(cls.testSpecDir + 'wDs/')

    def testLoadKurucz(self):
        """Test SED loading algorithm by making sure SEDs are all accounted for """
        # Test Matching to Kurucz SEDs
        loadTestKurucz = matchStar(kuruczDir = self.testKDir)
        testSEDs = loadTestKurucz.loadKuruczSEDs()

        # Read in a list of the SEDs in the kurucz test sed directory
        testKuruczList = os.listdir(self.testKDir)

        # First make sure that all SEDs are correctly accounted for if no subset provided
        testNames = []
        for testSED in testSEDs:
            testNames.append(testSED.name)

        # Python 3 replaces assertItemsEqual() with assertCountEqual()
        if hasattr(self, 'assertItemsEqual'):
            self.assertItemsEqual(testKuruczList, testNames)
        else:
            self.assertCountEqual(testKuruczList, testNames)

        # Test same condition if subset is provided
        testSubsetList = ['km01_7000.fits_g40_7140.gz', 'kp01_7000.fits_g40_7240.gz']
        testSEDsSubset = loadTestKurucz.loadKuruczSEDs(subset = testSubsetList)

        # Next make sure that correct subset loads if subset is provided
        testSubsetNames = []
        testSubsetLogZ = []
        testSubsetLogG = []
        testSubsetTemp = []
        for testSED in testSEDsSubset:
            testSubsetNames.append(testSED.name)
            testSubsetLogZ.append(testSED.logZ)
            testSubsetLogG.append(testSED.logg)
            testSubsetTemp.append(testSED.temp)

        # Python 3 replaces assertItemsEqual() with assertCountEqual()
        if hasattr(self, 'assertItemsEqual'):
            self.assertItemsEqual(testSubsetList, testSubsetNames)
        else:
            self.assertCountEqual(testSubsetList, testSubsetNames)

        self.assertEqual(testSubsetLogZ, [-0.1, 0.1])  # Test both pos. and neg. get in right
        self.assertEqual(testSubsetLogG, [4.0, 4.0])  # Test storage of logg and temp
        self.assertEqual(testSubsetTemp, [7140, 7240])

        # Test that attributes have been assigned
        for testSED in testSEDsSubset:
            self.assertIsNotNone(testSED.name)
            self.assertIsNotNone(testSED.logZ)
            self.assertIsNotNone(testSED.logg)
            self.assertIsNotNone(testSED.temp)

    def testLoadMLT(self):
        """Test SED loading algorithm by making sure SEDs are all accounted for"""
        # Test Matching to mlt SEDs
        loadTestMLT = matchStar(mltDir = self.testMLTDir)
        testSEDs = loadTestMLT.loadmltSEDs()

        # Read in a list of the SEDs in the mlt test sed directory
        testMLTList = os.listdir(self.testMLTDir)

        # First make sure that all SEDs are correctly accounted for if no subset provided
        testNames = []
        for testSED in testSEDs:
            testNames.append(testSED.name)

        # Python 3 replaces assertItemsEqual() with assertCountEqual()
        if hasattr(self, 'assertItemsEqual'):
            self.assertItemsEqual(testMLTList, testNames)
        else:
            self.assertCountEqual(testMLTList, testNames)

        # Next make sure that correct subset loads if subset is provided
        testSubsetList = testMLTList[0:2]
        testSEDsubset = loadTestMLT.loadmltSEDs(subset = testSubsetList)
        testSubsetNames = []
        for testSED in testSEDsubset:
            testSubsetNames.append(testSED.name)

        # Python 3 replaces assertItemsEqual() with assertCountEqual()
        if hasattr(self, 'assertItemsEqual'):
            self.assertItemsEqual(testSubsetList, testSubsetNames)
        else:
            self.assertCountEqual(testSubsetList, testSubsetNames)

        # Test that attributes have been assigned
        for testSED in testSEDsubset:
            self.assertIsNotNone(testSED.name)

    def testLoadWD(self):
        """Test SED loading algorithm by making sure SEDs are all accounted for and
        that there are separate lists for H and HE."""
        # Test Matching to WD SEDs
        loadTestWD = matchStar(wdDir = self.testWDDir)
        testSEDsH, testSEDsHE = loadTestWD.loadwdSEDs()

        # Add extra step because WD SEDs are separated into helium and hydrogen
        testNames = []
        for testH in testSEDsH:
            testNames.append(testH.name)
        for testHE in testSEDsHE:
            testNames.append(testHE.name)

        # Read in a list of the SEDs in the wd test sed directory
        testWDList = os.listdir(self.testWDDir)

        # First make sure that all SEDs are correctly accounted for if no subset provided

        # Python 3 replaces assertItemsEqual() with assertCountEqual()
        if hasattr(self, 'assertItemsEqual'):
            self.assertItemsEqual(testNames, testWDList)
        else:
            self.assertCountEqual(testNames, testWDList)

        # Test same condition if subset is provided
        testSubsetList = ['bergeron_10000_75.dat_10100.gz', 'bergeron_He_9000_80.dat_9400.gz']

        testSEDsSubsetH, testSEDsSubsetHE = selectStarSED(wdDir=
                                                          self.testWDDir).loadwdSEDs(subset=
                                                                                     testSubsetList)

        testNamesSubset = []
        for testH in testSEDsSubsetH:
            testNamesSubset.append(testH.name)
        for testHE in testSEDsSubsetHE:
            testNamesSubset.append(testHE.name)

        # Next make sure that correct subset loads if subset is provided
        # Python 3 replaces assertItemsEqual() with assertCountEqual()
        if hasattr(self, 'assertItemsEqual'):
            self.assertItemsEqual(testNamesSubset, testSubsetList)
        else:
            self.assertCountEqual(testNamesSubset, testSubsetList)

        # Make sure that the names get separated into correct wd type
        self.assertEqual(testSEDsSubsetH[0].name, testSubsetList[0])
        self.assertEqual(testSEDsSubsetHE[0].name, testSubsetList[1])

    @classmethod
    def tearDownClass(cls):
        sims_clean_up()
        del cls.testSpecDir
        del cls.testKDir
        del cls.testMLTDir
        del cls.testWDDir

        del cls.kmTestName
        del cls.mTestName


class TestMatchGalaxy(unittest.TestCase):

    @classmethod
    def setUpClass(cls):

        # Set up Test Spectra Directory
        cls.testSpecDir = os.path.join(getPackageDir('sims_photUtils'), 'tests/cartoonSedTestData/galaxySed/')

        cls.filterList = ('u', 'g', 'r', 'i', 'z')

    def testLoadBC03(self):
        """Test Loader for Bruzual and Charlot Galaxies"""
        loadTestBC03 = matchGalaxy(galDir = self.testSpecDir)
        testSEDs = loadTestBC03.loadBC03()

        # Read in a list of the SEDs in the test galaxy sed directory
        testGalList = os.listdir(self.testSpecDir)

        # Make sure the names of seds in folder and set that was read in are the same
        # This also tests that the name attribute is assigned to each Spectrum object correctly
        testNames = []
        for testSED in testSEDs:
            testNames.append(testSED.name)

        # Python 3 replaces assertItemsEqual() with assertCountEqual()
        if hasattr(self, 'assertItemsEqual'):
            self.assertItemsEqual(testGalList, testNames)
        else:
            self.assertCountEqual(testGalList, testNames)

        # Test same condition if a subset is provided
        testSubsetList = testGalList[0:2]
        testSEDsubset = loadTestBC03.loadBC03(subset = testSubsetList)
        testSubsetNames = []
        for testSED in testSEDsubset:
            testSubsetNames.append(testSED.name)

        # Python 3 replaces assertItemsEqual() with assertCountEqual()
        if hasattr(self, 'assertItemsEqual'):
            self.assertItemsEqual(testSubsetList, testSubsetNames)
        else:
            self.assertCountEqual(testSubsetList, testSubsetNames)

        # Test that attributes have been assigned
        for testSED in testSEDsubset:
            self.assertIsNotNone(testSED.name)
            self.assertIsNotNone(testSED.type)
            self.assertIsNotNone(testSED.age)
            self.assertIsNotNone(testSED.metallicity)

    @classmethod
    def tearDownClass(cls):
        sims_clean_up()
        del cls.testSpecDir


class TestSelectGalaxySED(unittest.TestCase):

    @classmethod
    def setUpClass(cls):

        # Set up Test Spectra Directory
        cls.testSpecDir = os.path.join(getPackageDir('sims_photUtils'), 'tests/cartoonSedTestData/galaxySed/')

    def testMatchToRestFrame(self):
        """Test that Galaxies with no effects added into catalog mags are matched correctly."""
        rng = np.random.RandomState(42)
        galPhot = BandpassDict.loadTotalBandpassesFromFiles()

        imSimBand = Bandpass()
        imSimBand.imsimBandpass()

        testMatching = selectGalaxySED(galDir = self.testSpecDir)
        testSEDList = testMatching.loadBC03()

        testSEDNames = []
        testMags = []
        testMagNormList = []
        magNormStep = 1

        for testSED in testSEDList:

            getSEDMags = Sed()
            testSEDNames.append(testSED.name)
            getSEDMags.setSED(wavelen = testSED.wavelen, flambda = testSED.flambda)
            testMagNorm = np.round(rng.uniform(20.0, 22.0), magNormStep)
            testMagNormList.append(testMagNorm)
            fluxNorm = getSEDMags.calcFluxNorm(testMagNorm, imSimBand)
            getSEDMags.multiplyFluxNorm(fluxNorm)
            testMags.append(galPhot.magListForSed(getSEDMags))

        # Also testing to make sure passing in non-default bandpasses works
        # Substitute in nan values to simulate incomplete data.
        testMags[0][1] = np.nan
        testMags[0][2] = np.nan
        testMags[0][4] = np.nan
        testMags[1][1] = np.nan
        testMatchingResults = testMatching.matchToRestFrame(testSEDList, testMags,
                                                            bandpassDict = galPhot)
        self.assertEqual(None, testMatchingResults[0][0])
        self.assertEqual(testSEDNames[1:], testMatchingResults[0][1:])
        self.assertEqual(None, testMatchingResults[1][0])
        np.testing.assert_almost_equal(testMagNormList[1:], testMatchingResults[1][1:], decimal = magNormStep)

        # Test Match Errors
        errMags = np.array((testMags[2], testMags[2], testMags[2], testMags[2]))
        errMags[1, 1] += 1.  # Total MSE will be 2/(5 colors) = 0.4
        errMags[2, 0:2] = np.nan
        errMags[2, 3] += 1.  # Total MSE will be 2/(3 colors) = 0.667
        errMags[3, :] = None
        errSED = testSEDList[2]
        testMatchingResultsErrors = testMatching.matchToRestFrame([errSED], errMags,
                                                                  bandpassDict = galPhot)
        np.testing.assert_almost_equal(np.array((0.0, 0.4, 2./3.)), testMatchingResultsErrors[2][0:3],
                                       decimal = 3)
        self.assertEqual(None, testMatchingResultsErrors[2][3])

    def testReddeningException(self):
        """Test that if reddening=True in matchToObserved CatRA & CatDec are defined or exception is raised"""
        testException = selectGalaxySED(galDir = self.testSpecDir)
        testSEDList = testException.loadBC03()
        magnitudes = [[1.0, 2.0, 3.0, 4.0, 5.0], [1.0, 2.0, 3.0, 4.0, 5.0]]
        redshifts = [1.0, 1.0]
        self.assertRaises(RuntimeError, testException.matchToObserved, testSEDList, magnitudes, redshifts,
                          reddening = True)

    def testMatchToObserved(self):
        """Test that Galaxy SEDs with extinction or redshift are matched correctly"""
        rng = np.random.RandomState(42)
        galPhot = BandpassDict.loadTotalBandpassesFromFiles()

        imSimBand = Bandpass()
        imSimBand.imsimBandpass()

        testMatching = selectGalaxySED(galDir = self.testSpecDir)
        testSEDList = testMatching.loadBC03()

        testSEDNames = []
        testRA = []
        testDec = []
        testRedshifts = []
        testMagNormList = []
        magNormStep = 1
        extCoeffs = [1.8140, 1.4166, 0.9947, 0.7370, 0.5790, 0.4761]
        testMags = []
        testMagsRedshift = []
        testMagsExt = []

        for testSED in testSEDList:

            # As a check make sure that it matches when no extinction and no redshift are present
            getSEDMags = Sed()
            testSEDNames.append(testSED.name)
            getSEDMags.setSED(wavelen = testSED.wavelen, flambda = testSED.flambda)
            testMags.append(galPhot.magListForSed(getSEDMags))

            # Check Extinction corrections
            sedRA = rng.uniform(10, 170)
            sedDec = rng.uniform(10, 80)
            testRA.append(sedRA)
            testDec.append(sedDec)
            raDec = np.array((sedRA, sedDec)).reshape((2, 1))
            ebvVal = ebv().calculateEbv(equatorialCoordinates = raDec)
            extVal = ebvVal*extCoeffs
            testMagsExt.append(galPhot.magListForSed(getSEDMags) + extVal)

            # Setup magnitudes for testing matching to redshifted values
            getRedshiftMags = Sed()
            testZ = np.round(rng.uniform(1.1, 1.3), 3)
            testRedshifts.append(testZ)
            testMagNorm = np.round(rng.uniform(20.0, 22.0), magNormStep)
            testMagNormList.append(testMagNorm)
            getRedshiftMags.setSED(wavelen = testSED.wavelen, flambda = testSED.flambda)
            getRedshiftMags.redshiftSED(testZ)
            fluxNorm = getRedshiftMags.calcFluxNorm(testMagNorm, imSimBand)
            getRedshiftMags.multiplyFluxNorm(fluxNorm)
            testMagsRedshift.append(galPhot.magListForSed(getRedshiftMags))

        # Will also test in passing of non-default bandpass
        testNoExtNoRedshift = testMatching.matchToObserved(testSEDList, testMags, np.zeros(8),
                                                           reddening = False,
                                                           bandpassDict = galPhot)
        testMatchingEbvVals = testMatching.matchToObserved(testSEDList, testMagsExt, np.zeros(8),
                                                           catRA = testRA, catDec = testDec,
                                                           reddening = True, extCoeffs = extCoeffs,
                                                           bandpassDict = galPhot)
        # Substitute in nan values to simulate incomplete data and make sure magnorm works too.
        testMagsRedshift[0][1] = np.nan
        testMagsRedshift[0][3] = np.nan
        testMagsRedshift[0][4] = np.nan
        testMagsRedshift[1][1] = np.nan
        testMatchingRedshift = testMatching.matchToObserved(testSEDList, testMagsRedshift, testRedshifts,
                                                            dzAcc = 3, reddening = False,
                                                            bandpassDict = galPhot)

        self.assertEqual(testSEDNames, testNoExtNoRedshift[0])
        self.assertEqual(testSEDNames, testMatchingEbvVals[0])
        self.assertEqual(None, testMatchingRedshift[0][0])
        self.assertEqual(testSEDNames[1:], testMatchingRedshift[0][1:])
        self.assertEqual(None, testMatchingRedshift[1][0])
        np.testing.assert_almost_equal(testMagNormList[1:], testMatchingRedshift[1][1:],
                                       decimal = magNormStep)

        # Test Match Errors
        errMag = testMagsRedshift[2]
        errRedshift = testRedshifts[2]
        errMags = np.array((errMag, errMag, errMag, errMag))
        errRedshifts = np.array((errRedshift, errRedshift, errRedshift, errRedshift))
        errMags[1, 1] += 1.  # Total MSE will be 2/(5 colors) = 0.4
        errMags[2, 0:2] = np.nan
        errMags[2, 3] += 1.  # Total MSE will be 2/(3 colors) = 0.667
        errMags[3, :] = None
        errSED = testSEDList[2]
        testMatchingResultsErrors = testMatching.matchToObserved([errSED], errMags, errRedshifts,
                                                                 reddening = False,
                                                                 bandpassDict = galPhot,
                                                                 dzAcc = 3)
        np.testing.assert_almost_equal(np.array((0.0, 0.4, 2./3.)), testMatchingResultsErrors[2][0:3],
                                       decimal = 2)  # Give a little more leeway due to redshifting effects
        self.assertEqual(None, testMatchingResultsErrors[2][3])

    @classmethod
    def tearDownClass(cls):
        sims_clean_up()
        del cls.testSpecDir


class TestSelectStarSED(unittest.TestCase):

    @classmethod
    def setUpClass(cls):

        # Left this in after removing loading SEDs so that we can make sure that if the structure of
        # sims_sed_library changes in a way that affects testMatchSEDs we can detect it.

        cls.kmTestName = 'km99_9999.fits_g99_9999'
        cls.mTestName = 'm99.99Full.dat'

        # Set up Test Spectra Directory
        cls.testSpecDir = os.path.join(getPackageDir('sims_photUtils'), 'tests/cartoonSedTestData/starSed/')
        cls.testKDir = str(cls.testSpecDir + 'kurucz/')
        cls.testMLTDir = str(cls.testSpecDir + 'mlt/')
        cls.testWDDir = str(cls.testSpecDir + 'wDs/')

    def testReddeningException(self):
        """Test that if reddening=True in matchToObserved CatRA & CatDec are defined or exception is raised"""
        testException = selectStarSED(kuruczDir=self.testKDir,
                                      mltDir=self.testMLTDir,
                                      wdDir=self.testWDDir)
        testSEDList = testException.loadKuruczSEDs()
        magnitudes = [[1.0, 2.0, 3.0, 4.0, 5.0], [1.0, 2.0, 3.0, 4.0, 5.0]]
        self.assertRaises(RuntimeError, testException.findSED, testSEDList, magnitudes,
                          reddening = True)

    def testFindSED(self):
        """Pull SEDs from each type and make sure that each SED gets matched to itself.
        Includes testing with extinction and passing in only colors."""
        rng = np.random.RandomState(42)
        bandpassDir = os.path.join(lsst.utils.getPackageDir('throughputs'), 'sdss')
        starPhot = BandpassDict.loadTotalBandpassesFromFiles(('u', 'g', 'r', 'i', 'z'),
                                                             bandpassDir = bandpassDir,
                                                             bandpassRoot = 'sdss_')

        imSimBand = Bandpass()
        imSimBand.imsimBandpass()

        testMatching = selectStarSED(kuruczDir=self.testKDir,
                                     mltDir=self.testMLTDir,
                                     wdDir=self.testWDDir)
        testSEDList = []
        testSEDList.append(testMatching.loadKuruczSEDs())
        testSEDList.append(testMatching.loadmltSEDs())
        testSEDListH, testSEDListHE = testMatching.loadwdSEDs()
        testSEDList.append(testSEDListH)
        testSEDList.append(testSEDListHE)

        testSEDNames = []
        testMags = []
        testMagNormList = []
        magNormStep = 1

        for typeList in testSEDList:
            if len(typeList) != 0:
                typeSEDNames = []
                typeMags = []
                typeMagNorms = []
                for testSED in typeList:
                    getSEDMags = Sed()
                    typeSEDNames.append(testSED.name)
                    getSEDMags.setSED(wavelen = testSED.wavelen, flambda = testSED.flambda)
                    testMagNorm = np.round(rng.uniform(20.0, 22.0), magNormStep)
                    typeMagNorms.append(testMagNorm)
                    fluxNorm = getSEDMags.calcFluxNorm(testMagNorm, imSimBand)
                    getSEDMags.multiplyFluxNorm(fluxNorm)
                    typeMags.append(starPhot.magListForSed(getSEDMags))
                testSEDNames.append(typeSEDNames)
                testMags.append(typeMags)
                testMagNormList.append(typeMagNorms)

        # Since default bandpassDict should be SDSS ugrizy shouldn't need to specify it
        # Substitute in nan values to simulate incomplete data.
        for typeList, names, mags, magNorms in zip(testSEDList, testSEDNames, testMags, testMagNormList):
            if len(typeList) > 2:
                nanMags = np.array(mags)
                nanMags[0][0] = np.nan
                nanMags[0][2] = np.nan
                nanMags[0][3] = np.nan
                nanMags[1][1] = np.nan
                testMatchingResults = testMatching.findSED(typeList, nanMags, reddening = False)
                self.assertEqual(None, testMatchingResults[0][0])
                self.assertEqual(names[1:], testMatchingResults[0][1:])
                self.assertEqual(None, testMatchingResults[1][0])
                np.testing.assert_almost_equal(magNorms[1:], testMatchingResults[1][1:],
                                               decimal = magNormStep)
            else:
                testMatchingResults = testMatching.findSED(typeList, mags, reddening = False)
                self.assertEqual(names, testMatchingResults[0])
                np.testing.assert_almost_equal(magNorms, testMatchingResults[1], decimal = magNormStep)

        # Test Null Values option
        nullMags = np.array(testMags[0])
        nullMags[0][0] = -99.
        nullMags[0][4] = -99.
        nullMags[1][0] = -99.
        nullMags[1][1] = -99.
        testMatchingResultsNull = testMatching.findSED(testSEDList[0], nullMags,
                                                       nullValues = -99., reddening = False)
        self.assertEqual(testSEDNames[0], testMatchingResultsNull[0])
        np.testing.assert_almost_equal(testMagNormList[0], testMatchingResultsNull[1],
                                       decimal = magNormStep)

        # Test Error Output
        errMags = np.array((testMags[0][0], testMags[0][0], testMags[0][0], testMags[0][0]))
        errMags[1, 1] += 1.  # Total MSE will be 2/(4 colors) = 0.5
        errMags[2, 0:2] = np.nan
        errMags[2, 3] += 1.  # Total MSE will be 2/(2 colors) = 1.0
        errMags[3, :] = None
        errSED = testSEDList[0][0]
        testMatchingResultsErrors = testMatching.findSED([errSED], errMags, reddening = False)
        np.testing.assert_almost_equal(np.array((0.0, 0.5, 1.0)), testMatchingResultsErrors[2][0:3],
                                       decimal = 3)
        self.assertEqual(None, testMatchingResultsErrors[2][3])

        # Now test what happens if we pass in a bandpassDict
        testMatchingResultsNoDefault = testMatching.findSED(testSEDList[0], testMags[0],
                                                            bandpassDict = starPhot,
                                                            reddening = False)
        self.assertEqual(testSEDNames[0], testMatchingResultsNoDefault[0])
        np.testing.assert_almost_equal(testMagNormList[0], testMatchingResultsNoDefault[1],
                                       decimal = magNormStep)

        # Test Reddening
        testRA = rng.uniform(10, 170, len(testSEDList[0]))
        testDec = rng.uniform(10, 80, len(testSEDList[0]))
        extFactor = .5
        raDec = np.array((testRA, testDec))
        ebvVals = ebv().calculateEbv(equatorialCoordinates = raDec)
        extVals = ebvVals*extFactor
        testRedMags = []
        for extVal, testMagSet in zip(extVals, testMags[0]):
            testRedMags.append(testMagSet + extVal)
        testMatchingResultsRed = testMatching.findSED(testSEDList[0], testRedMags, catRA = testRA,
                                                      catDec = testDec, reddening = True,
                                                      extCoeffs = np.ones(5)*extFactor)
        self.assertEqual(testSEDNames[0], testMatchingResultsRed[0])
        np.testing.assert_almost_equal(testMagNormList[0], testMatchingResultsRed[1],
                                       decimal = magNormStep)

        # Finally, test color input
        testColors = []
        for testMagSet in testMags[0]:
            testColorSet = []
            for filtNum in range(0, len(starPhot)-1):
                testColorSet.append(testMagSet[filtNum] - testMagSet[filtNum+1])
            testColors.append(testColorSet)
        testMatchingColorsInput = testMatching.findSED(testSEDList[0], testMags[0],
                                                       reddening = False, colors = testColors)
        self.assertEqual(testSEDNames[0], testMatchingColorsInput[0])
        np.testing.assert_almost_equal(testMagNormList[0], testMatchingColorsInput[1],
                                       decimal = magNormStep)

    @classmethod
    def tearDownClass(cls):
        sims_clean_up()
        del cls.testSpecDir
        del cls.testKDir
        del cls.testMLTDir
        del cls.testWDDir

        del cls.kmTestName
        del cls.mTestName


class MemoryTestClass(lsst.utils.tests.MemoryTestCase):
    pass

if __name__ == "__main__":
    lsst.utils.tests.init()
    unittest.main()
