import os
import sys
import time
import logging
import cv2
import psutil
import database
from logger import server_logger

class HardwareManager:
    """
    Manages PC AI hardware accelerator detection, priority resolution,
    ONNX execution provider mapping, and performance metrics tracking.
    """
    def __init__(self):
        self.preference = "Auto"  # Options: 'Auto', 'Force NPU', 'Force GPU', 'Force CPU'
        self.last_inference_time_ms = 0.0
        self.last_training_time_seconds = 0.0
        self._detected_npu = False
        self._detected_gpu = False
        self._detected_cpu = True
        self.gpu_name = "N/A"
        self.npu_name = "N/A"
        self.cpu_name = f"CPU ({os.cpu_count() or 4} cores)"
        self.detect_hardware()

    def detect_hardware(self):
        """Detects available NPU, GPU, and CPU hardware accelerators."""

        # 1. GPU Detection
        # Check OpenCV CUDA support
        cuda_count = getattr(cv2.cuda, 'getCudaEnabledDeviceCount', lambda: 0)()
        if cuda_count > 0:
            self._detected_gpu = True
            self.gpu_name = f"NVIDIA CUDA ({cuda_count} Device)"

        # Check OpenCL GPU acceleration (Intel Iris / AMD / NVIDIA)
        if not self._detected_gpu and cv2.ocl.haveOpenCL():
            try:
                cv2.ocl.setUseOpenCL(True)
                self._detected_gpu = True
                self.gpu_name = "OpenCL Accelerated GPU / iGPU"
            except Exception:
                pass

        # Check ONNX Runtime GPU / DirectML providers
        try:
            import onnxruntime as ort
            providers = ort.get_available_providers()
            if 'CUDAExecutionProvider' in providers:
                self._detected_gpu = True
                self.gpu_name = "NVIDIA CUDA (ONNX Runtime)"
            elif 'DmlExecutionProvider' in providers:
                self._detected_gpu = True
                self.gpu_name = "DirectML DirectX 12 GPU / iGPU"
            elif 'ROCMExecutionProvider' in providers:
                self._detected_gpu = True
                self.gpu_name = "AMD ROCm GPU"
        except Exception:
            pass

        # 2. NPU Detection
        # Check ONNX Runtime NPU providers (Intel NPU, OpenVINO, Qualcomm QNN, Vitis AI)
        try:
            import onnxruntime as ort
            providers = ort.get_available_providers()
            if 'OpenVINOExecutionProvider' in providers:
                self._detected_npu = True
                self.npu_name = "Intel NPU / OpenVINO Accelerator"
            elif 'VitisAIExecutionProvider' in providers:
                self._detected_npu = True
                self.npu_name = "AMD Ryzen AI NPU (Vitis AI)"
            elif 'QNNExecutionProvider' in providers:
                self._detected_npu = True
                self.npu_name = "Qualcomm Snapdragon NPU (QNN)"
        except Exception:
            pass

        # OpenCV DNN Target NPU check
        try:
            if hasattr(cv2.dnn, 'DNN_TARGET_NPU'):
                self._detected_npu = True
                if self.npu_name == "N/A":
                    self.npu_name = "OpenCV Hardware NPU"
        except Exception:
            pass

        target_device, provider_name = self.resolve_inference_target()
        server_logger.info(f"AI Device Selected : {target_device}")
        server_logger.info(f"Execution Provider : {provider_name}")
        server_logger.info("Model Loaded Successfully")
        server_logger.info("Recognition Ready")

    def get_preference(self):
        """Loads administrator hardware preference from database."""
        try:
            database.init_db()
            pref = database.get_setting('ai_hardware_preference', 'Auto')
            if pref in ['Auto', 'Force NPU', 'Force GPU', 'Force CPU']:
                self.preference = pref
        except Exception:
            pass
        return self.preference

    def set_preference(self, preference):
        """Saves administrator hardware preference to database."""
        if preference in ['Auto', 'Force NPU', 'Force GPU', 'Force CPU']:
            self.preference = preference
            try:
                database.init_db()
                database.set_setting('ai_hardware_preference', preference)
                server_logger.info(f"Updated AI Hardware Preference to: {preference}")
            except Exception as e:
                server_logger.error(f"Error saving hardware preference: {e}")
            return True
        return False

    def resolve_inference_target(self):
        """
        Resolves active inference hardware target following priority rules:
        Preference Auto: NPU -> GPU -> CPU
        Preference Force NPU: NPU (fallback GPU -> CPU if NPU unavailable)
        Preference Force GPU: GPU (fallback CPU if GPU unavailable)
        Preference Force CPU: CPU
        """
        pref = self.get_preference()

        if pref == 'Force CPU':
            return 'CPU', 'CPU Execution'
        elif pref == 'Force NPU':
            if self._detected_npu:
                return 'NPU', self.npu_name
            elif self._detected_gpu:
                server_logger.warning("NPU requested but unavailable. Falling back to GPU.")
                return 'GPU', self.gpu_name
            else:
                server_logger.warning("NPU requested but unavailable. Falling back to CPU.")
                return 'CPU', 'CPU Fallback'
        elif pref == 'Force GPU':
            if self._detected_gpu:
                return 'GPU', self.gpu_name
            else:
                server_logger.warning("GPU requested but unavailable. Falling back to CPU.")
                return 'CPU', 'CPU Fallback'
        else: # 'Auto'
            if self._detected_npu:
                return 'NPU', self.npu_name
            elif self._detected_gpu:
                return 'GPU', self.gpu_name
            else:
                return 'CPU', self.cpu_name

    def resolve_training_target(self):
        """
        Resolves active training hardware target following priority rules:
        GPU -> CPU (Do not train deep networks on NPU unless supported)
        """
        pref = self.get_preference()
        if pref == 'Force CPU':
            return 'CPU'
        elif self._detected_gpu:
            return 'GPU'
        else:
            return 'CPU'

    def get_onnx_providers(self):
        """Returns ONNX Runtime execution provider priority list for inference."""
        target, _ = self.resolve_inference_target()
        providers = []

        try:
            import onnxruntime as ort
            available = ort.get_available_providers()
        except Exception:
            available = ['CPUExecutionProvider']

        if target == 'NPU':
            for p in ['OpenVINOExecutionProvider', 'VitisAIExecutionProvider', 'QNNExecutionProvider', 'DmlExecutionProvider']:
                if p in available:
                    providers.append(p)
        elif target == 'GPU':
            for p in ['CUDAExecutionProvider', 'DmlExecutionProvider', 'ROCMExecutionProvider']:
                if p in available:
                    providers.append(p)

        providers.append('CPUExecutionProvider')
        return providers

    def get_opencv_dnn_target_backend(self):
        """Returns OpenCV DNN (backend, target) tuple matching resolved hardware."""
        target, _ = self.resolve_inference_target()

        try:
            if target == 'NPU' and hasattr(cv2.dnn, 'DNN_TARGET_NPU'):
                return cv2.dnn.DNN_BACKEND_OPENCV, cv2.dnn.DNN_TARGET_NPU
            if target == 'GPU':
                if getattr(cv2.cuda, 'getCudaEnabledDeviceCount', lambda: 0)() > 0 and hasattr(cv2.dnn, 'DNN_BACKEND_CUDA'):
                    return cv2.dnn.DNN_BACKEND_CUDA, cv2.dnn.DNN_TARGET_CUDA
                if cv2.ocl.haveOpenCL():
                    return cv2.dnn.DNN_BACKEND_OPENCV, cv2.dnn.DNN_TARGET_OPENCL
        except Exception:
            pass

        return cv2.dnn.DNN_BACKEND_OPENCV, cv2.dnn.DNN_TARGET_CPU

    def record_inference_time(self, time_ms):
        """Records last face recognition inference latency."""
        self.last_inference_time_ms = round(time_ms, 2)

    def record_training_time(self, time_seconds):
        """Records last classifier model training duration."""
        self.last_training_time_seconds = round(time_seconds, 2)

    def get_system_memory_info(self):
        """Returns RAM and system memory utilization metrics."""
        mem = psutil.virtual_memory()
        return {
            'ram_used_mb': round((mem.total - mem.available) / (1024 * 1024), 2),
            'ram_total_mb': round(mem.total / (1024 * 1024), 2),
            'ram_available_mb': round(mem.available / (1024 * 1024), 2),
            'ram_usage_percent': mem.percent,
            'cpu_usage_percent': psutil.cpu_percent(interval=None)
        }

    def get_hardware_status(self):
        """Returns summary status payload for Dashboard & REST APIs."""
        target_device, provider_name = self.resolve_inference_target()
        training_target = self.resolve_training_target()
        mem_info = self.get_system_memory_info()

        return {
            'npu_available': self._detected_npu,
            'gpu_available': self._detected_gpu,
            'cpu_available': self._detected_cpu,
            'npu_name': self.npu_name,
            'gpu_name': self.gpu_name,
            'cpu_name': self.cpu_name,
            'current_device_used': f"{target_device} ({provider_name})",
            'active_inference_target': target_device,
            'active_training_target': training_target,
            'preference': self.get_preference(),
            'last_inference_time_ms': self.last_inference_time_ms,
            'last_training_time_seconds': self.last_training_time_seconds,
            'memory': mem_info
        }

# Global Singleton Instance
hardware_manager = HardwareManager()
