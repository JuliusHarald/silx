#/*##########################################################################
#
# Copyright (c) 2004-2016 European Synchrotron Radiation Facility
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#
########################################################################### */
"""This modules provides a set of multi-peak fit functions and associated
estimation functions in a format that can be imported into a
:class:`silx.math.fit.specfit.Specfit` instance.

The functions to be imported by :meth:`Specfit.importfun` are defined by
following lists of equal length:

    - :const:`THEORY`: list of function names
    - :const:`FUNCTION`: list of actual functions.
      Each function must conform to the following signature:
      ``f(x, *params) -> y``

         - ``x`` is a sequence of values for the independent variable
           where the function is calculated.
         - ``params`` is a list of parameters needed by the function. There
           is a minimal number ``n`` of required parameters for each function,
           but the length of the list can be longer, as long as it is a multiple
           of ``n``. In that case, the function will calculate and sum the base
           function using the parameters for each series of ``n`` consecutive
           parameters.

           For example, a gaussian function may require 3 parameters (*height,
           center* and *fwhm*). Provided wit a list of 9 parameters, the
           gaussian function  will return the sum of 3 gaussians with various
           heights, center positions and widths.

           This makes it easy to fit data multiple peaks as a sum of individual
           peak functions.
         - ``y`` is the output sequence of the function calculated for
           each ``x`` value

    - :const:`PARAMETERS`: list of lists of parameter names for the base function
      (e.g. ``["height", "center", "fwhm"]`` for a gaussian)
    - :const:`ESTIMATE`: estimation function. Provided with data, this function
      is responsible for determining how many parameters are needed (usually
      by finding the number of peaks), and returning reasonable estimations
      for each parameters, as well as constraints for each parameter. These
      return values can be used to serve as initial parameters for a recursive
      fitting algorithm (such as :func:`silx.math.fit.leastsq`)

      The signature of the estimation function must conform to:
      ``f(x, y, bg, yscaling=None) -> (parameters, constraints)``

          - ``x``: sequence of values for the independent variable
            where the function is calculated.
          - ``y``: data to be fitted
          - ``bg``: background to be subtracted from the data before fitting
          - ``yscaling``: scaling parameter for ``y`` values. If ``None``,
            use ``"Yscaling"`` field in :attr:`config` dictionary.

          - ``parameters``: list of estimated value for each parameter
          - ``constraints``:
            2D sequence of dimension ``(n_parameters, 3)`` where,
            for each parameter denoted by the index i, the meaning is

                     - ``constraints[i][0]`` -- constraint code defining the
                       meaning of ``constraints[i][1]`` and ``constraints[i][2]``

                        - 0 - Free (CFREE)
                        - 1 - Positive (CPOSITIVE)
                        - 2 - Quoted (CQUOTED)
                        - 3 - Fixed (CFIXED)
                        - 4 - Factor (CFACTOR)
                        - 5 - Delta (CDELTA)
                        - 6 - Sum (CSUM)


                     - ``constraints[i][1]``

                        - Ignored if ``constraints[i][0]`` is 0, 1 or 3
                        - Min value of the parameter if ``constraints[i][0]`` is CQUOTED
                        - Index of fitted parameter to which it is related

                     - ``constraints[i][2]``

                        - Ignored if ``constraints[i][0]`` is 0, 1 or 3
                        - Max value of the parameter if constraints[i][0] is CQUOTED
                        - Factor to apply to related parameter with index ``constraints[i][1]``
                        - Difference with parameter with index ``constraints[i][1]``
                        - Sum obtained when adding parameter with index ``constraints[i][1]``


    - :const:`CONFIGURE`: list of configuration functions. A configuration
      function can update configuration variables that influence the behavior
      of fit functions or estimation functions.

By following this structure, you can define your own fit functions to be used
with :class:`silx.math.fit.specfit.Specfit`.

Module members:
---------------
"""
# TODO: replace lists with one big dictionary (Specfit to be modified)
__authors__ = ["V.A. Sole", "P. Knobel"]
__license__ = "MIT"
__date__ = "30/06/2016"
import os
import numpy
arctan = numpy.arctan

from silx.math.fit import functions
from silx.math.fit.peaks import peak_search, guess_fwhm
from silx.math.fit.leastsq import leastsq

try:
    HOME = os.getenv('HOME')
except:
    HOME = None
if HOME is not None:
    os.environ['HOME'] = HOME
else:
    os.environ['HOME'] = "."
SPECFITFUNCTIONS_DEFAULTS = {'NoConstraintsFlag': False,
                             'PositiveFwhmFlag': True,
                             'PositiveHeightAreaFlag': True,
                             'SameFwhmFlag': False,
                             'QuotedPositionFlag': False,   # peak not outside data range
                             'QuotedEtaFlag': False,        # force 0 < eta < 1
                             'Yscaling': 1.0,
                             'Xscaling': 1.0,
                             'FwhmPoints': 8,
                             'AutoFwhm': False,
                             'Sensitivity': 2.5,
                             'ForcePeakPresence': False,
                             # Hypermet
                             'HypermetTails': 15,
                             'QuotedFwhmFlag': 0,
                             'MaxFwhm2InputRatio': 1.5,
                             'MinFwhm2InputRatio': 0.4,
                             # short tail parameters
                             'MinGaussArea4ShortTail': 50000.,
                             'InitialShortTailAreaRatio': 0.050,
                             'MaxShortTailAreaRatio': 0.100,
                             'MinShortTailAreaRatio': 0.0010,
                             'InitialShortTailSlopeRatio': 0.70,
                             'MaxShortTailSlopeRatio': 2.00,
                             'MinShortTailSlopeRatio': 0.50,
                             # long tail parameters
                             'MinGaussArea4LongTail': 1000.0,
                             'InitialLongTailAreaRatio': 0.050,
                             'MaxLongTailAreaRatio': 0.300,
                             'MinLongTailAreaRatio': 0.010,
                             'InitialLongTailSlopeRatio': 20.0,
                             'MaxLongTailSlopeRatio': 50.0,
                             'MinLongTailSlopeRatio': 5.0,
                             # step tail
                             'MinGaussHeight4StepTail': 5000.,
                             'InitialStepTailHeightRatio': 0.002,
                             'MaxStepTailHeightRatio': 0.0100,
                             'MinStepTailHeightRatio': 0.0001,
                             # Hypermet constraints
                             #   position in range [estimated position +- estimated fwhm/2]
                             'HypermetQuotedPositionFlag': True,
                             'DeltaPositionFwhmUnits': 0.5,
                             'SameSlopeRatioFlag': 1,
                             'SameAreaRatioFlag': 1}
"""This dictionary defines default configuration parameters that have effects
on fit functions and estimation functions.
This dictionary  is replicated as attribute :attr:`SpecfitFunctions.config`,
which can be modified by configuration functions defined in
:const:`CONFIGURE`.
"""

CFREE = 0
CPOSITIVE = 1
CQUOTED = 2
CFIXED = 3
CFACTOR = 4
CDELTA = 5
CSUM = 6
CIGNORED = 7


class SpecfitFunctions(object):
    """Class wrapping functions from :class:`silx.math.fit.functions`
    and providing estimate functions for all of these fit functions."""
    def __init__(self, config=None):
        if config is None:
            self.config = SPECFITFUNCTIONS_DEFAULTS
        else:
            self.config = config

    def ahypermet(self, x, *pars):
        """
        Wrapping of :func:`silx.math.fit.functions.sum_ahypermet`.

        Depending on the value of `self.config['HypermetTails']`, one can
        activate or deactivate the various terms of the hypermet function.

        `self.config['HypermetTails']` must be an integer between 0 and 15.
        It is a set of 4 binary flags, one for activating each one of the
        hypermet terms: *gaussian function, short tail, long tail, step*.

        For example, 15 can be expressed as ``1111`` in base 2, so a flag of
        15 means all terms are active.

        """
        g_term = self.config['HypermetTails'] & 1
        st_term = (self.config['HypermetTails'] >> 1) & 1
        lt_term = (self.config['HypermetTails'] >> 2) & 1
        step_term = (self.config['HypermetTails'] >> 3) & 1
        return functions.sum_ahypermet(x, *pars,
                                       gaussian_term=g_term, st_term=st_term,
                                       lt_term=lt_term, step_term=step_term)

    def atan(self, x, *pars):
        return pars[0] * (0.5 + (arctan((1.0 * x - pars[1]) / pars[2]) / numpy.pi))

    def periodic_gauss(self, x, *pars):
        """
        Return a sum of gaussian functions defined by
        *(npeaks, delta, height, centroid, fwhm)*,
        where:

        - *npeaks* is the number of gaussians peaks
        - *delta* is the distance between 2 peaks
        - *height* is the peak amplitude of all the gaussians
        - *centroid* is the peak x-coordinate of the first gaussian
        - *fwhm* is the full-width at half maximum for all the gaussians

        :param x: Independant variable where the function is calculated
        :param pars: *(npeaks, delta, height, centroid, fwhm)*
        :return: Sum of ``npeaks`` gaussians
        """
        newpars = numpy.zeros((pars[0], 3), numpy.float)
        for i in range(int(pars[0])):
            newpars[i, 0] = pars[2]
            newpars[i, 1] = pars[3] + i * pars[1]
            newpars[:, 2] = pars[4]
        return functions.sum_gauss(x, newpars)

    def user_estimate(self, x, y, z, yscaling=1.0):
        """Interactive estimation function for gaussian parameters.
        The user is prompted for the number of peaks and for his estimation
        of *Height, Position, FWHM* for each gaussian peak in the data.

        To conform to the estimation function signature expected by
        :mod:`Specfit`, this function must be called with at least 3
        and at most 5 arguments. All arguments are ignored.

        :return: Tuple of estimated parameters and constraints. Parameters are
            provided by the user. Fit constraints are set to 0 / FREE for all
            parameters.
        """
        ngauss = input(' Number of Gaussians : ')
        ngauss = int(ngauss)
        if ngauss < 1:
            ngauss = 1
        newpar = []
        for i in range(ngauss):
            print("Defining Gaussian number %d " % (i + 1))
            newpar.append(input('Height   = '))
            newpar.append(input('Position = '))
            newpar.append(input('FWHM     = '))
            # newpar.append(in)
        return newpar, numpy.zeros((len(newpar), 3), numpy.float)

    def estimate_height_position_fwhm(self, x, y, bg=None,
                                      yscaling=None):
        """Estimation of *Height, Position, FWHM* of peaks, for gaussian-like
        curves.

        This functions finds how many parameters are needed, based on the
        number of peaks detected. Then it estimates the fit parameters
        with a few iterations of fitting gaussian functions.

        :param x: Array of abscissa values
        :param y: Array of ordinate values (``y = f(x)``)
        :param bg: If not ``None``, background signal to be subtracted from
            ``y`` before fitting gaussian functions to peaks.
        :param yscaling: Scaling factor applied to ``y`` data when searching
            for peaks
        :return: Tuple of estimated fit parameters and fit constraints.
            Parameters to be estimated for each peak are:
            *Height, Position, FWHM*.
            Fit constraints depend on :attr:`config`.
        """
        if yscaling is None:
            try:
                yscaling = self.config['Yscaling']
            except:
                yscaling = 1.0
        if yscaling == 0:
            yscaling = 1.0

        fittedpar = []

        if bg is None:
            bg = numpy.zeros_like(y)

        if self.config['AutoFwhm']:
            search_fwhm = guess_fwhm(y)
        else:
            search_fwhm = int(float(self.config['FwhmPoints']))
        search_sens = float(self.config['Sensitivity'])

        if search_fwhm < 3:
            search_fwhm = 3
            self.config['FwhmPoints'] = 3

        if search_sens < 1:
            search_sens = 1
            self.config['Sensitivity'] = 1

        npoints = len(y)

        # Find indices of peaks in data array
        if npoints > 1.5 * search_fwhm:
            peaks = peak_search(yscaling * numpy.fabs(y),
                                fwhm=search_fwhm,
                                sensitivity=search_sens)
        else:
            peaks = []

        if not len(peaks):
            #mca = int(float(self.config.get('McaMode', 0)))
            forcePeak = int(float(self.config.get('ForcePeakPresence', 0)))
            #if not mca and forcePeak:
            if forcePeak:
                delta = y - bg
                peaks = [int(numpy.nonzero(delta == delta.max())[0])]

        # Find index of largest peak in peaks array
        index_largest_peak = 0
        if len(peaks) > 0:
            # estimate fwhm as 5 * sampling interval
            sig = 5 * abs(x[npoints - 1] - x[0]) / npoints
            peakpos = x[int(peaks[0])]
            if abs(peakpos) < 1.0e-16:
                peakpos = 0.0
            param = numpy.array(
                [y[int(peaks[0])] - bg[int(peaks[0])], peakpos, sig])
            height_largest_peak = param[0]
            peak_index = 1
            for i in peaks[1:]:
                param2 = numpy.array(
                    [y[int(i)] - bg[int(i)], x[int(i)], sig])
                param = numpy.concatenate((param, param2))
                if param2[0] > height_largest_peak:
                    height_largest_peak = param2[0]
                    index_largest_peak = peak_index
                peak_index += 1

            # Make arrays 2D and substract background
            xw = numpy.resize(x, (npoints, 1))
            yw = numpy.resize(y - bg, (npoints, 1))

            cons = numpy.zeros((len(param), 3), numpy.float)

            # peak height must be positive
            cons[0:len(param):3, 0] = CPOSITIVE
            # force peaks to stay around their position
            cons[1:len(param):3, 0] = CQUOTED

            # set possible peak range to estimated peak +- guessed fwhm
            if len(xw) > search_fwhm:
                fwhmx = numpy.fabs(xw[int(search_fwhm)] - xw[0])
                cons[1:len(param):3, 1] = param[1:len(param):3] - 0.5 * fwhmx
                cons[1:len(param):3, 2] = param[1:len(param):3] + 0.5 * fwhmx
            else:
                cons[1:len(param):3, 1] = min(xw) * numpy.ones(
                                                        (param[1:len(param):3]),
                                                        numpy.float)
                cons[1:len(param):3, 2] = max(xw) * numpy.ones(
                                                        (param[1:len(param):3]),
                                                        numpy.float)

            # ensure fwhm is positive
            cons[2:len(param):3, 0] = CPOSITIVE

            # run a quick iterative fit (4 iterations) to improve
            # estimations
            fittedpar, _ = leastsq(functions.sum_gauss, xw, yw, param,
                                   max_iter=4, constraints=cons.tolist())

        # set final constraints based on config parameters
        cons = numpy.zeros((len(fittedpar), 3), numpy.float)
        peak_index = 0
        for i in range(len(peaks)):
            # Setup height area constrains
            if not self.config['NoConstraintsFlag']:
                if self.config['PositiveHeightAreaFlag']:
                    cons[peak_index, 0] = CPOSITIVE
                    cons[peak_index, 1] = 0
                    cons[peak_index, 2] = 0
            peak_index += 1

            # Setup position constrains
            if not self.config['NoConstraintsFlag']:
                if self.config['QuotedPositionFlag']:
                    cons[peak_index, 0] = CQUOTED
                    cons[peak_index, 1] = min(x)
                    cons[peak_index, 2] = max(x)
            peak_index += 1

            # Setup positive FWHM constrains
            if not self.config['NoConstraintsFlag']:
                if self.config['PositiveFwhmFlag']:
                    cons[peak_index, 0] = CPOSITIVE
                    cons[peak_index, 1] = 0
                    cons[peak_index, 2] = 0
                if self.config['SameFwhmFlag']:
                    if (i != index_largest_peak):
                        cons[peak_index, 0] = CFACTOR
                        cons[peak_index, 1] = 3 * index_largest_peak + 2
                        cons[peak_index, 2] = 1.0
            peak_index += 1

        return fittedpar, cons

    def estimate_agauss(self, x, y, bg, yscaling=None):
        """Estimation of *Area, Position, FWHM* of peaks, for gaussian-like
        curves.

        This functions uses :meth:`estimate_height_position_fwhm`, then
        converts the height parameters to area under the curve with the
        formula ``area = sqrt(2*pi) * height * fwhm / (2 * sqrt(2 * log(2))``

        :param x: Array of abscissa values
        :param y: Array of ordinate values (``y = f(x)``)
        :param bg: If not ``None``, background signal to be subtracted from
            ``y`` before fitting gaussian functions to peaks.
        :param yscaling: Scaling factor applied to ``y`` data when searching
            for peaks
        :return: Tuple of estimated fit parameters and fit constraints.
            Parameters to be estimated for each peak are:
            *Area, Position, FWHM*.
            Fit constraints depend on :attr:`config`.
        """
        fittedpar, cons = self.estimate_height_position_fwhm(x, y, bg,
                                                             yscaling)
        # get the number of found peaks
        npeaks = len(fittedpar) // 3
        # Replace height with area in fittedpar
        for i in range(npeaks):
            height = fittedpar[3 * i]
            fwhm = fittedpar[3 * i + 2]
            fittedpar[3 * i] = numpy.sqrt(2 * numpy.pi) * height * fwhm / (
                               2.0 * numpy.sqrt(2 * numpy.log(2)))
        return fittedpar, cons

    def estimate_alorentz(self, x, y, bg, yscaling=None):
        """Estimation of *Area, Position, FWHM* of peaks, for Lorentzian
        curves.

        This functions uses :meth:`estimate_height_position_fwhm`, then
        converts the height parameters to area under the curve with the
        formula ``area = height * fwhm * 0.5 * pi``

        :param x: Array of abscissa values
        :param y: Array of ordinate values (``y = f(x)``)
        :param bg: If not ``None``, background signal to be subtracted from
            ``y`` before fitting gaussian functions to peaks.
        :param yscaling: Scaling factor applied to ``y`` data when searching
            for peaks
        :return: Tuple of estimated fit parameters and fit constraints.
            Parameters to be estimated for each peak are:
            *Area, Position, FWHM*.
            Fit constraints depend on :attr:`config`.
        """
        fittedpar, cons = self.estimate_height_position_fwhm(x, y, bg,
                                                             yscaling)
        # get the number of found peaks
        npeaks = len(fittedpar) // 3
        # Replace height with area in fittedpar
        for i in range(npeaks):
            height = fittedpar[3 * i]
            fwhm = fittedpar[3 * i + 2]
            fittedpar[3 * i] = (height * fwhm * 0.5 * numpy.pi)
        return fittedpar, cons

    def estimate_splitgauss(self, x, y, bg, yscaling=None):
        """Estimation of *Height, Position, FWHM1, FWHM2* of peaks, for
        asymmetric gaussian-like curves.

        This functions uses :meth:`estimate_height_position_fwhm`, then
        adds a second (identical) estimation of FWHM to the fit parameters
        for each peak, and the corresponding constraint.

        :param x: Array of abscissa values
        :param y: Array of ordinate values (``y = f(x)``)
        :param bg: If not ``None``, background signal to be subtracted from
            ``y`` before fitting gaussian functions to peaks.
        :param yscaling: Scaling factor applied to ``y`` data when searching
            for peaks
        :return: Tuple of estimated fit parameters and fit constraints.
            Parameters to be estimated for each peak are:
            *Area, Position, FWHM1, FWHM2*.
            Fit constraints depend on :attr:`config`.
        """
        fittedpar, cons = self.estimate_height_position_fwhm(x, y, bg,
                                                             yscaling)
        # get the number of found peaks
        npeaks = len(fittedpar) // 3
        estimated_parameters = []
        estimated_constraints = numpy.zeros((4 * npeaks, 3), numpy.float)
        for i in range(npeaks):
            for j in range(3):
                estimated_parameters.append(fittedpar[3 * i + j])
            estimated_parameters.append(fittedpar[3 * i + 2])
            estimated_constraints[4 * i, 0] = cons[3 * i, 0]
            estimated_constraints[4 * i + 1, 0] = cons[3 * i + 1, 0]
            estimated_constraints[4 * i + 2, 0] = cons[3 * i + 2, 0]
            estimated_constraints[4 * i + 3, 0] = cons[3 * i + 2, 0]
            estimated_constraints[4 * i, 1] = cons[3 * i, 1]
            estimated_constraints[4 * i + 1, 1] = cons[3 * i + 1, 1]
            estimated_constraints[4 * i + 2, 1] = cons[3 * i + 2, 1]
            estimated_constraints[4 * i + 3, 1] = cons[3 * i + 2, 1]
            estimated_constraints[4 * i, 2] = cons[3 * i, 2]
            estimated_constraints[4 * i + 1, 2] = cons[3 * i + 1, 2]
            estimated_constraints[4 * i + 2, 2] = cons[3 * i + 2, 2]
            estimated_constraints[4 * i + 3, 2] = cons[3 * i + 2, 2]
            if cons[3 * i + 2, 0] == 4:
                # same FWHM case
                estimated_constraints[4 * i + 2, 1] = \
                    int(cons[3 * i + 2, 1] / 3) * 4 + 2
                estimated_constraints[4 * i + 3, 1] = \
                    int(cons[3 * i + 2, 1] / 3) * 4 + 3
        return estimated_parameters, estimated_constraints

    def estimate_pvoigt(self, x, y, bg, yscaling=None):
        """Estimation of *Height, Position, FWHM, eta* of peaks, for
        pseudo-Voigt curves.

        Pseudo-Voigt are a sum of a gaussian curve *G(x)* and a lorentzian
        curve *L(x)* with the same height, center, fwhm parameters:
        ``y(x) = eta * G(x) + (1-eta) * L(x)``

        This functions uses :meth:`estimate_height_position_fwhm`, then
        adds a constant estimation of *eta* (0.5) to the fit parameters
        for each peak, and the corresponding constraint.

        :param x: Array of abscissa values
        :param y: Array of ordinate values (``y = f(x)``)
        :param bg: If not ``None``, background signal to be subtracted from
            ``y`` before fitting gaussian functions to peaks.
        :param yscaling: Scaling factor applied to ``y`` data when searching
            for peaks
        :return: Tuple of estimated fit parameters and fit constraints.
            Parameters to be estimated for each peak are:
            *Height, Position, FWHM, eta*.
            Constraint for the eta parameter can be set to QUOTED (0.--1.)
            by setting :attr:`config`['QuotedEtaFlag'] to ``True``.
            If this is not the case, the constraint code is set to FREE.
        """
        fittedpar, cons = self.estimate_height_position_fwhm(x, y, bg,
                                                             yscaling)
        npeaks = len(fittedpar) // 3
        newpar = []
        newcons = numpy.zeros((4 * npeaks, 3), numpy.float)
        # find out related parameters proper index
        if not self.config['NoConstraintsFlag']:
            if self.config['SameFwhmFlag']:
                j = 0
                # get the index of the free FWHM
                for i in range(npeaks):
                    if cons[3 * i + 2, 0] != 4:
                        j = i
                for i in range(npeaks):
                    if i != j:
                        cons[3 * i + 2, 1] = 4 * j + 2
        for i in range(npeaks):
            newpar.append(fittedpar[3 * i])
            newpar.append(fittedpar[3 * i + 1])
            newpar.append(fittedpar[3 * i + 2])
            newpar.append(0.5)
            newcons[4 * i, 0] = cons[3 * i, 0]
            newcons[4 * i + 1, 0] = cons[3 * i + 1, 0]
            newcons[4 * i + 2, 0] = cons[3 * i + 2, 0]
            newcons[4 * i, 1] = cons[3 * i, 1]
            newcons[4 * i + 1, 1] = cons[3 * i + 1, 1]
            newcons[4 * i + 2, 1] = cons[3 * i + 2, 1]
            newcons[4 * i, 2] = cons[3 * i, 2]
            newcons[4 * i + 1, 2] = cons[3 * i + 1, 2]
            newcons[4 * i + 2, 2] = cons[3 * i + 2, 2]
            # Eta constrains
            newcons[4 * i + 3, 0] = 0
            newcons[4 * i + 3, 1] = 0
            newcons[4 * i + 3, 2] = 0
            if self.config['QuotedEtaFlag']:
                # QUOTED=2
                newcons[4 * i + 3, 0] = CQUOTED
                newcons[4 * i + 3, 1] = 0.0
                newcons[4 * i + 3, 2] = 1.0
        return newpar, newcons

    def estimate_splitpvoigt(self, x, y, bg, yscaling=None):
        """Estimation of *Height, Position, FWHM1, FWHM2, eta* of peaks, for
        asymmetric pseudo-Voigt curves.

        This functions uses :meth:`estimate_height_position_fwhm`, then
        adds an identical FWHM2 parameter and a constant estimation of
        *eta* (0.5) to the fit parameters for each peak, and the corresponding
        constraints.

        Constraint for the eta parameter can be set to QUOTED (0.--1.)
        by setting :attr:`config`['QuotedEtaFlag'] to ``True``.
        If this is not the case, the constraint code is set to FREE.

        :param x: Array of abscissa values
        :param y: Array of ordinate values (``y = f(x)``)
        :param bg: If not ``None``, background signal to be subtracted from
            ``y`` before fitting gaussian functions to peaks.
        :param yscaling: Scaling factor applied to ``y`` data when searching
            for peaks
        :return: Tuple of estimated fit parameters and fit constraints.
            Parameters to be estimated for each peak are:
            *Height, Position, FWHM1, FWHM2, eta*.
        """
        fittedpar, cons = self.estimate_height_position_fwhm(x, y, bg,
                                                             yscaling)
        npeaks = len(fittedpar) // 3
        newpar = []
        newcons = numpy.zeros((5 * npeaks, 3), numpy.float)
        # find out related parameters proper index
        if not self.config['NoConstraintsFlag']:
            if self.config['SameFwhmFlag']:
                j = 0
                # get the index of the free FWHM
                for i in range(npeaks):
                    if cons[3 * i + 2, 0] != 4:
                        j = i
                for i in range(npeaks):
                    if i != j:
                        cons[3 * i + 2, 1] = 4 * j + 2
        for i in range(npeaks):
            # height
            newpar.append(fittedpar[3 * i])
            # position
            newpar.append(fittedpar[3 * i + 1])
            # fwhm1
            newpar.append(fittedpar[3 * i + 2])
            # fwhm2 equal to the first
            newpar.append(fittedpar[3 * i + 2])
            # eta
            newpar.append(0.5)
            newcons[5 * i, 0] = cons[3 * i, 0]
            newcons[5 * i + 1, 0] = cons[3 * i + 1, 0]
            newcons[5 * i + 2, 0] = cons[3 * i + 2, 0]
            newcons[5 * i + 3, 0] = cons[3 * i + 2, 0]
            newcons[5 * i, 1] = cons[3 * i, 1]
            newcons[5 * i + 1, 1] = cons[3 * i + 1, 1]
            newcons[5 * i + 2, 1] = cons[3 * i + 2, 1]
            newcons[5 * i + 3, 1] = cons[3 * i + 2, 1]
            newcons[5 * i, 2] = cons[3 * i, 2]
            newcons[5 * i + 1, 2] = cons[3 * i + 1, 2]
            newcons[5 * i + 2, 2] = cons[3 * i + 2, 2]
            newcons[5 * i + 3, 2] = cons[3 * i + 2, 2]
            if cons[3 * i + 2, 0] == 4:
                newcons[5 * i + 3, 1] = newcons[5 * i + 2, 1] + 1
            # Eta constrains
            newcons[5 * i + 4, 0] = 0
            newcons[5 * i + 4, 1] = 0
            newcons[5 * i + 4, 2] = 0
            if self.config['QuotedEtaFlag']:
                # QUOTED=2
                newcons[5 * i + 4, 0] = CQUOTED
                newcons[5 * i + 4, 1] = 0.0
                newcons[5 * i + 4, 2] = 1.0
        return newpar, newcons

    def estimate_apvoigt(self, x, y, bg, yscaling=None):
        """Estimation of *Area, Position, FWHM1, eta* of peaks, for
        pseudo-Voigt curves.

        This functions uses :meth:`estimate_pvoigt`, then converts the height
        parameter to area.

        :param x: Array of abscissa values
        :param y: Array of ordinate values (``y = f(x)``)
        :param bg: If not ``None``, background signal to be subtracted from
            ``y`` before fitting gaussian functions to peaks.
        :param yscaling: Scaling factor applied to ``y`` data when searching
            for peaks
        :return: Tuple of estimated fit parameters and fit constraints.
            Parameters to be estimated for each peak are:
            *Area, Position, FWHM, eta*.
        """
        fittedpar, cons = self.estimate_pvoigt(x, y, bg, yscaling)
        npeaks = len(fittedpar) // 4
        # Assume 50% of the area is determined by the gaussian and 50% by
        # the Lorentzian.
        for i in range(npeaks):
            height = fittedpar[4 * i]
            fwhm = fittedpar[4 * i + 2]
            fittedpar[4 * i] = 0.5 * (height * fwhm * 0.5 * numpy.pi) +\
                0.5 * (height * fwhm / (2.0 * numpy.sqrt(2 * numpy.log(2)))
                       ) * numpy.sqrt(2 * numpy.pi)
        return fittedpar, cons

    def estimate_ahypermet(self, x, y, bg, yscaling=None):
        """Estimation of *area, position, fwhm, st_area_r, st_slope_r,
        lt_area_r, lt_slope_r, step_height_r* of peaks, for hypermet curves.

        :param x: Array of abscissa values
        :param y: Array of ordinate values (``y = f(x)``)
        :param bg: If not ``None``, background signal to be subtracted from
            ``y`` before fitting gaussian functions to peaks.
        :param yscaling: Scaling factor applied to ``y`` data when searching
            for peaks
        :return: Tuple of estimated fit parameters and fit constraints.
            Parameters to be estimated for each peak are:
            *area, position, fwhm, st_area_r, st_slope_r,
            lt_area_r, lt_slope_r, step_height_r* .
        """
        fittedpar, cons = self.estimate_height_position_fwhm(x, y, bg, yscaling)
        npeaks = len(fittedpar) // 3
        newpar = []
        newcons = numpy.zeros((8 * npeaks, 3), numpy.float)
        main_peak = 0
        # find out related parameters proper index
        if not self.config['NoConstraintsFlag']:
            if self.config['SameFwhmFlag']:
                j = 0
                # get the index of the free FWHM
                for i in range(npeaks):
                    if cons[3 * i + 2, 0] != 4:
                        j = i
                for i in range(npeaks):
                    if i != j:
                        cons[3 * i + 2, 1] = 8 * j + 2
                main_peak = j
        for i in range(npeaks):
            if fittedpar[3 * i] > fittedpar[3 * main_peak]:
                main_peak = i

        for i in range(npeaks):
            height = fittedpar[3 * i]
            position = fittedpar[3 * i + 1]
            fwhm = fittedpar[3 * i + 2]
            area = (height * fwhm / (2.0 * numpy.sqrt(2 * numpy.log(2)))
                    ) * numpy.sqrt(2 * numpy.pi)
            # the gaussian parameters
            newpar.append(area)
            newpar.append(position)
            newpar.append(fwhm)
            # print "area, pos , fwhm = ",area,position,fwhm
            # Avoid zero derivatives because of not calculating contribution
            g_term = 1
            st_term = 1
            lt_term = 1
            step_term = 1
            if self.config['HypermetTails'] != 0:
                g_term = self.config['HypermetTails'] & 1
                st_term = (self.config['HypermetTails'] >> 1) & 1
                lt_term = (self.config['HypermetTails'] >> 2) & 1
                step_term = (self.config['HypermetTails'] >> 3) & 1
            if g_term == 0:
                # fix the gaussian parameters
                newcons[8 * i, 0] = CFIXED
                newcons[8 * i + 1, 0] = CFIXED
                newcons[8 * i + 2, 0] = CFIXED
            # the short tail parameters
            if ((area * yscaling) <
                self.config['MinGaussArea4ShortTail']) | \
               (st_term == 0):
                newpar.append(0.0)
                newpar.append(0.0)
                newcons[8 * i + 3, 0] = CFIXED
                newcons[8 * i + 3, 1] = 0.0
                newcons[8 * i + 3, 2] = 0.0
                newcons[8 * i + 4, 0] = CFIXED
                newcons[8 * i + 4, 1] = 0.0
                newcons[8 * i + 4, 2] = 0.0
            else:
                newpar.append(self.config['InitialShortTailAreaRatio'])
                newpar.append(self.config['InitialShortTailSlopeRatio'])
                newcons[8 * i + 3, 0] = CQUOTED
                newcons[8 * i + 3, 1] = self.config['MinShortTailAreaRatio']
                newcons[8 * i + 3, 2] = self.config['MaxShortTailAreaRatio']
                newcons[8 * i + 4, 0] = CQUOTED
                newcons[8 * i + 4, 1] = self.config['MinShortTailSlopeRatio']
                newcons[8 * i + 4, 2] = self.config['MaxShortTailSlopeRatio']
            # the long tail parameters
            if ((area * yscaling) <
                self.config['MinGaussArea4LongTail']) | \
               (lt_term == 0):
                newpar.append(0.0)
                newpar.append(0.0)
                newcons[8 * i + 5, 0] = CFIXED
                newcons[8 * i + 5, 1] = 0.0
                newcons[8 * i + 5, 2] = 0.0
                newcons[8 * i + 6, 0] = CFIXED
                newcons[8 * i + 6, 1] = 0.0
                newcons[8 * i + 6, 2] = 0.0
            else:
                newpar.append(self.config['InitialLongTailAreaRatio'])
                newpar.append(self.config['InitialLongTailSlopeRatio'])
                newcons[8 * i + 5, 0] = CQUOTED
                newcons[8 * i + 5, 1] = self.config['MinLongTailAreaRatio']
                newcons[8 * i + 5, 2] = self.config['MaxLongTailAreaRatio']
                newcons[8 * i + 6, 0] = CQUOTED
                newcons[8 * i + 6, 1] = self.config['MinLongTailSlopeRatio']
                newcons[8 * i + 6, 2] = self.config['MaxLongTailSlopeRatio']
            # the step parameters
            if ((height * yscaling) <
                self.config['MinGaussHeight4StepTail']) | \
               (step_term == 0):
                newpar.append(0.0)
                newcons[8 * i + 7, 0] = CFIXED
                newcons[8 * i + 7, 1] = 0.0
                newcons[8 * i + 7, 2] = 0.0
            else:
                newpar.append(self.config['InitialStepTailHeightRatio'])
                newcons[8 * i + 7, 0] = CQUOTED
                newcons[8 * i + 7, 1] = self.config['MinStepTailHeightRatio']
                newcons[8 * i + 7, 2] = self.config['MaxStepTailHeightRatio']
            # if self.config['NoConstraintsFlag'] == 1:
            #   newcons=numpy.zeros((8*npeaks, 3),numpy.float)
        if npeaks > 0:
            if g_term:
                if self.config['PositiveHeightAreaFlag']:
                    for i in range(npeaks):
                        newcons[8 * i, 0] = CPOSITIVE
                if self.config['PositiveFwhmFlag']:
                    for i in range(npeaks):
                        newcons[8 * i + 2, 0] = CPOSITIVE
                if self.config['SameFwhmFlag']:
                    for i in range(npeaks):
                        if i != main_peak:
                            newcons[8 * i + 2, 0] = CFACTOR
                            newcons[8 * i + 2, 1] = 8 * main_peak + 2
                            newcons[8 * i + 2, 2] = 1.0
                if self.config['HypermetQuotedPositionFlag']:
                    for i in range(npeaks):
                        delta = self.config['DeltaPositionFwhmUnits'] * fwhm
                        newcons[8 * i + 1, 0] = CQUOTED
                        newcons[8 * i + 1, 1] = newpar[8 * i + 1] - delta
                        newcons[8 * i + 1, 2] = newpar[8 * i + 1] + delta
            if self.config['SameSlopeRatioFlag']:
                for i in range(npeaks):
                    if i != main_peak:
                        newcons[8 * i + 4, 0] = CFACTOR
                        newcons[8 * i + 4, 1] = 8 * main_peak + 4
                        newcons[8 * i + 4, 2] = 1.0
                        newcons[8 * i + 6, 0] = CFACTOR
                        newcons[8 * i + 6, 1] = 8 * main_peak + 6
                        newcons[8 * i + 6, 2] = 1.0
            if self.config['SameAreaRatioFlag']:
                for i in range(npeaks):
                    if i != main_peak:
                        newcons[8 * i + 3, 0] = CFACTOR
                        newcons[8 * i + 3, 1] = 8 * main_peak + 3
                        newcons[8 * i + 3, 2] = 1.0
                        newcons[8 * i + 5, 0] = CFACTOR
                        newcons[8 * i + 5, 1] = 8 * main_peak + 5
                        newcons[8 * i + 5, 2] = 1.0
        return newpar, newcons

    def estimate_downstep(self, x, y, bg, yscaling=1.0):
        """Estimation of parameters for downstep curves.

        The functions estimates gaussian parameters for the derivative of
        the data, and returns estimated parameters for the largest gaussian
        peak.

        :param x: Array of abscissa values
        :param y: Array of ordinate values (``y = f(x)``)
        :param bg: If not ``None``, background signal to be subtracted from
            ``y`` before fitting gaussian functions to peaks.
        :param yscaling: Scaling factor applied to ``y`` data when searching
            for peaks
        :return: Tuple of estimated fit parameters and fit constraints.
            Parameters to be estimated for each downstep are:
            *height, centroid, fwhm* .
        """
        crappyfilter = [-0.25, -0.75, 0.0, 0.75, 0.25]
        cutoff = 2
        yy = numpy.convolve(y, crappyfilter, mode=1)[cutoff:-cutoff]
        if max(yy) > 0:
            yy = yy * max(y) / max(yy)
        xx = x[cutoff:-cutoff]
        fittedpar, cons = self.estimate_agauss(xx, yy, bg, yscaling)
        npeaks = len(fittedpar) // 3
        largest_index = 0
        largest = [fittedpar[3 * largest_index],
                   fittedpar[3 * largest_index + 1],
                   fittedpar[3 * largest_index + 2]]
        for i in range(npeaks):
            if fittedpar[3 * i] > largest[0]:
                largest_index = i
                largest = [fittedpar[3 * largest_index],
                           fittedpar[3 * largest_index + 1],
                           fittedpar[3 * largest_index + 2]]
        largest[0] = max(y) - min(y)
        # Setup constrains
        if not self.config['NoConstraintsFlag']:
                # Setup height constrains
            if self.config['PositiveHeightAreaFlag']:
                            #POSITIVE = 1
                cons[0, 0] = CPOSITIVE
                cons[0, 1] = 0
                cons[0, 2] = 0

            # Setup position constrains
            if self.config['QuotedPositionFlag']:
                #QUOTED = 2
                cons[1, 0] = CQUOTED
                cons[1, 1] = min(x)
                cons[1, 2] = max(x)

            # Setup positive FWHM constrains
            if self.config['PositiveFwhmFlag']:
                # POSITIVE=1
                cons[2, 0] = CPOSITIVE
                cons[2, 1] = 0
                cons[2, 2] = 0

        return largest, cons

    def estimate_slit(self, x, y, bg, yscaling=1.0):
        """Estimation of parameters for slit curves.

        The functions estimates upstep and downstep parameters for the largest
        steps, and uses them for calculating the center (middle between upstep
        and downstep), the height (maximum amplitude in data), the fwhm
        (distance between the up- and down-step centers) and the beamfwhm
        (average of FWHM for up- and down-step).

        :param x: Array of abscissa values
        :param y: Array of ordinate values (``y = f(x)``)
        :param bg: If not ``None``, background signal to be subtracted from
            ``y`` before fitting gaussian functions to peaks.
        :param yscaling: Scaling factor applied to ``y`` data when searching
            for peaks
        :return: Tuple of estimated fit parameters and fit constraints.
            Parameters to be estimated for each slit are:
            *height, position, fwhm, beamfwhm* .
        """
        largestup, cons = self.estimate_upstep(
            x, y, bg, yscaling)
        largestdown, cons = self.estimate_downstep(
            x, y, bg, yscaling)
        fwhm = numpy.fabs(largestdown[1] - largestup[1])
        beamfwhm = 0.5 * (largestup[2] + largestdown[1])
        beamfwhm = min(beamfwhm, fwhm / 10.0)
        beamfwhm = max(beamfwhm, (max(x) - min(x)) * 3.0 / len(x))
        # own estimation
        yy = y - bg
        height = max(y - bg)
        i1 = numpy.nonzero(yy >= 0.5 * height)[0]
        xx = numpy.take(x, i1)
        position = (xx[0] + xx[-1]) / 2.0
        fwhm = xx[-1] - xx[0]
        largest = [height, position, fwhm, beamfwhm]
        cons = numpy.zeros((4, 3), numpy.float)
        # Setup constrains
        if not self.config['NoConstraintsFlag']:
            # Setup height constrains
            if self.config['PositiveHeightAreaFlag']:
                #POSITIVE = 1
                cons[0, 0] = CPOSITIVE
                cons[0, 1] = 0
                cons[0, 2] = 0

            # Setup position constrains
            if self.config['QuotedPositionFlag']:
                #QUOTED = 2
                cons[1, 0] = CQUOTED
                cons[1, 1] = min(x)
                cons[1, 2] = max(x)

            # Setup positive FWHM constrains
            if self.config['PositiveFwhmFlag']:
                # POSITIVE=1
                cons[2, 0] = CPOSITIVE
                cons[2, 1] = 0
                cons[2, 2] = 0

            # Setup positive FWHM constrains
            if self.config['PositiveFwhmFlag']:
                # POSITIVE=1
                cons[3, 0] = CPOSITIVE
                cons[3, 1] = 0
                cons[3, 2] = 0
        return largest, cons

    def estimate_upstep(self, x, y, bg, yscaling=1.0):
        """Estimation of parameters for upstep curves.

        The functions estimates gaussian parameters for the derivative of
        the data, and returns estimated parameters for the largest gaussian
        peak.

        :param x: Array of abscissa values
        :param y: Array of ordinate values (``y = f(x)``)
        :param bg: If not ``None``, background signal to be subtracted from
            ``y`` before fitting gaussian functions to peaks.
        :param yscaling: Scaling factor applied to ``y`` data when searching
            for peaks
        :return: Tuple of estimated fit parameters and fit constraints.
            Parameters to be estimated for each upstep are:
            *height, centroid, fwhm* .
        """
        crappyfilter = [0.25, 0.75, 0.0, -0.75, -0.25]
        cutoff = 2
        yy = numpy.convolve(y, crappyfilter, mode=1)[cutoff:-cutoff]
        if max(yy) > 0:
            yy = yy * max(y) / max(yy)
        xx = x[cutoff:-cutoff]
        fittedpar, cons = self.estimate_agauss(xx, yy, bg, yscaling)
        npeaks = len(fittedpar) // 3
        largest_index = 0
        largest = [fittedpar[3 * largest_index],
                   fittedpar[3 * largest_index + 1],
                   fittedpar[3 * largest_index + 2]]
        newcons = numpy.zeros((3, 3), numpy.float)
        for i in range(npeaks):
            if fittedpar[3 * i] > largest[0]:
                largest_index = i
                largest = [fittedpar[3 * largest_index],
                           fittedpar[3 * largest_index + 1],
                           fittedpar[3 * largest_index + 2]]
        largest[0] = max(y) - min(y)
        # Setup constrains
        if not self.config['NoConstraintsFlag']:
                # Setup height constrains
            if self.config['PositiveHeightAreaFlag']:
                #POSITIVE = 1
                cons[0, 0] = CPOSITIVE
                cons[0, 1] = 0
                cons[0, 2] = 0

            # Setup position constrains
            if self.config['QuotedPositionFlag']:
                #QUOTED = 2
                cons[1, 0] = CQUOTED
                cons[1, 1] = min(x)
                cons[1, 2] = max(x)

            # Setup positive FWHM constrains
            if self.config['PositiveFwhmFlag']:
                # POSITIVE=1
                cons[2, 0] = CPOSITIVE
                cons[2, 1] = 0
                cons[2, 2] = 0

        return largest, cons

    def estimate_periodic_gauss(self, x, y, bg=None, yscaling=None):
        """Estimation of parameters for periodic gaussian curves:
        *number of peaks, distance between peaks, height, position of the
        first peak, fwhm*

        The functions detects all peaks, then computes the parameters the
        following way:

            - *distance*: average of distances between detected peaks
            - *height*: average height of detected peaks
            - *fwhm*: fwhm of the highest peak (in number of samples) if
                :attr:`config`['AutoFwhm'] is ``True``, else take the default
                value :attr:`config`['FwhmPoints']

        :param x: Array of abscissa values
        :param y: Array of ordinate values (``y = f(x)``)
        :param bg: If not ``None``, background signal to be subtracted from
            ``y`` before fitting gaussian functions to peaks.
        :param yscaling: Scaling factor applied to ``y`` data when searching
            for peaks
        :return: Tuple of estimated fit parameters and fit constraints.
        """
        if yscaling is None:
            try:
                yscaling = self.config['Yscaling']
            except:
                yscaling = 1.0
        if yscaling == 0:
            yscaling = 1.0

        if bg is None:
            bg = numpy.zeros_like(y)

        if self.config['AutoFwhm']:
            search_fwhm = guess_fwhm(y)
        else:
            search_fwhm = int(float(self.config['FwhmPoints']))
        search_sens = float(self.config['Sensitivity'])

        if search_fwhm < 3:
            search_fwhm = 3

        if search_sens < 1:
            search_sens = 1

        if len(y) > 1.5 * search_fwhm:
            peaks = peak_search(yscaling*y, fwhm=search_fwhm,
                                sensitivity=search_sens)
        else:
            peaks = []
        npeaks = len(peaks)
        if not npeaks:
            fittedpar = []
            cons = numpy.zeros((len(fittedpar), 3), numpy.float)
            return fittedpar, cons

        fittedpar = [0.0, 0.0, 0.0, 0.0, 0.0]

        # The number of peaks
        fittedpar[0] = npeaks

        # The separation between peaks in x units
        delta = 0.0
        height = 0.0
        for i in range(npeaks):
            height += y[int(peaks[i])] - bg[int(peaks[i])]
            if i != ((npeaks) - 1):
                delta += (x[int(peaks[i + 1])] - x[int(peaks[i])])

        # delta between peaks
        if npeaks > 1:
            fittedpar[1] = delta / (npeaks - 1)

        # starting height
        fittedpar[2] = height / npeaks

        # position of the first peak
        fittedpar[3] = x[int(peaks[0])]

        # Estimate the fwhm
        fittedpar[4] = search_fwhm

        # setup constraints
        cons = numpy.zeros((5, 3), numpy.float)
        cons[0, 0] = CFIXED  # the number of gaussians
        if npeaks == 1:
            cons[1, 0] = CFIXED  # the delta between peaks
        else:
            cons[1, 0] = CFREE
        j = 2
        # Setup height area constrains
        if not self.config['NoConstraintsFlag']:
            if self.config['PositiveHeightAreaFlag']:
                #POSITIVE = 1
                cons[j, 0] = CPOSITIVE
                cons[j, 1] = 0
                cons[j, 2] = 0
        j += 1

        # Setup position constrains
        if not self.config['NoConstraintsFlag']:
            if self.config['QuotedPositionFlag']:
                #QUOTED = 2
                cons[j, 0] = CQUOTED
                cons[j, 1] = min(x)
                cons[j, 2] = max(x)
        j += 1

        # Setup positive FWHM constrains
        if not self.config['NoConstraintsFlag']:
            if self.config['PositiveFwhmFlag']:
                # POSITIVE=1
                cons[j, 0] = CPOSITIVE
                cons[j, 1] = 0
                cons[j, 2] = 0
        j += 1
        return fittedpar, cons

    def configure(self, *vars, **kw):
        """Add new / unknown keyword arguments to :attr:`config`,
        update entries in :attr:`config` if the parameter name is a existing
        key.

        :param vars: List of all positional arguments (ignored)
        :param kw: Dictionary of keyword arguments.
        :return: Configuration dictionary :attr:`config`
        """
        if not kw.keys():
            return self.config
        for key in kw.keys():
            notdone = 1
            # take care of lower / upper case problems ...
            for config_key in self.config.keys():
                if config_key.lower() == key.lower():
                    self.config[config_key] = kw[key]
                    notdone = 0
            if notdone:
                self.config[key] = kw[key]
        return self.config

fitfuns = SpecfitFunctions()

THEORY = ['Gaussians',
          'Lorentz',
          'Area Gaussians',
          'Area Lorentz',
          'Pseudo-Voigt Line',
          'Area Pseudo-Voigt',
          'Split Gaussian',
          'Split Lorentz',
          'Split Pseudo-Voigt',
          'Step Down',
          'Step Up',
          'Slit',
          'Atan',
          'Hypermet',
          'Periodic Gaussians']
"""Fit function names"""

FUNCTION = [functions.sum_gauss,
            functions.sum_lorentz,
            functions.sum_agauss,
            functions.sum_alorentz,
            functions.sum_pvoigt,
            functions.sum_apvoigt,
            functions.sum_splitgauss,
            functions.sum_splitlorentz,
            functions.sum_splitpvoigt,
            functions.sum_downstep,
            functions.sum_upstep,
            functions.sum_slit,
            fitfuns.atan,
            functions.sum_ahypermet,
            fitfuns.periodic_gauss]
"""Fit functions"""


PARAMETERS = [['Height', 'Position', 'FWHM'],
              ['Height', 'Position', 'Fwhm'],
              ['Area', 'Position', 'Fwhm'],
              ['Area', 'Position', 'Fwhm'],
              ['Height', 'Position', 'Fwhm', 'Eta'],
              ['Area', 'Position', 'Fwhm', 'Eta'],
              ['Height', 'Position', 'LowFWHM', 'HighFWHM'],
              ['Height', 'Position', 'LowFWHM', 'HighFWHM'],
              ['Height', 'Position', 'LowFWHM', 'HighFWHM', 'Eta'],
              ['Height', 'Position', 'FWHM'],
              ['Height', 'Position', 'FWHM'],
              ['Height', 'Position', 'FWHM', 'BeamFWHM'],
              ['Height', 'Position', 'Width'],
              ['G_Area', 'Position', 'FWHM',
               'ST_Area', 'ST_Slope', 'LT_Area', 'LT_Slope', 'Step_H'],
              ['N', 'Delta', 'Height', 'Position', 'FWHM']]
"""Lists of minimal parameters required by each fit function"""

ESTIMATE = [fitfuns.estimate_height_position_fwhm,  # for gauss
            fitfuns.estimate_height_position_fwhm,  # for lorentz
            fitfuns.estimate_agauss,
            fitfuns.estimate_alorentz,
            fitfuns.estimate_pvoigt,
            fitfuns.estimate_apvoigt,
            fitfuns.estimate_splitgauss,
            fitfuns.estimate_splitgauss,
            fitfuns.estimate_splitpvoigt,
            fitfuns.estimate_downstep,
            fitfuns.estimate_upstep,
            fitfuns.estimate_slit,
            fitfuns.estimate_upstep,                # for atan
            fitfuns.estimate_ahypermet,
            fitfuns.estimate_periodic_gauss]
"""Parameter estimation functions"""

CONFIGURE = [fitfuns.configure,
             fitfuns.configure,
             fitfuns.configure,
             fitfuns.configure,
             fitfuns.configure,
             fitfuns.configure,
             fitfuns.configure,
             fitfuns.configure,
             fitfuns.configure,
             fitfuns.configure,
             fitfuns.configure,
             fitfuns.configure,
             fitfuns.configure,
             fitfuns.configure,
             fitfuns.configure]
"""Configuration functions"""


def test(a):
    from silx.gui import qt
    from silx.gui.plot import plot1D
    from silx.math.fit import specfit
    x = numpy.arange(1000).astype(numpy.float)
    p = numpy.array([1500, 100., 50.0,
                     1500, 700., 50.0])
    y_synthetic = functions.sum_gauss(x, *p) + 1

    fit = specfit.Specfit(x, y_synthetic)
    fit.addtheory('Gaussians', functions.sum_gauss, ['Height', 'Position', 'FWHM'],
                  a.estimate_height_position_fwhm)
    fit.settheory('Gaussians')
    fit.setbackground('Linear')

    fit.estimate()
    fit.startfit()

    y_fit = fit.gendata()

    app = qt.QApplication([])

    # Offset of 1 to see the difference in log scale
    plot1D(x, (y_synthetic + 1, y_fit), "Input data + 1, Fit")

    app.exec_()


if __name__ == "__main__":
    test(fitfuns)

