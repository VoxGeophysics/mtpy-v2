#!/usr/bin/env python

"""
Z
===

Container for the Impedance Tensor 

Originally written by Jared Peacock Lars Krieger
Updated 2022 by J. Peacock to work with new framework

"""

# =============================================================================
# Imports
# =============================================================================
import copy
import numpy as np

from .base import TFBase
from . import MT_TO_OHM_FACTOR, IMPEDANCE_UNITS
from .pt import PhaseTensor
from .z_analysis import (
    ZInvariants,
    find_distortion,
    remove_distortion_from_z_object,
    calculate_depth_of_investigation,
)


# ==============================================================================
# Impedance Tensor Class
# ==============================================================================
class Z(TFBase):
    """Z class - generates an impedance tensor (Z) object.

    Z is a complex array of the form (n_frequency, 2, 2),
    with indices in the following order:

        - Zxx: (0,0)
        - Zxy: (0,1)
        - Zyx: (1,0)
        - Zyy: (1,1)

    All errors are given as standard deviations (sqrt(VAR))
    :param z: Array containing complex impedance values.
    :type z: numpy.ndarray(n_frequency, 2, 2)
    :param z_error: Array containing error values (standard deviation)
        of impedance tensor elements.
    :type z_error: numpy.ndarray(n_frequency, 2, 2)
    :param frequency: Array of frequencyuency values corresponding to impedance
        tensor elements.
    :type frequency: np.ndarray(n_frequency)
    """

    def __init__(
        self,
        z=None,
        z_error=None,
        frequency=None,
        z_model_error=None,
        units="mt",
    ):
        """Initialize an instance of the Z class.
        :param z_model_error:
            Defaults to None.
        :param z: Array containing complex impedance values, defaults to None.
        :type z: numpy.ndarray(n_frequency, 2, 2), optional
        :param z_error: Array containing error values (standard deviation)
            of impedance tensor elements, defaults to None.
        :type z_error: numpy.ndarray(n_frequency, 2, 2), optional
        :param frequency: Array of frequencyuency values corresponding to impedance
            tensor elements, defaults to None.
        :type frequency: np.ndarray(n_frequency), optional
        :param units: units for the impedance [ "mt" [mV/km/nT] | ohm [Ohms] ]
        :type units: str

        """

        self._ohm_factor = MT_TO_OHM_FACTOR
        self._unit_factors = IMPEDANCE_UNITS
        self.units = units

        # if units input is ohms, then we want to scale them to mt units that
        # way the underlying data is consistent in [mV/km/nT]
        if z is not None:
            z = z * self._scale_factor
        if z_error is not None:
            z_error = z_error * self._scale_factor
        if z_model_error is not None:
            z_model_error = z_model_error * self._scale_factor

        super().__init__(
            tf=z,
            tf_error=z_error,
            tf_model_error=z_model_error,
            frequency=frequency,
            _name="impedance",
        )

    @property
    def units(self):
        """impedance units"""
        return self._units

    @units.setter
    def units(self, value):
        """impedance units setter options are [ mt | ohm ]"""
        if not isinstance(value, str):
            raise TypeError("Units input must be a string.")
        if value.lower() not in self._unit_factors.keys():
            raise ValueError(
                f"{value} is not an acceptable unit for impedance."
            )

        self._units = value

    @property
    def _scale_factor(self):
        """unit scale factor"""
        return self._unit_factors[self._units]

    @property
    def z(self):
        """Impedance tensor

        np.ndarray(nfrequency, 2, 2).
        """
        if self._has_tf():
            return self._dataset.transfer_function.values / self._scale_factor

    @z.setter
    def z(self, z):
        """Set the attribute 'z'. Should be in units of mt [mV/km/nT]
        :param z: Complex impedance tensor array.
        :type z: np.ndarray(nfrequency, 2, 2)
        """

        old_shape = None
        if self._has_tf():
            old_shape = self._dataset.transfer_function.shape
        elif self._has_frequency():
            old_shape = (
                self.frequency.size,
                self._expected_shape[0],
                self._expected_shape[1],
            )
        z = self._validate_array_input(z, "complex", old_shape)
        if z is None:
            return

        if self._is_empty():
            self._dataset = self._initialize(tf=z)
        else:
            self._dataset["transfer_function"].loc[self.comps] = z

    # ----impedance error-----------------------------------------------------
    @property
    def z_error(self):
        """Error of impedance tensor array as standard deviation."""
        if self._has_tf_error():
            return (
                self._dataset.transfer_function_error.values
                / self._scale_factor
            )

    @z_error.setter
    def z_error(self, z_error):
        """Set the attribute z_error.
        :param z_error: Error of impedance tensor array as standard deviation.
        :type z_error: np.ndarray(nfrequency, 2, 2)
        """
        old_shape = None
        if not self._has_tf_error():
            old_shape = self._dataset.transfer_function_error.shape
        elif self._has_frequency():
            old_shape = (
                self.frequency.size,
                self._expected_shape[0],
                self._expected_shape[1],
            )

        z_error = self._validate_array_input(z_error, "float", old_shape)
        if z_error is None:
            return

        if self._is_empty():
            self._dataset = self._initialize(tf_error=z_error)
        else:
            self._dataset["transfer_function_error"].loc[self.comps] = z_error

    # ----impedance model error-----------------------------------------------------
    @property
    def z_model_error(self):
        """Model error of impedance tensor array as standard deviation."""
        if self._has_tf_model_error():
            return (
                self._dataset.transfer_function_model_error.values
                / self._scale_factor
            )

    @z_model_error.setter
    def z_model_error(self, z_model_error):
        """Set the attribute z_model_error.
        :param z_model_error: Error of impedance tensor array as standard
            deviation.
        :type z_model_error: np.ndarray(nfrequency, 2, 2)
        """

        old_shape = None
        if not self._has_tf_model_error():
            old_shape = self._dataset.transfer_function_error.shape

        elif self._has_frequency():
            old_shape = (
                self.frequency.size,
                self._expected_shape[0],
                self._expected_shape[1],
            )

        z_model_error = self._validate_array_input(
            z_model_error, "float", old_shape
        )

        if z_model_error is None:
            return

        if self._is_empty():
            self._dataset = self._initialize(tf_error=z_model_error)
        else:
            self._dataset["transfer_function_model_error"].loc[
                self.comps
            ] = z_model_error

    def remove_ss(
        self, reduce_res_factor_x=1.0, reduce_res_factor_y=1.0, inplace=False
    ):
        """Remove the static shift by providing the respective correction factors
        for the resistivity in the x and y components.
        (Factors can be determined by using the "Analysis" module for the
        impedance tensor)

        Assume the original observed tensor Z is built by a static shift S
        and an unperturbated "correct" Z0 :

             * Z = S * Z0

        therefore the correct Z will be :
            * Z0 = S^(-1) * Z
        :param reduce_res_factor_x: Static shift factor to be applied to x
            components (ie z[:, 0, :]).  This is assumed to be in resistivity scale, defaults to 1.0.
        :type reduce_res_factor_x: float or iterable list or array, optional
        :param reduce_res_factor_y: Static shift factor to be applied to y
            components (ie z[:, 1, :]).  This is assumed to be in resistivity scale, defaults to 1.0.
        :type reduce_res_factor_y: float or iterable list or array, optional
        :param inplace: Update the current object or return a new impedance, defaults to False.
        :type inplace: boolean, optional
        :return s: Static shift matrix,.
        :rtype s: np.ndarray ((2, 2))
        :return s: Corrected Z if inplace is False.
        :rtype s: mtpy.core.z.Z
        """

        def _validate_factor_single(factor):
            """Validate factor single."""
            try:
                x_factor = float(factor)
            except ValueError:
                msg = f"factor must be a valid number not {factor}"
                self.logger.error(msg)
                raise ValueError(msg)
            return np.repeat(x_factor, len(self.z))

        def _validate_ss_input(factor):
            """Validate ss input."""
            if not np.iterable(factor):
                x_factor = _validate_factor_single(factor)

            elif len(reduce_res_factor_x) == 1:
                x_factor = _validate_factor_single(factor)
            else:
                x_factor = np.array(factor, dtype=float)

            if len(x_factor) != len(self.z):
                msg = (
                    f"Length of reduce_res_factor_x needs to be {len(self.z)} "
                    f" not {len(x_factor)}"
                )
                self.logger.error(msg)
                raise ValueError(msg)
            return x_factor

        x_factors = np.sqrt(_validate_ss_input(reduce_res_factor_x))
        y_factors = np.sqrt(_validate_ss_input(reduce_res_factor_y))

        z_corrected = copy.copy(self.z)

        z_corrected[:, 0, 0] = (
            self.z[:, 0, 0] * self._scale_factor
        ) / x_factors
        z_corrected[:, 0, 1] = (
            self.z[:, 0, 1] * self._scale_factor
        ) / x_factors
        z_corrected[:, 1, 0] = (
            self.z[:, 1, 0] * self._scale_factor
        ) / y_factors
        z_corrected[:, 1, 1] = (
            self.z[:, 1, 1] * self._scale_factor
        ) / y_factors

        z_corrected = z_corrected / self._scale_factor

        if inplace:
            self.z = z_corrected
        else:
            return Z(
                z=z_corrected,
                z_error=self.z_error,
                frequency=self.frequency,
                z_model_error=self.z_model_error,
                units=self.units,
            )

    def remove_distortion(
        self,
        distortion_tensor=None,
        distortion_error_tensor=None,
        n_frequencies=None,
        comp="det",
        only_2d=False,
        inplace=False,
    ):
        """Remove distortion D form an observed impedance tensor Z to obtain
        the uperturbed "correct" Z0:
        Z = D * Z0

        Propagation of errors/uncertainties included
        :param only_2d:
            Defaults to False.
        :param comp:
            Defaults to "det".
        :param n_frequencies:
            Defaults to None.
        :param distortion_tensor: Real distortion tensor as a 2x2, defaults to None.
        :type distortion_tensor: np.ndarray(2, 2, dtype=real), optional
        :param distortion_error_tensor:, defaults to None.
        :type distortion_error_tensor: np.ndarray(2, 2, dtype=real),, optional
        :param inplace: Update the current object or return a new impedance, defaults to False.
        :type inplace: boolean, optional
        :return s: Input distortion tensor.
        :rtype s: np.ndarray(2, 2, dtype='real')
        :return s: Impedance tensor with distorion removed.
        :rtype s: np.ndarray(num_frequency, 2, 2, dtype='complex')
        :return s: Impedance tensor error after distortion is removed.
        :rtype s: np.ndarray(num_frequency, 2, 2, dtype='complex')
        """

        if distortion_tensor is None:
            (
                distortion_tensor,
                distortion_error_tensor,
            ) = self.estimate_distortion(
                n_frequencies=n_frequencies, comp=comp, only_2d=only_2d
            )

        z_corrected, z_corrected_error = remove_distortion_from_z_object(
            self, distortion_tensor, distortion_error_tensor, self.logger
        )

        # into mt units
        z_corrected = z_corrected * self._scale_factor
        z_corrected_error = z_corrected_error * self._scale_factor

        if inplace:
            self.z = z_corrected
            self.z_error = z_corrected_error
        else:
            z_object = Z(
                z=z_corrected,
                z_error=z_corrected_error,
                frequency=self.frequency,
                z_model_error=self.z_model_error,
            )
            z_object.units = self.units
            return z_object

    @property
    def resistivity(self):
        """Resistivity of impedance."""
        if self.z is not None:
            return np.apply_along_axis(
                lambda x: np.abs(x) ** 2 / self.frequency * 0.2,
                0,
                self.z * self._scale_factor,
            )

    @property
    def phase(self):
        """Phase of impedance."""
        if self.z is not None:
            return np.rad2deg(np.angle(self.z * self._scale_factor))

    @property
    def resistivity_error(self):
        """Resistivity error of impedance

        By standard error propagation, relative error in resistivity is
        2*relative error in z amplitude..
        """
        if self.z is not None and self.z_error is not None:
            with np.errstate(divide="ignore", invalid="ignore"):
                return np.apply_along_axis(
                    lambda x: x / self.frequency * 0.2,
                    0,
                    2
                    * (self.z_error * self._scale_factor)
                    * np.abs(self.z * self._scale_factor),
                )

    @property
    def phase_error(self):
        """Phase error of impedance

        Uncertainty in phase (in degrees) is computed by defining a circle around
        the z vector in the complex plane. The uncertainty is the absolute angle
        between the vector to (x,y) and the vector between the origin and the
        tangent to the circle..
        """
        if self.z is not None and self.z_error is not None:
            with np.errstate(divide="ignore", invalid="ignore"):
                return np.degrees(np.arctan(self.z_error / np.abs(self.z)))

    @property
    def resistivity_model_error(self):
        """Resistivity model error of impedance."""
        if self.z is not None and self.z_model_error is not None:
            with np.errstate(divide="ignore", invalid="ignore"):
                return np.apply_along_axis(
                    lambda x: x / self.frequency * 0.2,
                    0,
                    2
                    * (self.z_model_error * self._scale_factor)
                    * np.abs(self.z * self._scale_factor),
                )

    @property
    def phase_model_error(self):
        """Phase model error of impedance."""
        if self.z is not None and self.z_model_error is not None:
            with np.errstate(divide="ignore", invalid="ignore"):
                return np.degrees(
                    np.arctan(self.z_model_error / np.abs(self.z))
                )

    def _compute_z_error(self, res_error, phase_error):
        """Compute z error from apparent resistivity and phase.
        :param res: Resistivity array.
        :type res: np.ndarray
        :param res_error: Resistivity error array.
        :type res_error: np.ndarray
        :param phase: Phase array in degrees.
        :type phase: np.ndarray
        :param phase_error: Phase error array in degrees.
        :type phase_error: np.ndarray
        :return: Impedance error as a float.
        :rtype: np.ndarray
        """
        if res_error is None:
            return None

        # not extremely positive where the 250 comes from it is roughly 5 x 50
        # which is about 5 * (2*pi)**2
        return np.abs(
            np.sqrt(self.frequency * (res_error.T) * 250).T
            * np.tan(np.radians(phase_error))
        )

    def set_resistivity_phase(
        self,
        resistivity,
        phase,
        frequency,
        res_error=None,
        phase_error=None,
        res_model_error=None,
        phase_model_error=None,
    ):
        """Set values for resistivity (res - in Ohm m) and phase
        (phase - in degrees), including error propagation.
        :param phase_model_error:
            Defaults to None.
        :param res_model_error:
            Defaults to None.
        :param resistivity: Resistivity array in Ohm-m.
        :type resistivity: np.ndarray(num_frequency, 2, 2)
        :param phase: Phase array in degrees.
        :type phase: np.ndarray(num_frequency, 2, 2)
        :param frequency: Frequency array in Hz.
        :type frequency: np.ndarray(num_frequency)
        :param res_error: Resistivity error array in Ohm-m, defaults to None.
        :type res_error: np.ndarray(num_frequency, 2, 2), optional
        :param phase_error: Phase error array in degrees, defaults to None.
        :type phase_error: np.ndarray(num_frequency, 2, 2), optional
        """

        if resistivity is None or phase is None or frequency is None:
            self.logger.debug(
                "Cannot estimate resitivity and phase if resistivity, "
                "phase, or frequency is None."
            )
            return

        self.frequency = self._validate_frequency(frequency)
        resistivity = self._validate_array_input(resistivity, float)
        phase = self._validate_array_input(phase, float)

        res_error = self._validate_array_input(res_error, float)
        phase_error = self._validate_array_input(phase_error, float)
        res_model_error = self._validate_array_input(res_model_error, float)
        phase_model_error = self._validate_array_input(phase_model_error, float)

        abs_z = np.sqrt(5.0 * self.frequency * (resistivity.T)).T
        self.z = abs_z * np.exp(1j * np.radians(phase))

        self.z_error = self._compute_z_error(res_error, phase_error)
        self.z_model_error = self._compute_z_error(
            res_model_error, phase_model_error
        )

    @property
    def det(self):
        """Determinant of impedance."""
        if self.z is not None:
            det_z = np.array(
                [np.linalg.det(ii * self._scale_factor) ** 0.5 for ii in self.z]
            )

            return det_z

    @property
    def det_error(self):
        """Return the determinant of impedance error."""
        det_z_error = None
        if self.z_error is not None:
            det_z_error = np.zeros_like(self.det, dtype=float)
            with np.errstate(invalid="ignore"):
                # components of the impedance tensor are not independent variables
                # so can't use standard error propagation
                # calculate manually:
                # difference of determinant of z + z_error and z - z_error then divide by 2
                det_z_error[:] = (
                    self._scale_factor
                    * (
                        np.abs(
                            np.linalg.det(self.z + self.z_error)
                            - np.linalg.det(self.z - self.z_error)
                        )
                        / 2.0
                    )
                    ** 0.5
                )
        return det_z_error

    @property
    def det_model_error(self):
        """Return the determinant of impedance model error."""
        det_z_error = None
        if self.z_model_error is not None:
            det_z_error = np.zeros_like(self.det, dtype=float)
            with np.errstate(invalid="ignore"):
                # components of the impedance tensor are not independent variables
                # so can't use standard error propagation
                # calculate manually:
                # difference of determinant of z + z_error and z - z_error then divide by 2
                det_z_error[:] = (
                    np.abs(
                        np.linalg.det(self.z + self.z_model_error)
                        - np.linalg.det(self.z - self.z_model_error)
                    )
                    / 2.0
                ) ** 0.5
        return det_z_error

    @property
    def phase_det(self):
        """Phase determinant."""
        if self.det is not None:
            return np.rad2deg(np.arctan2(self.det.imag, self.det.real))

    @property
    def phase_error_det(self):
        """Phase error determinant."""
        if self.det is not None:
            return np.rad2deg(np.arcsin(self.det_error / abs(self.det)))

    @property
    def phase_model_error_det(self):
        """Phase model error determinant."""
        if self.det is not None:
            return np.rad2deg(np.arcsin(self.det_model_error / abs(self.det)))

    @property
    def res_det(self):
        """Resistivity determinant."""
        if self.det is not None:
            return 0.2 * (1.0 / self.frequency) * abs(self.det) ** 2

    @property
    def res_error_det(self):
        """Resistivity error determinant."""
        if self.det_error is not None:
            return (
                0.2
                * (1.0 / self.frequency)
                * np.abs(self.det + self.det_error) ** 2
                - self.res_det
            )

    @property
    def res_model_error_det(self):
        """Resistivity model error determinant."""
        if self.det_model_error is not None:
            return (
                0.2
                * (1.0 / self.frequency)
                * np.abs(self.det + self.det_model_error) ** 2
                - self.res_det
            )

    def _get_component(self, comp, array):
        """Get the correct component from an array.
        :param comp: [ xx | xy | yx | yy ].
        :type comp: string
        :param array: Impedance array.
        :type array: np.ndarray
        :return: Array component.
        :rtype: np.ndarray
        """
        if array is not None:
            index_dict = {"x": 0, "y": 1}
            ii = index_dict[comp[-2]]
            jj = index_dict[comp[-1]]

            return array[:, ii, jj]

    @property
    def res_xx(self):
        """Resistivity of xx component."""
        return self._get_component("xx", self.resistivity)

    @property
    def res_xy(self):
        """Resistivity of xy component."""
        return self._get_component("xy", self.resistivity)

    @property
    def res_yx(self):
        """Resistivity of yx component."""
        return self._get_component("yx", self.resistivity)

    @property
    def res_yy(self):
        """Resistivity of yy component."""
        return self._get_component("yy", self.resistivity)

    @property
    def res_error_xx(self):
        """Resistivity error of xx component."""
        return self._get_component("xx", self.resistivity_error)

    @property
    def res_error_xy(self):
        """Resistivity error of xy component."""
        return self._get_component("xy", self.resistivity_error)

    @property
    def res_error_yx(self):
        """Resistivity error of yx component."""
        return self._get_component("yx", self.resistivity_error)

    @property
    def res_error_yy(self):
        """Resistivity error of yy component."""
        return self._get_component("yy", self.resistivity_error)

    @property
    def res_model_error_xx(self):
        """Resistivity model error of xx component."""
        return self._get_component("xx", self.resistivity_model_error)

    @property
    def res_model_error_xy(self):
        """Resistivity model error of xy component."""
        return self._get_component("xy", self.resistivity_model_error)

    @property
    def res_model_error_yx(self):
        """Resistivity model error of yx component."""
        return self._get_component("yx", self.resistivity_model_error)

    @property
    def res_model_error_yy(self):
        """Resistivity model error of yy component."""
        return self._get_component("yy", self.resistivity_model_error)

    @property
    def phase_xx(self):
        """Phase of xx component."""
        return self._get_component("xx", self.phase)

    @property
    def phase_xy(self):
        """Phase of xy component."""
        return self._get_component("xy", self.phase)

    @property
    def phase_yx(self):
        """Phase of yx component."""
        return self._get_component("yx", self.phase)

    @property
    def phase_yy(self):
        """Phase of yy component."""
        return self._get_component("yy", self.phase)

    @property
    def phase_error_xx(self):
        """Phase error of xx component."""
        return self._get_component("xx", self.phase_error)

    @property
    def phase_error_xy(self):
        """Phase error of xy component."""
        return self._get_component("xy", self.phase_error)

    @property
    def phase_error_yx(self):
        """Phase error of yx component."""
        return self._get_component("yx", self.phase_error)

    @property
    def phase_error_yy(self):
        """Phase error of yy component."""
        return self._get_component("yy", self.phase_error)

    @property
    def phase_model_error_xx(self):
        """Phase model error of xx component."""
        return self._get_component("xx", self.phase_model_error)

    @property
    def phase_model_error_xy(self):
        """Phase model error of xy component."""
        return self._get_component("xy", self.phase_model_error)

    @property
    def phase_model_error_yx(self):
        """Phase model error of yx component."""
        return self._get_component("yx", self.phase_model_error)

    @property
    def phase_model_error_yy(self):
        """Phase model error of yy component."""
        return self._get_component("yy", self.phase_model_error)

    @property
    def phase_tensor(self):
        """Phase tensor object based on impedance."""
        return PhaseTensor(
            z=self.z,
            z_error=self.z_error,
            z_model_error=self.z_model_error,
            frequency=self.frequency,
        )

    @property
    def invariants(self):
        """Weaver Invariants."""
        return ZInvariants(z=self.z)

    def estimate_dimensionality(
        self, skew_threshold=5, eccentricity_threshold=0.1
    ):
        """Estimate dimensionality of the impedance tensor from parameters such
        as strike and phase tensor eccentricity
        :return: DESCRIPTION.
        :rtype: TYPE
        """

        dimensionality = np.ones(self.period.size, dtype=int)

        # need to get 2D first then 3D
        dimensionality[
            np.where(self.phase_tensor.eccentricity > eccentricity_threshold)
        ] = 2
        dimensionality[
            np.where(np.abs(self.phase_tensor.skew) > skew_threshold)
        ] = 3

        return dimensionality

    def estimate_distortion(
        self, n_frequencies=None, comp="det", only_2d=False, clockwise=True
    ):
        """Estimate distortion.
        :param only_2d:
            Defaults to False.
        :param n_frequencies: DESCRIPTION, defaults to None.
        :type n_frequencies: TYPE, optional
        :param comp: DESCRIPTION, defaults to "det".
        :type comp: TYPE, optional
        :param: DESCRIPTION.
        :type: TYPE
        :return: DESCRIPTION.
        :rtype: TYPE
        """
        if n_frequencies is None:
            nf = self.frequency.size
        else:
            nf = n_frequencies

        if self._has_tf():
            new_z_object = Z(
                z=self._dataset.transfer_function.values[0:nf, :, :],
                frequency=self.frequency[0:nf],
            )
            if self._has_tf_error():
                new_z_object.z_error = (
                    self._dataset.transfer_function_error.values[0:nf]
                )

        return find_distortion(
            new_z_object, comp=comp, only_2d=only_2d, clockwise=clockwise
        )

    def estimate_depth_of_investigation(self):
        """Estimate depth of investigation.
        :return: DESCRIPTION.
        :rtype: TYPE
        """

        return calculate_depth_of_investigation(self)
