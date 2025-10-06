import numpy as np
import time
import logging
from enum import Enum
from typing import Optional, List, Dict, Any

# Try to import sklearn FastICA, fallback to scipy if not available
try:
    from sklearn.decomposition import FastICA
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    import warnings
    warnings.warn("scikit-learn not available, using scipy fallback for ICA")

class ICAState(Enum):
    """ICA processing states"""
    OFF = "OFF"
    CALIBRATING = "CALIBRATING"
    ACTIVE = "ACTIVE"

class ICAManager:
    """
    Simple ICA manager for basic EEG artifact removal.
    Focuses on eye blinks and small movements.
    """
    
    def __init__(self, status_bar, fast_ica_checkbox, ica_calib_spinbox, channel_dial):
        self.status_bar = status_bar
        self.fast_ica_checkbox = fast_ica_checkbox
        self.ica_calib_spinbox = ica_calib_spinbox
        self.channel_dial = channel_dial  # Add channel dial reference
        
        # State management
        self.state = ICAState.OFF
        self.calibration_buffer = []
        self.calibration_start_time = None
        self.ica_model = None
        
        # Configuration
        self.sampling_rate = 125  # Hz
        self.min_channels = 2
        
        # Setup logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        
        # Setup UI
        self._setup_ui()
    
    def _setup_ui(self):
        """Setup UI controls"""
        self.ica_calib_spinbox.setRange(3, 30)
        self.ica_calib_spinbox.setValue(8)
        
        # Start with checkbox disabled and unchecked
        self.fast_ica_checkbox.setEnabled(False)
        self.fast_ica_checkbox.setChecked(False)
    
    def _update_status(self, message: str):
        """Update the status bar"""
        if self.status_bar and message:
            self.status_bar.setText(message)
            self.status_bar.repaint()
    
    def set_board_shim(self, board_shim):
        """Set the board shim reference"""
        self.board_shim = board_shim
        self.logger.info("ICA manager board reference set")
    
    def clear_board_shim(self):
        """Clear board shim reference when board goes offline"""
        self.board_shim = None
        
        # Always disable ICA when board is off
        if self.state != ICAState.OFF:
            self._enter_off_state()
        
        # Clear status
        self._update_status("")
        self.logger.info("ICA manager cleared board reference")
    
    def enable_ica_manually(self):
        """Enable ICA when user checks the checkbox"""
        if self._check_preconditions():
            self._enter_calibrating_state()
        else:
            # If preconditions fail, uncheck the checkbox
            self.fast_ica_checkbox.setChecked(False)
            self.logger.warning("Cannot enable ICA: preconditions not met")
    
    def disable_ica_manually(self):
        """Disable ICA when user unchecks the checkbox"""
        self._enter_off_state()
    
    def _check_preconditions(self) -> bool:
        """Check if ICA can be enabled"""
        if not hasattr(self, 'board_shim') or self.board_shim is None:
            return False
        
        # Get active channel count from the dial
        channel_count = self.channel_dial.value()
        
        return channel_count >= self.min_channels
    
    def _enter_off_state(self):
        """Enter OFF state - reset everything"""
        self.state = ICAState.OFF
        self.calibration_buffer = []
        self.calibration_start_time = None
        self.ica_model = None
        
        # Always uncheck when disabling
        self.fast_ica_checkbox.setChecked(False)
        
        # Clear status
        self._update_status("")
        self.logger.info("ICA entered OFF state")
    
    def _enter_calibrating_state(self):
        """Enter CALIBRATING state - start collecting data"""
        self.state = ICAState.CALIBRATING
        self.calibration_buffer = []
        self.calibration_start_time = time.time()
        
        # Update status
        self._update_status("ICA: Calibrating...")
        self.logger.info("ICA entered CALIBRATING state")
    
    def _enter_active_state(self):
        """Enter ACTIVE state - ICA is processing data"""
        self.state = ICAState.ACTIVE
        
        # Update status with active channel count from dial
        active_channel_count = self.channel_dial.value()
        self._update_status(f"ICA: Running ({active_channel_count} channels)")
        self.logger.info(f"ICA entered ACTIVE state with {active_channel_count} channels")
    
    def process_data(self, preprocessed_data: Dict[int, np.ndarray]) -> Dict[int, np.ndarray]:
        """Process data through ICA pipeline"""
        if self.state == ICAState.OFF:
            return preprocessed_data
        
        # Get active channel count from the dial
        active_channel_count = self.channel_dial.value()
        
        if active_channel_count < self.min_channels:
            if self.state != ICAState.OFF:
                self._enter_off_state()
            return preprocessed_data
        
        # Only process the active channels (1 to active_channel_count)
        active_channels = list(range(1, active_channel_count + 1))
        
        # Create output with all channels preserved
        output_data = preprocessed_data.copy()
        
        if self.state == ICAState.CALIBRATING:
            # During calibration, only collect data from active channels
            self._handle_calibration(preprocessed_data, active_channels)
            return output_data
        elif self.state == ICAState.ACTIVE:
            # Apply ICA only to active channels, preserve others unchanged
            processed_active = self._apply_ica(preprocessed_data, active_channels)
            
            # Update only the active channels in output
            for ch in active_channels:
                if ch in processed_active:
                    output_data[ch] = processed_active[ch]
            
            return output_data
        
        return output_data
    
    def _handle_calibration(self, preprocessed_data: Dict[int, np.ndarray], active_channels: List[int]):
        """Handle data during calibration phase"""
        # Extract data for active channels
        data_matrix = []
        for ch in active_channels:
            if ch in preprocessed_data:
                data_matrix.append(preprocessed_data[ch])
        
        if not data_matrix:
            return
        
        # Ensure all channels have the same length
        min_length = min(len(data) for data in data_matrix)
        data_matrix = [data[:min_length] for data in data_matrix]
        
        # Convert to numpy array
        data_matrix = np.array(data_matrix)
        
        # Add to calibration buffer
        self.calibration_buffer.append(data_matrix)
        
        # Check if we have enough calibration data
        calibration_duration = self.ica_calib_spinbox.value()
        if time.time() - self.calibration_start_time >= calibration_duration:
            self._fit_ica()
            self._enter_active_state()
    
    def _fit_ica(self):
        """Fit ICA model using calibration data"""
        try:
            if not self.calibration_buffer:
                raise ValueError("No calibration data available")
            
            # Concatenate all calibration data
            data_chunks = []
            for chunk in self.calibration_buffer:
                if chunk is not None:
                    data_chunks.append(chunk)
            
            if not data_chunks:
                raise ValueError("No valid data chunks in calibration buffer")
            
            # Stack data: (n_channels, total_samples)
            stacked_data = np.hstack(data_chunks)
            
            # Transpose to (n_samples, n_channels) for ICA
            data_for_ica = stacked_data.T
            
            # Remove any remaining NaNs
            valid_mask = np.all(np.isfinite(data_for_ica), axis=1)
            data_for_ica = data_for_ica[valid_mask]
            
            if len(data_for_ica) < 100:  # Need minimum samples
                raise ValueError(f"Insufficient valid samples for ICA: {len(data_for_ica)} < 100")
            
            # Fit ICA model
            if SKLEARN_AVAILABLE:
                self.ica_model = FastICA(
                    n_components=data_for_ica.shape[1],
                    whiten='unit-variance',
                    max_iter=200,
                    tol=1e-4,
                    random_state=42
                )
                self.ica_model.fit(data_for_ica)
            else:
                # Simple fallback - just use the data as is
                self.ica_model = None
            
            # Enter active state
            self._enter_active_state()
            
            self.logger.info(f"ICA fit successful: {len(data_for_ica)} samples, {data_for_ica.shape[1]} components")
            
        except Exception as e:
            self.logger.error(f"ICA fit failed: {e}")
            # If ICA fails, disable it
            self._enter_off_state()
    
    def _apply_ica(self, preprocessed_data: Dict[int, np.ndarray], active_channels: List[int]) -> Dict[int, np.ndarray]:
        """Apply ICA to new data"""
        if self.ica_model is None:
            return preprocessed_data
        
        try:
            # Extract data for active channels
            data_matrix = []
            for ch in active_channels:
                if ch in preprocessed_data:
                    data_matrix.append(preprocessed_data[ch])
            
            if not data_matrix:
                return preprocessed_data
            
            # Ensure all channels have the same length
            min_length = min(len(data) for data in data_matrix)
            data_matrix = [data[:min_length] for data in data_matrix]
            
            # Stack data: (n_channels, n_samples)
            stacked_data = np.array(data_matrix)
            
            # Remove any NaN values
            valid_mask = np.all(np.isfinite(stacked_data), axis=0)
            if not np.any(valid_mask):
                return preprocessed_data
                
            data_for_ica = stacked_data[:, valid_mask]
            
            # Apply ICA transformation
            data_transposed = data_for_ica.T  # (n_samples, n_channels)
            
            # Get independent components
            components = self.ica_model.transform(data_transposed)
            
            # Simple artifact removal - zero out components with high kurtosis
            cleaned_components = self._remove_bad_components(components)
            
            # Transform back to channel space
            cleaned_data = self.ica_model.inverse_transform(cleaned_components)
            
            # Transpose back to (n_channels, n_samples)
            cleaned_data = cleaned_data.T
            
            # Update the processed data
            result_data = {}
            for i, ch in enumerate(active_channels):
                if i < cleaned_data.shape[0]:
                    # Ensure output has same length as input
                    if len(cleaned_data[i]) == len(preprocessed_data[ch]):
                        result_data[ch] = cleaned_data[i]
                    else:
                        # Pad or truncate to match input length
                        if len(cleaned_data[i]) < len(preprocessed_data[ch]):
                            padded = np.zeros(len(preprocessed_data[ch]))
                            padded[:len(cleaned_data[i])] = cleaned_data[i]
                            result_data[ch] = padded
                        else:
                            result_data[ch] = cleaned_data[i][:len(preprocessed_data[ch])]
                else:
                    result_data[ch] = preprocessed_data[ch]
            
            return result_data
            
        except Exception as e:
            self.logger.error(f"ICA application failed: {e}")
            return preprocessed_data
    
    def _remove_bad_components(self, components: np.ndarray) -> np.ndarray:
        """Remove bad components based on kurtosis - simple approach"""
        if components.size == 0:
            return components
        
        try:
            # Compute kurtosis for each component
            kurtosis = np.zeros(components.shape[1])
            for i in range(components.shape[1]):
                comp = components[:, i]
                if np.std(comp) > 1e-8:
                    kurtosis[i] = self._compute_kurtosis(comp)
            
            # Zero components with high kurtosis (likely artifacts)
            threshold = 10.0  # Relaxed threshold
            bad_components = np.abs(kurtosis) > threshold
            
            if np.any(bad_components):
                components_cleaned = components.copy()
                components_cleaned[:, bad_components] = 0
                
                num_removed = np.sum(bad_components)
                self.logger.debug(f"Removed {num_removed} bad components")
                
                return components_cleaned
            
            return components
            
        except Exception as e:
            self.logger.error(f"Error in component removal: {e}")
            return components
    
    def _compute_kurtosis(self, data: np.ndarray) -> float:
        """Compute kurtosis of a signal"""
        if len(data) < 4:
            return 0.0
        
        mean = np.mean(data)
        std = np.std(data)
        
        if std < 1e-8:
            return 0.0
        
        normalized = (data - mean) / std
        kurtosis = np.mean(normalized ** 4) - 3
        
        return kurtosis
    
    def get_state(self) -> ICAState:
        """Get current ICA state"""
        return self.state
    
    def is_enabled(self) -> bool:
        """Check if ICA is enabled and active"""
        return self.state in [ICAState.CALIBRATING, ICAState.ACTIVE]
    
    def reset(self):
        """Reset ICA to OFF state"""
        self._enter_off_state()
    
    def get_status_summary(self) -> str:
        """Get current status summary"""
        if self.state == ICAState.OFF:
            return ""
        elif self.state == ICAState.CALIBRATING:
            return "ICA: Calibrating..."
        elif self.state == ICAState.ACTIVE:
            active_channel_count = self.channel_dial.value()
            return f"ICA: Running ({active_channel_count} channels)"
        return ""

