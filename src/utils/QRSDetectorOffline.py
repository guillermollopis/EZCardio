import numpy as np
import matplotlib.pyplot as plt
from time import gmtime, strftime
import scipy
from scipy.signal import butter, lfilter

from scipy import ndimage
#from numba import jit

LOG_DIR = "logs/"
PLOT_DIR = "plots/"


class QRSDetectorOffline(object):
    """
    Python Offline ECG QRS Detector based on the Pan-Tomkins algorithm.

    Michał Sznajder (Jagiellonian University) - technical contact (msznajder@gmail.com)
    Marta Łukowska (Jagiellonian University)
    The module is offline Python implementation of QRS complex detection in the ECG signal based
    on the Pan-Tomkins algorithm: Pan J, Tompkins W.J., A real-time QRS detection algorithm,
    IEEE Transactions on Biomedical Engineering, Vol. BME-32, No. 3, March 1985, pp. 230-236.
    The QRS complex corresponds to the depolarization of the right and left ventricles of the human heart. It is the most visually obvious part of the ECG signal. QRS complex detection is essential for time-domain ECG signal analyses, namely heart rate variability. It makes it possible to compute inter-beat interval (RR interval) values that correspond to the time between two consecutive R peaks. Thus, a QRS complex detector is an ECG-based heart contraction detector.
    Offline version detects QRS complexes in a pre-recorded ECG signal dataset (e.g. stored in .csv format).
    This implementation of a QRS Complex Detector is by no means a certified medical tool and should not be used in health monitoring. It was created and used for experimental purposes in psychophysiology and psychology.
    You can find more information in module documentation:
    https://github.com/c-labpl/qrs_detector
    If you use these modules in a research project, please consider citing it:
    https://zenodo.org/record/583770
    If you use these modules in any other project, please refer to MIT open-source license.
    MIT License
    Copyright (c) 2017 Michał Sznajder, Marta Łukowska
    Permission is hereby granted, free of charge, to any person obtaining a copy
    of this software and associated documentation files (the "Software"), to deal
    in the Software without restriction, including without limitation the rights
    to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
    copies of the Software, and to permit persons to whom the Software is
    furnished to do so, subject to the following conditions:
    The above copyright notice and this permission notice shall be included in all
    copies or substantial portions of the Software.
    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
    AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
    LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
    OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
    SOFTWARE.
    """

    def __init__(self, ecg_raw, ecg_data, fs, verbose=True, log_data=False, plot_data=False, show_plot=False):
        """
        QRSDetectorOffline class initialisation method.
        :param string ecg_data: data
        :param bool verbose: flag for printing the results
        :param bool log_data: flag for logging the results
        :param bool plot_data: flag for plotting the results to a file
        :param bool show_plot: flag for showing generated results plot - will not show anything if plot is not generated
        """
        # Configuration parameters.
        #if ecg_data is not None:
        #    self.ecg_data = ecg_data

        self.signal_frequency = fs  # Set ECG device frequency in samples per second here.

        self.filter_lowcut = 0.0
        self.filter_highcut = 15.0
        self.filter_order = 1

        self.integration_window = int(fs/16.7)  # Change proportionally when adjusting frequency (in samples). 15 for 250 hz

        self.findpeaks_limit = 0.35
        self.findpeaks_spacing = int(fs/5)*2  # Change proportionally when adjusting frequency (in samples).50 for 250 hz

        self.refractory_period = fs/2.083  # Change proportionally when adjusting frequency (in samples).120 for 250 hz
        self.qrs_peak_filtering_factor = 0.125 # og is 0.125
        self.noise_peak_filtering_factor = 0.125 # og is 0.125
        self.qrs_noise_diff_weight = 0.25 # og is 0.25

        # Loaded ECG data.
        self.ecg_no_filter = ecg_raw
        self.ecg_data_raw = ecg_data

        # Measured and calculated values.
        self.filtered_ecg_measurements = None
        self.differentiated_ecg_measurements = None
        self.squared_ecg_measurements = None
        self.integrated_ecg_measurements = None
        self.detected_peaks_indices = None
        self.detected_peaks_values = None

        self.qrs_peak_value = 0.0
        self.noise_peak_value = 0.0
        self.threshold_value = 0.0

        # Detection results.
        self.qrs_peaks_indices = np.array([], dtype=int)
        self.noise_peaks_indices = np.array([], dtype=int)

        # Final ECG data and QRS detection results array - samples with detected QRS are marked with 1 value.
        self.ecg_data_detected = None

        # Run whole detector flow.
        #self.load_ecg_data()
        
        self.detect_peaks(fs)
        self.detected_peaks_indices = self.detected_peaks_indices.astype(int)

        detect_noise = True
        # detect ecg noise
        if detect_noise:
            low_noise_intervals = self.detect_low_ecg_noise(self.integrated_ecg_measurements, fs)
            high_noise_intervals = self.detect_high_ecg_noise(self.integrated_ecg_measurements, fs, self.detected_peaks_indices)
            intervals = sorted(low_noise_intervals + high_noise_intervals, key=lambda x: x[0])

            merged_start = np.array([], dtype=int)
            merged_end = np.array([], dtype=int)

            if (len(intervals) > 0):
                start, end = intervals[0]
                min_combine_noise_distance = 2*fs

                for current_start, current_end in intervals[1:]:
                    if current_start <= end + min_combine_noise_distance:
                        # Overlapping or close intervals, merge them
                        end = max(end, current_end)
                    else:
                        # No overlap, add the previous interval and start a new one
                        merged_start = np.append(merged_start, start)
                        merged_end = np.append(merged_end, end)
                        start, end = current_start, current_end

                    # delete peaks in the interval
                    delete_indexes = np.zeros(self.detected_peaks_indices.shape, dtype=bool)  # Create a mask of True values
                    delete_indexes[(self.detected_peaks_indices > start) & (self.detected_peaks_indices < end)] = True 
                
                    self.detected_peaks_indices = np.delete(self.detected_peaks_indices, delete_indexes)
                    self.detected_peaks_values = np.delete(self.detected_peaks_values, delete_indexes)

                # Add the last interval
                merged_start = np.append(merged_start, start)
                merged_end = np.append(merged_end, end)
                from gui import PALMS

                # add noise to partitions and palms
                for new_start, new_end in zip(merged_end, merged_start): 
                    PALMS.get().START_INDEXES = np.append(PALMS.get().START_INDEXES, int(new_start))
                    PALMS.get().END_INDEXES = np.append(PALMS.get().END_INDEXES, int(new_end))
                    PALMS.get().START_ECG_INDEXES = np.append(PALMS.get().START_ECG_INDEXES, int(new_start))
                    PALMS.get().END_ECG_INDEXES = np.append(PALMS.get().END_ECG_INDEXES, int(new_end))

                PALMS.get().END_ECG_INDEXES = np.sort(PALMS.get().END_ECG_INDEXES)
                PALMS.get().END_INDEXES = np.sort(PALMS.get().END_INDEXES)
                PALMS.get().START_ECG_INDEXES = np.sort(PALMS.get().START_ECG_INDEXES)
                PALMS.get().START_INDEXES = np.sort(PALMS.get().START_INDEXES)

        #self.detected_peaks_indices, self.detected_peaks_values, self.qrs_peaks_indices, self.qrs_peak_value, self.noise_peaks_indices, self.noise_peak_value, self.threshold_value = QRSDetectorOffline.detect_qrs_plus(self.integrated_ecg_measurements, self.signal_frequency, self.detected_peaks_indices, self.detected_peaks_values, self.refractory_period, self.qrs_peak_filtering_factor, self.noise_peak_filtering_factor, self.qrs_noise_diff_weight, self.qrs_peaks_indices, self.threshold_value, self.qrs_peak_value, self.noise_peaks_indices, self.noise_peak_value)
        self.detected_peaks_indices, self.detected_peaks_values, self.qrs_peaks_indices, self.qrs_peak_value, self.noise_peaks_indices, self.noise_peak_value, self.threshold_value = QRSDetectorOffline.detect_qrs(self, self.integrated_ecg_measurements, self.detected_peaks_indices, self.detected_peaks_values, self.refractory_period, self.qrs_peak_filtering_factor, self.noise_peak_filtering_factor, self.qrs_noise_diff_weight, self.qrs_peaks_indices, self.threshold_value, self.qrs_peak_value, self.noise_peaks_indices, self.noise_peak_value, self.signal_frequency)
        
        if verbose:
            self.print_detection_data()

        #if log_data:
        #    self.log_path = "{:s}QRS_offline_detector_log_{:s}.csv".format(LOG_DIR,
        #                                                                   strftime("%Y_%m_%d_%H_%M_%S", gmtime()))
        #    self.log_detection_data()

        if plot_data:
            self.plot_path = "{:s}QRS_offline_detector_plot_{:s}.png".format(PLOT_DIR,
                                                                             strftime("%Y_%m_%d_%H_%M_%S", gmtime()))
            self.plot_detection_data(show_plot=show_plot)

    """Loading ECG measurements data methods."""

    def load_ecg_data(self):
        """
        Method loading ECG data set from a file.
        """
        self.ecg_data_raw = np.loadtxt(self.ecg_data, skiprows=1, usecols=8, delimiter=',')

    """ECG measurements data processing methods."""

    #@jit
    def detect_peaks(self, fs):
        """
        Method responsible for extracting peaks from loaded ECG measurements data through measurements processing.
        """
        # loop in ecg_physionet, which calls this function. So unnecessary here
        # Extract measurements from loaded ECG data.
        ecg_measurements = self.ecg_data_raw
        # Upsampling from 130 Hz to 2000 Hz
        #upsampling_factor = 2000 / fs
        
        self.filtered_ecg_measurements = ecg_measurements
        #self.filtered_ecg_measurements = np.array(ndimage.zoom(ecg_measurements, upsampling_factor))
        
        # Measurements filtering - 0-15 Hz band pass filter.
        #self.filtered_ecg_measurements = self.bandpass_filter(self.filtered_ecg_measurements, lowcut=self.filter_lowcut,
        #                                                      highcut=self.filter_highcut, signal_freq=self.signal_frequency,
        #                                                      filter_order=self.filter_order)
        self.filtered_ecg_measurements[:5] = self.filtered_ecg_measurements[5]
        self.filtered_ecg_measurements, self.differentiated_ecg_measurements, self.squared_ecg_measurements, self.integrated_ecg_measurements, self.detected_peaks_indices = QRSDetectorOffline.detect_peaks_midle_plus(fs, self.filtered_ecg_measurements, self.integration_window, self.findpeaks_limit, self.findpeaks_spacing)
        
        self.detected_peaks_indices = self.detected_peaks_indices.reshape(self.detected_peaks_indices.size)
        if self.findpeaks_limit is not None:
            self.detected_peaks_indices = self.detected_peaks_indices[self.integrated_ecg_measurements[self.detected_peaks_indices] > self.findpeaks_limit]
        
        #self.detected_peaks_indices = self.interpolate_peaks()
        self.detected_peaks_values = self.integrated_ecg_measurements[self.detected_peaks_indices]

        # indices to proper values
        #self.detected_peaks_indices = ((self.detected_peaks_indices+27) / upsampling_factor)
        
        # Downsampling from 2000 Hz to 130 Hz
        downsampling_factor = fs / 2000
        
        #self.filtered_ecg_measurements = np.array(ndimage.zoom(self.filtered_ecg_measurements, downsampling_factor))
        new_length = len(ecg_measurements)
        #self.filtered_ecg_measurements = QRSDetectorOffline.downsample_ecg(self.filtered_ecg_measurements, new_length)
        
        if (len(self.detected_peaks_indices) > 0 and self.detected_peaks_indices[-1] >= len(self.filtered_ecg_measurements)):
            self.detected_peaks_indices = self.detected_peaks_indices[:-1]
            self.detected_peaks_values = self.detected_peaks_values[:-1]

        self.detected_peaks_indices = np.round(self.detected_peaks_indices, 3)
        self.detected_peaks_values = np.round(self.detected_peaks_values, 3)

    
    def interpolate_peaks(self):
        from scipy.signal import resample, find_peaks

        upsample_factor = int(2000/self.signal_frequency)
        window_size = int(0.1*self.signal_frequency)

        peaks_indexes = []
        peaks_indexes = np.array(peaks_indexes)

        for peak in self.detected_peaks_indices:

            # Define the window around the detected peak
            start_idx = max(0, peak - window_size)
            end_idx = min(len(self.filtered_ecg_measurements), peak + window_size)
            segment = self.filtered_ecg_measurements[start_idx:end_idx]

            # Upsample the segment
            upsampled_segment = resample(segment, len(segment) * upsample_factor)

            # Redetect the peak in the upsampled segment
            #upsampled_peaks, _ = find_peaks(upsampled_segment, height=None)  # Add any other relevant parameters for peak detection

            # Find the closest upsampled peak to the center (original peak location)
            #upsampled_r_peak = upsampled_peaks[np.argmin(abs(upsampled_peaks - len(segment) * upsample_factor // 2))]
            upsampled_r_peak = np.argmax(upsampled_segment)

            # Map back to the original sampling rate
            accurate_r_peak_idx = int(start_idx + upsampled_r_peak // upsample_factor)

            peaks_indexes = np.append(peaks_indexes, accurate_r_peak_idx)

        return peaks_indexes.astype(int)
    

    def interpolate_peak(self, peak_index):
        from scipy.signal import resample

        upsample_factor = int(2000/self.signal_frequency)
        window_size = int(0.035*self.signal_frequency)

        # Define the window around the detected peak
        start_idx = max(0, peak_index - window_size)
        end_idx = min(len(self.filtered_ecg_measurements), peak_index + window_size)
        segment = self.filtered_ecg_measurements[start_idx:end_idx]

        # Upsample the segment
        original_indices = np.arange(len(segment))

        # Upsampling
        upsample_factor = int(2000/self.signal_frequency)  # Replace with your upsample factor
        new_length = len(segment) * upsample_factor
        new_indices = np.linspace(0, len(segment) - 1, new_length)

        # Linear interpolation
        upsampled_segment = np.interp(new_indices, original_indices, segment)
        #upsampled_segment = resample(segment, len(segment) * upsample_factor)

        upsampled_r_peak = np.argmax(upsampled_segment)
        upsampled_r_value = upsampled_segment[upsampled_r_peak]

        # Map back to the original sampling rate
        accurate_r_peak_idx = start_idx + upsampled_r_peak // upsample_factor

        #import matplotlib.pyplot as plt
        #plt.plot(upsampled_segment, label='Integrated Signal')

        # Mark the peaks
        #plt.plot(upsampled_r_peak, upsampled_segment[upsampled_r_peak], "x", label='Detected Peaks')

        # You can also highlight the peaks with a stem plot
        #plt.stem(upsampled_r_peak, upsampled_segment[upsampled_r_peak], linefmt="C2-", markerfmt="C2x", basefmt=" ")

        # Enhance the plot
        #plt.title('Integrated Signal with Detected Peaks')
        #plt.xlabel('Sample Number')
        #plt.ylabel('Signal Amplitude')
        #plt.legend()
        #plt.show()

        #plt.plot(segment, label='Integrated Signal')

        # Mark the peaks
        #plt.plot(accurate_r_peak_idx-start_idx, self.filtered_ecg_measurements[accurate_r_peak_idx], "x", label='Detected Peaks')

        # You can also highlight the peaks with a stem plot
        #plt.stem(accurate_r_peak_idx-start_idx, self.filtered_ecg_measurements[accurate_r_peak_idx], linefmt="C2-", markerfmt="C2x", basefmt=" ")

        # Enhance the plot
        #plt.title('Integrated Signal with Detected Peaks')
        #plt.xlabel('Sample Number')
        #plt.ylabel('Signal Amplitude')
        #plt.legend()
        #plt.show()
        return accurate_r_peak_idx+1, upsampled_r_value
    

    #@jit(nopython=True, cache=True)
    def downsample_ecg(ecg, new_length): # new_length is 100, len(ecg) is 1000

        # Calculate the downsampling factor
        downsampling_factor = len(ecg) / new_length

        # Create an array representing the new indices after downsampling
        new_indices = np.arange(new_length)

        # Calculate the corresponding indices in the original array
        original_indices = np.asarray(np.floor(new_indices * downsampling_factor))

        # Perform downsampling by taking values at the original indices
        #downsampled_array = ecg[original_indices]

        return original_indices
    
    #@jit(nopython=True, cache=True)
    def upsample_ecg(ecg, new_length):

        # Create an array representing the new indices after upsampling
        #new_indices = np.arange(new_length)

        new_ecg_indices = np.linspace(0, new_length-1, len(ecg))

        # Perform linear interpolation
        upsampled_array = np.interp(list(range(0, new_length)), new_ecg_indices, ecg)

        return upsampled_array
    
    def detect_low_ecg_noise(self, ecg_signal, fs, min_duration_ms=1000):
        """
        Annotates intervals with low values and finds start and end indices of these intervals in an ECG signal.

        Parameters:
        ecg_signal (numpy array): The ECG signal.
        fs (int): Sampling frequency of the ECG signal.
        low_threshold (float): Threshold for low values.
        min_duration_ms (int): Minimum duration in milliseconds for a low-value interval to be considered noise.

        Returns:
        List of tuples: Each tuple represents the start and end indices of low-value intervals.
        """
        low_threshold = np.median(ecg_signal)*0.1
        min_samples = (fs * min_duration_ms) // 1000
        low_intervals = np.zeros_like(ecg_signal)
        noise_intervals = []

        low_intervals[abs(ecg_signal) < low_threshold] = 1

        padded_arr = np.pad(low_intervals, (1, 1), 'constant', constant_values=0)
        diffs = np.diff(padded_arr)
        starts = np.where(diffs == 1)[0]
        ends = np.where(diffs == -1)[0]

        noise_intervals = [(start, end - 1) for start, end in zip(starts, ends) if end - start >= min_samples]

        return noise_intervals
    

    def detect_high_ecg_noise(self, ecg_signal, fs, peaks, multiplier=10, min_distance_ms=500):
        """
        Identifies intervals with high peaks as noise in an ECG signal.

        Parameters:
        ecg_signal (numpy array): The ECG signal.
        fs (int): Sampling frequency of the ECG signal.
        multiplier (float): Multiplier to determine the threshold based on the median of the peaks.
        min_distance_ms (int): Minimum distance in milliseconds to merge nearby high peak intervals.

        Returns:
        List of tuples: Each tuple represents the start and end indices of high peak noise intervals.
        """
        # Detect peaks
        peak_values = ecg_signal[peaks]
        peak_values = peak_values[peak_values > np.median(peak_values)]

        # Determine threshold
        threshold = np.median(peak_values) * multiplier

        # Find high peak intervals
        high_peaks = np.where(ecg_signal > threshold)[0]
        noise_intervals = []
        if len(high_peaks) > 0:
            start_idx = high_peaks[0]
            end_idx = high_peaks[0]
            for i in high_peaks[1:]:
                if i - end_idx <= (min_distance_ms * fs) // 1000:
                    end_idx = i
                else:
                    noise_intervals.append((start_idx, end_idx))
                    start_idx = i
                    end_idx = i
            noise_intervals.append((start_idx, end_idx))  # Append last interval

        return []


    #@jit(nopython=True, cache=True)
    def detect_peaks_midle(fs, filtered_ecg_measurements, integration_window, findpeaks_limit, findpeaks_spacing):
        
        # Derivative - provides QRS slope information.
        differentiated_ecg_measurements = np.ediff1d(filtered_ecg_measurements)

        # Squaring - intensifies values received in derivative.
        squared_ecg_measurements = differentiated_ecg_measurements ** 2

        # Moving-window integration.
        integrated_ecg_measurements = np.convolve(squared_ecg_measurements, np.ones(integration_window))
        
        len = integrated_ecg_measurements.size
        x = np.zeros(len + 2 * findpeaks_spacing)
        x[:findpeaks_spacing] = integrated_ecg_measurements[0] - 1.e-6
        x[-findpeaks_spacing:] = integrated_ecg_measurements[-1] - 1.e-6
        x[findpeaks_spacing:findpeaks_spacing + len] = integrated_ecg_measurements
        peak_candidate = np.zeros(len)
        peak_candidate[:] = 1.0
        for s in range(findpeaks_spacing):
            start = findpeaks_spacing - s - 1
            h_b = x[start: start + len]  # before
            start = findpeaks_spacing
            h_c = x[start: start + len]  # central
            start = findpeaks_spacing + s + 1
            h_a = x[start: start + len]  # after
            peak_candidate *= (h_c > h_b) & (h_c > h_a)

        detected_peaks_indices = np.argwhere(peak_candidate)

        return filtered_ecg_measurements, differentiated_ecg_measurements, squared_ecg_measurements, integrated_ecg_measurements, detected_peaks_indices
    

    def detect_peaks_midle_plus(fs, filtered_ecg_measurements, integration_window, findpeaks_limit, findpeaks_spacing):
        
        # Derivative - provides QRS slope information.
        differentiated_ecg_measurements = np.ediff1d(filtered_ecg_measurements)

        # Squaring - intensifies values received in derivative.
        squared_ecg_measurements = differentiated_ecg_measurements ** 2

        # 3. Smooth the signal using a 150 ms wide flat-top window function
        from scipy.signal import find_peaks, flattop
        window_width = int(0.150 * fs)  # 150ms window
        window = flattop(window_width, sym=False)
        smooth_signal = np.convolve(squared_ecg_measurements, window, mode='same') / sum(window)

        # 4. Apply moving window integration with a 150 ms wide window
        #integration_window_width = int(0.150 * fs)  # 150ms window
        #integration_window = np.ones(integration_window_width) / integration_window_width
        #integrated_signal = np.convolve(smooth_signal, integration_window, mode='same')
        integrated_signal = smooth_signal

        detected_peaks_indices, _ = find_peaks(integrated_signal, distance=0.231*fs)
        # plot to debug
        #import matplotlib.pyplot as plt
        #plt.plot(filtered_ecg_measurements, label='Integrated Signal')

        # Mark the peaks
        #plt.plot(detected_peaks_indices, integrated_signal[detected_peaks_indices], "x", label='Detected Peaks')

        # You can also highlight the peaks with a stem plot
        #plt.stem(detected_peaks_indices, integrated_signal[detected_peaks_indices], linefmt="C2-", markerfmt="C2x", basefmt=" ")

        # Enhance the plot
        #plt.title('Integrated Signal with Detected Peaks')
        #plt.xlabel('Sample Number')
        #plt.ylabel('Signal Amplitude')
        #plt.legend()
        #plt.show()

        return filtered_ecg_measurements, differentiated_ecg_measurements, squared_ecg_measurements, integrated_signal, detected_peaks_indices
    


    #@jit(nopython=True, cache=True)
    def detect_qrs(self, filtered_signal, detected_peaks_indices, detected_peaks_values, refractory_period, qrs_peak_filtering_factor, noise_peak_filtering_factor, qrs_noise_diff_weight, qrs_peaks_indices, threshold_value, qrs_peak_value, noise_peaks_indices, noise_peak_value, fs):
        """
        Method responsible for classifying detected ECG measurements peaks either as noise or as QRS complex (heart beat).
        """
        
        #threshold_value = np.max(filtered_signal[:2*fs]) / 3
        #qrs_peak_value = threshold_value
        #noise_peak_value = 0.5 * np.mean(np.abs(filtered_signal[:2*fs]))
        #threshold_value2 = noise_peak_value
        
        for detected_peak_index, detected_peaks_value in zip(detected_peaks_indices, detected_peaks_values):

            peak_index, peak_value = self.interpolate_peak(detected_peak_index)

            try:
                last_qrs_index = qrs_peaks_indices[-1]
            except:
                last_qrs_index = 0
            
            # After a valid QRS complex detection, there is a 200 ms refractory period before next one can be detected.
            if peak_index - last_qrs_index > fs*0.2 or not qrs_peaks_indices.size:
                # Peak must be classified either as a noise peak or a QRS peak.
                # To be classified as a QRS peak it must exceed dynamically set threshold value.
                if peak_value > threshold_value:
                    try:
                        previous_slope = np.mean((np.diff(filtered_signal[qrs_peaks_indices[-1]-int(0.07*fs):qrs_peaks_indices[-1]])))
                        current_slope = np.mean((np.diff(filtered_signal[peak_index-int(0.07*fs):peak_index])))
                        mean_rr = np.mean(np.diff(qrs_peaks_indices[-7:]))
                        if (peak_index - last_qrs_index < 0.36*fs or peak_index - last_qrs_index < 0.5*mean_rr) and current_slope < 0.6*previous_slope:
                            noise_peaks_indices = np.append(noise_peaks_indices, peak_index)
                            noise_peak_value = 0.125 * peak_value + 0.875 * noise_peak_value
                        else:
                            qrs_peaks_indices = np.append(qrs_peaks_indices, peak_index)
                            qrs_peak_value = 0.125 * peak_value + 0.875 * qrs_peak_value
                    except:
                        qrs_peaks_indices = np.append(qrs_peaks_indices, peak_index)
                        qrs_peak_value = 0.125 * peak_value + 0.875 * qrs_peak_value

                elif (len(qrs_peaks_indices)>2):
                    # check if r or t peak
                    previous_slope = np.mean((np.diff(filtered_signal[qrs_peaks_indices[-1]-int(0.07*fs):qrs_peaks_indices[-1]])))
                    current_slope = np.mean((np.diff(filtered_signal[peak_index-int(0.07*fs):peak_index])))
                    mean_rr = np.mean(np.diff(qrs_peaks_indices[-7:]))
                    if peak_index - last_qrs_index < 0.36*fs or peak_index - last_qrs_index < 0.5*mean_rr:
                        if current_slope < 0.6*previous_slope: # it is t wave
                            noise_peaks_indices = np.append(noise_peaks_indices, peak_index)

                            # Adjust noise peak value used later for setting QRS-noise threshold.
                            noise_peak_value = 0.125 * peak_value + 0.875 * noise_peak_value
                        else:
                            qrs_peaks_indices = np.append(qrs_peaks_indices, peak_index)

                            # Adjust QRS peak value used later for setting QRS-noise threshold.
                            qrs_peak_value = 0.125 * peak_value + 0.875 * qrs_peak_value
                    
                    # check if missed beat with low amplitude
                    elif (peak_index - last_qrs_index > 1*fs or peak_index - last_qrs_index > 1.66*mean_rr):
                        meansb = np.mean([filtered_signal[qrs_peaks_indices[-3]], filtered_signal[qrs_peaks_indices[-2]], filtered_signal[qrs_peaks_indices[-1]]])
                        threshold3 = 0.5*0.4*threshold_value + 0.5*meansb
                        window_values = filtered_signal[qrs_peaks_indices[-1]+int(fs*0.36):peak_index]
                        max_value_index = np.argmax(window_values)
                        if window_values[max_value_index] > threshold3:
                            index_value = max_value_index+qrs_peaks_indices[-1]+int(fs*0.36)
                            qrs_peaks_indices = np.append(qrs_peaks_indices, index_value)
                            # Adjust QRS peak value with rule 2
                            qrs_peak_value = 0.75 * peak_value + 0.25 * qrs_peak_value
                        else:
                            if (peak_index - last_qrs_index > 1.4*fs):
                                window_values = filtered_signal[qrs_peaks_indices[-1]+int(fs*0.36):peak_index]
                                max_value_index = np.argmax(window_values)
                                if (window_values[max_value_index] > 0.2*threshold_value2):
                                    index_value = max_value_index+qrs_peaks_indices[-1]+int(fs*0.36)
                                    qrs_peaks_indices = np.append(qrs_peaks_indices, index_value)
                                    # Adjust QRS peak value with rule 2
                                    qrs_peak_value = 0.75 * peak_value + 0.25 * qrs_peak_value
                                else:
                                    noise_peaks_indices = np.append(noise_peaks_indices, max_value_index+qrs_peaks_indices[-1]+int(fs*0.36))
                                    noise_peak_value = 0.75 * peak_value + 0.25 * noise_peak_value

                    # check if miss beat after very high peak
                    elif (peak_index - last_qrs_index > 1.4*fs):
                        window_values = filtered_signal[qrs_peaks_indices[-1]+int(fs*0.36):peak_index]
                        max_value_index = np.argmax(window_values)
                        if (window_values[max_value_index] > 0.2*threshold_value2):
                            index_value = max_value_index+qrs_peaks_indices[-1]+int(fs*0.36)
                            qrs_peaks_indices = np.append(qrs_peaks_indices, index_value)
                            # Adjust QRS peak value with rule 2
                            qrs_peak_value = 0.75 * peak_value + 0.25 * qrs_peak_value
                        else:
                            noise_peaks_indices = np.append(noise_peaks_indices, max_value_index+qrs_peaks_indices[-1]+int(fs*0.36))
                            noise_peak_value = 0.75 * peak_value + 0.25 * noise_peak_value
                    else:
                        noise_peaks_indices = np.append(noise_peaks_indices, peak_index)

                        # Adjust noise peak value used later for setting QRS-noise threshold.
                        noise_peak_value = 0.75 * peak_value + 0.25 * noise_peak_value

                else:
                    if (peak_index - last_qrs_index > 1.4*fs):
                        window_values = filtered_signal[last_qrs_index+int(fs*0.36):peak_index]
                        max_value_index = np.argmax(window_values)
                        if (window_values[max_value_index] > 0.2*threshold_value2):
                            index_value = max_value_index+last_qrs_index+int(fs*0.36)
                            qrs_peaks_indices = np.append(qrs_peaks_indices, index_value)
                            # Adjust QRS peak value with rule 2
                            qrs_peak_value = 0.75 * peak_value + 0.25 * qrs_peak_value
                        else:
                            noise_peaks_indices = np.append(noise_peaks_indices, max_value_index+last_qrs_index+int(fs*0.36))
                            noise_peak_value = 0.75 * peak_value + 0.25 * noise_peak_value
                    else:
                        noise_peaks_indices = np.append(noise_peaks_indices, peak_index)

                        # Adjust noise peak value used later for setting QRS-noise threshold.
                        noise_peak_value = 0.75 * peak_value + 0.25 * noise_peak_value

            # Adjust QRS-noise threshold value based on previously detected QRS or noise peaks value.
            threshold_value = noise_peak_value + 0.25 * (qrs_peak_value - noise_peak_value)
            threshold_value2 = 0.4*threshold_value

        return detected_peaks_indices, detected_peaks_values, qrs_peaks_indices, qrs_peak_value, noise_peaks_indices, noise_peak_value, threshold_value
    

    

    def detect_qrs_plus(self, filtered_signal, fs, detected_peaks_indices, detected_peaks_values, refractory_period, qrs_peak_filtering_factor, noise_peak_filtering_factor, qrs_noise_diff_weight, qrs_peaks_indices, threshold_value, qrs_peak_value, noise_peaks_indices, noise_peak_value):
        """
        Method responsible for classifying detected ECG measurements peaks either as noise or as QRS complex (heart beat).
        """

        # initialize values
        threshold1 = np.max(np.abs(filtered_signal[0:int(2*fs)]))/3
        threshold2 = np.mean(np.abs(filtered_signal[0:int(2*fs)]))/2
        spk = threshold1
        npk = threshold2
        
        for i, (detected_peak_index, detected_peaks_value) in enumerate(zip(detected_peaks_indices, detected_peaks_values)):

            if detected_peaks_value > threshold1:
                # peak candidate
                qrs_peaks_indices = np.append(qrs_peaks_indices, detected_peak_index)
                qrs_peak_value = np.append(qrs_peak_value, detected_peaks_value)
                spk, npk = update_thresholds_rule1(spk, npk, detected_peaks_value)
            
            elif len(qrs_peaks_indices) > 0:
                mean_rr = np.mean(np.diff(qrs_peaks_indices[-8:-1]))/fs
                current_rr = (detected_peak_index - qrs_peaks_indices[-1])/fs
                if (current_rr < 0.36 or current_rr < (0.5*mean_rr)):
                    #classify it as T-wave or QRS complex based on slope Adjust SPK and NPK using Rule-1, if QRS complex found
                    previous_slope = np.mean(np.diff(filtered_signal[qrs_peaks_indices[-1]-int(0.070*fs):qrs_peaks_indices[-1]]))
                    current_slope = np.mean(np.diff(filtered_signal[detected_peak_index-int(0.070*fs):detected_peak_index]))
                    if current_slope < 0.6*previous_slope:
                        noise_peaks_indices = np.append(noise_peaks_indices, detected_peak_index) # t wave
                        noise_peak_value = np.append(noise_peak_value, detected_peaks_value)
                    else:
                        qrs_peaks_indices = np.append(qrs_peaks_indices, detected_peak_index)
                        qrs_peak_value = np.append(qrs_peak_value, detected_peaks_value)
                        spk, npk = update_thresholds_rule1(spk, npk, detected_peaks_value)
                elif (current_rr > 1 or current_rr > (1.66*mean_rr)):
                    MEANSB = np.mean(np.diff(qrs_peaks_indices[-4:-1]))/fs # not sure: MEANSB is a window with the preceding 3 QRS complexes and the following 3 peaks.
                    threshold3 = 0.5*threshold2 + 0.5*MEANSB
                    if detected_peaks_value > threshold3:
                        qrs_peaks_indices = np.append(qrs_peaks_indices, detected_peak_index)
                        qrs_peak_value = np.append(qrs_peak_value, detected_peaks_value)
                        spk, npk = update_thresholds_rule2(spk, npk, detected_peaks_value)
                elif (current_rr > 1.4):
                    if (detected_peaks_value > 0.2*threshold2):
                        qrs_peaks_indices = np.append(qrs_peaks_indices, detected_peak_index)
                        qrs_peak_value = np.append(qrs_peak_value, detected_peaks_value)
                        spk, npk = update_thresholds_rule2(spk, npk, detected_peaks_value)

            threshold1 = npk + 0.25*(spk-npk)
            threshold2 = 0.4 * threshold1
            

        return detected_peaks_indices, detected_peaks_values, qrs_peaks_indices, qrs_peak_value, noise_peaks_indices, noise_peak_value, threshold_value


    """Results reporting methods."""

    def print_detection_data(self):
        """
        Method responsible for printing the results.
        """
        print("qrs peaks indices")
        print(self.qrs_peaks_indices)
        print("noise peaks indices")
        print(self.noise_peaks_indices)

    def log_detection_data(self):
        """
        Method responsible for logging measured ECG and detection results to a file.
        """
        with open(self.log_path, "wb") as fin:
            fin.write(b"timestamp,ecg_measurement,qrs_detected\n")
            np.savetxt(fin, self.ecg_data_detected, delimiter=",")

    def plot_detection_data(self, show_plot=False):
        """
        Method responsible for plotting detection results.
        :param bool show_plot: flag for plotting the results and showing plot
        """
        print("plotting offline")

        def plot_data(axis, data, title='', fontsize=10):
            axis.set_title(title, fontsize=fontsize)
            axis.grid(which='both', axis='both', linestyle='--')
            axis.plot(data, color="salmon", zorder=1)

        def plot_points(axis, values, indices):
            axis.scatter(x=indices, y=values[indices], c="black", s=50, zorder=2)

        plt.close('all')
        fig, axarr = plt.subplots(6, sharex=True, figsize=(15, 18))

        plot_data(axis=axarr[0], data=self.ecg_data_raw, title='Raw ECG measurements')
        plot_data(axis=axarr[1], data=self.filtered_ecg_measurements, title='Filtered ECG measurements')
        plot_data(axis=axarr[2], data=self.differentiated_ecg_measurements, title='Differentiated ECG measurements')
        plot_data(axis=axarr[3], data=self.squared_ecg_measurements, title='Squared ECG measurements')
        plot_data(axis=axarr[4], data=self.integrated_ecg_measurements, title='Integrated ECG measurements with QRS peaks marked (black)')
        plot_points(axis=axarr[4], values=self.integrated_ecg_measurements, indices=self.qrs_peaks_indices)
        #plot_data(axis=axarr[5], data=self.ecg_data_detected[:, 1], title='Raw ECG measurements with QRS peaks marked (black)')
        #plot_points(axis=axarr[5], values=self.ecg_data_detected[:, 1], indices=self.qrs_peaks_indices)

        #plt.tight_layout()
        #fig.savefig(self.plot_path)
        
        if show_plot:
            plt.show()

        #plt.close()

    """Tools methods."""

    def bandpass_filter(self, data, lowcut, highcut, signal_freq, filter_order):
        """
        Method responsible for creating and applying Butterworth filter.
        :param deque data: raw data
        :param float lowcut: filter lowcut frequency value
        :param float highcut: filter highcut frequency value
        :param int signal_freq: signal frequency in samples per second (Hz)
        :param int filter_order: filter order
        :return array: filtered data
        """
        nyquist_freq = 0.5 * signal_freq
        low = lowcut / nyquist_freq
        high = highcut / nyquist_freq
        if low == 0:
            b, a = butter(filter_order, [high], btype="low")
        else:
            b, a = butter(filter_order, [low, high], btype="band")
        y = lfilter(b, a, data)
        return y
    #@jit
    def findpeaks(self, data, spacing=1, limit=None):
        """
        Janko Slavic peak detection algorithm and implementation.
        https://github.com/jankoslavic/py-tools/tree/master/findpeaks
        Finds peaks in `data` which are of `spacing` width and >=`limit`.
        :param ndarray data: data
        :param float spacing: minimum spacing to the next peak (should be 1 or more)
        :param float limit: peaks should have value greater or equal
        :return array: detected peaks indexes array
        """
        len = data.size
        x = np.zeros(len + 2 * spacing)
        x[:spacing] = data[0] - 1.e-6
        x[-spacing:] = data[-1] - 1.e-6
        x[spacing:spacing + len] = data
        peak_candidate = np.zeros(len)
        peak_candidate[:] = True
        for s in range(spacing):
            start = spacing - s - 1
            h_b = x[start: start + len]  # before
            start = spacing
            h_c = x[start: start + len]  # central
            start = spacing + s + 1
            h_a = x[start: start + len]  # after
            peak_candidate = np.logical_and(peak_candidate, np.logical_and(h_c > h_b, h_c > h_a))

        ind = np.argwhere(peak_candidate)
        ind = ind.reshape(ind.size)
        if limit is not None:
            ind = ind[data[ind] > limit]
        return ind


# Helper function to update thresholds
def update_thresholds_rule1(spk, npk, value):
    spk = 0.125 * value + 0.875 * spk
    npk = 0.125 * value + 0.875 * npk
    return spk, npk

# Helper function to update thresholds
def update_thresholds_rule2(spk, npk, value):
    spk = 0.75 * value + 0.25 * spk
    npk = 0.75 * value + 0.25 * npk
    return spk, npk

def plot_data(axis, data, title, points_to_mark):
    axis.plot(data, label='ECG')
    axis.set_title(title)

    # Extract y-coordinates of points to mark from the data
    y_coordinates = [data[i] for i in points_to_mark]

    # Plot the marked points
    axis.plot(points_to_mark, y_coordinates, 'ro', markersize=5, label='Marked Points')  # 'ro' = red circle markers
    axis.legend()

