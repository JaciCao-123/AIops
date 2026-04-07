import pytest
import pandas as pd
import numpy as np
import json
import tempfile
import shutil
from datetime import datetime, timedelta
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from base.config import Config
from base.detector import BaseDetector
from auth_logs.detector import AuthDetector
from cloud_logs.detector import CloudDetector
from app_server_logs.detector import AppServerDetector
from ssh_logs.detector import SSHDetector
from correlation_engine.engine import CorrelationEngine


class TestConfig:
    def test_config_singleton(self):
        config1 = Config()
        config2 = Config()
        assert config1 is config2
    
    def test_config_properties(self):
        config = Config()
        assert config.auth is not None
        assert config.cloud is not None
        assert config.app_server is not None
        assert config.ssh is not None
        assert config.correlation is not None
    
    def test_config_get_method(self):
        config = Config()
        value = config.get("detection.auth.anomaly_day", 25)
        assert isinstance(value, int)


class TestAuthDetector:
    @pytest.fixture
    def temp_dir(self):
        temp = tempfile.mkdtemp()
        yield temp
        shutil.rmtree(temp)
    
    @pytest.fixture
    def auth_detector(self, temp_dir):
        return AuthDetector(base_dir=temp_dir)
    
    def test_generate_data(self, auth_detector):
        result = auth_detector.generate_data()
        assert result is True
        
        output_path = auth_detector.raw_data_dir / "auth_failures.csv"
        assert output_path.exists()
        
        df = pd.read_csv(output_path)
        assert 'timestamp' in df.columns
        assert 'username' in df.columns
        assert 'application' in df.columns
        assert 'source_ip' in df.columns
        assert 'failure_type' in df.columns
    
    def test_clean_data(self, auth_detector):
        auth_detector.generate_data()
        
        result = auth_detector.clean_data()
        assert result is True
        
        output_path = auth_detector.cleaned_data_dir / "auth_failures_minutely.csv"
        assert output_path.exists()
        
        df = pd.read_csv(output_path)
        assert 'ds' in df.columns
        assert 'y' in df.columns
    
    def test_full_pipeline(self, auth_detector):
        result = auth_detector.run_pipeline()
        assert result is True
        
        model_path = auth_detector.model_dir / "prophet_auth_model.pkl"
        assert model_path.exists()


class TestCloudDetector:
    @pytest.fixture
    def temp_dir(self):
        temp = tempfile.mkdtemp()
        yield temp
        shutil.rmtree(temp)
    
    @pytest.fixture
    def cloud_detector(self, temp_dir):
        return CloudDetector(base_dir=temp_dir)
    
    def test_generate_data(self, cloud_detector):
        result = cloud_detector.generate_data()
        assert result is True
        
        output_path = cloud_detector.raw_data_dir / "cloud_api_calls.csv"
        assert output_path.exists()
        
        df = pd.read_csv(output_path)
        assert 'timestamp' in df.columns
        assert 'user' in df.columns
        assert 'action' in df.columns
        assert 'source_ip' in df.columns
    
    def test_full_pipeline(self, cloud_detector):
        result = cloud_detector.run_pipeline()
        assert result is True


class TestAppServerDetector:
    @pytest.fixture
    def temp_dir(self):
        temp = tempfile.mkdtemp()
        yield temp
        shutil.rmtree(temp)
    
    @pytest.fixture
    def app_detector(self, temp_dir):
        return AppServerDetector(base_dir=temp_dir)
    
    def test_generate_data(self, app_detector):
        result = app_detector.generate_data()
        assert result is True
        
        output_path = app_detector.raw_data_dir / "app_server_errors.csv"
        assert output_path.exists()
        
        df = pd.read_csv(output_path)
        assert 'timestamp' in df.columns
        assert 'service' in df.columns
        assert 'error_code' in df.columns
    
    def test_full_pipeline(self, app_detector):
        result = app_detector.run_pipeline()
        assert result is True


class TestSSHDetector:
    @pytest.fixture
    def temp_dir(self):
        temp = tempfile.mkdtemp()
        yield temp
        shutil.rmtree(temp)
    
    @pytest.fixture
    def ssh_detector(self, temp_dir):
        return SSHDetector(base_dir=temp_dir)
    
    def test_generate_data(self, ssh_detector):
        result = ssh_detector.generate_data()
        assert result is True
        
        output_path = ssh_detector.raw_data_dir / "ssh_failures.csv"
        assert output_path.exists()
        
        df = pd.read_csv(output_path)
        assert 'timestamp' in df.columns
        assert 'username' in df.columns
        assert 'source_ip' in df.columns
        assert 'hostname' in df.columns
    
    def test_full_pipeline(self, ssh_detector):
        result = ssh_detector.run_pipeline()
        assert result is True


class TestCorrelationEngine:
    @pytest.fixture
    def temp_dir(self):
        temp = tempfile.mkdtemp()
        yield temp
        shutil.rmtree(temp)
    
    @pytest.fixture
    def events_dir(self, temp_dir):
        events = Path(temp_dir) / "events"
        events.mkdir(parents=True, exist_ok=True)
        return events
    
    def _create_alert(self, events_dir: Path, alert_type: str, ts: datetime, source_system: str):
        alert = {
            "alert_type": alert_type,
            "timestamp": ts.isoformat(),
            "severity": "HIGH",
            "description": f"{alert_type} detected",
            "entities": {"test": "data"},
            "source_system": source_system
        }
        
        filepath = events_dir / f"{source_system}_alert_{ts.strftime('%Y%m%d%H%M%S')}.json"
        with open(filepath, 'w') as f:
            json.dump(alert, f)
    
    def test_no_events(self, events_dir):
        engine = CorrelationEngine(events_dir=str(events_dir))
        incidents = engine.run()
        assert len(incidents) == 0
    
    def test_single_event(self, events_dir):
        ts = datetime.now()
        self._create_alert(events_dir, "SSH_BruteForce_Detected", ts, "ssh")
        
        engine = CorrelationEngine(events_dir=str(events_dir))
        incidents = engine.run()
        
        assert len(incidents) == 0
    
    def test_coordinated_attack(self, events_dir):
        ts = datetime.now()
        
        self._create_alert(events_dir, "SSH_BruteForce_Detected", ts, "ssh")
        self._create_alert(events_dir, "Auth_CredentialStuffing_Detected", ts + timedelta(minutes=5), "auth")
        
        engine = CorrelationEngine(events_dir=str(events_dir))
        incidents = engine.run()
        
        assert len(incidents) >= 1
        assert any(i['incident_type'] == 'Coordinated_Attack_Detected' for i in incidents)
    
    def test_multi_vector_attack(self, events_dir):
        ts = datetime.now()
        
        self._create_alert(events_dir, "SSH_BruteForce_Detected", ts, "ssh")
        self._create_alert(events_dir, "Auth_CredentialStuffing_Detected", ts + timedelta(minutes=1), "auth")
        self._create_alert(events_dir, "Cloud_Anomaly_Detected", ts + timedelta(minutes=2), "cloud")
        
        engine = CorrelationEngine(events_dir=str(events_dir))
        incidents = engine.run()
        
        assert any(i['incident_type'] == 'Multi_Vector_Attack_Detected' for i in incidents)
    
    def test_non_correlated_event(self, events_dir):
        ts = datetime.now()
        
        self._create_alert(events_dir, "SSH_BruteForce_Detected", ts, "ssh")
        self._create_alert(events_dir, "Auth_CredentialStuffing_Detected", ts + timedelta(hours=2), "auth")
        
        engine = CorrelationEngine(events_dir=str(events_dir))
        incidents = engine.run()
        
        assert not any(i['incident_type'] == 'Coordinated_Attack_Detected' for i in incidents)


class TestBaseDetector:
    @pytest.fixture
    def temp_dir(self):
        temp = tempfile.mkdtemp()
        yield temp
        shutil.rmtree(temp)
    
    def test_aggregate_by_time(self, temp_dir):
        class DummyDetector(BaseDetector):
            name = "dummy"
            
            def generate_data(self): return True
            def clean_data(self): return True
            def train_model(self): return True
            def predict_and_alert(self): return True
        
        detector = DummyDetector(base_dir=temp_dir)
        
        df = pd.DataFrame({
            'timestamp': pd.date_range('2023-03-01', periods=100, freq='T'),
            'value': range(100)
        })
        
        result = detector._aggregate_by_time(df, freq='T')
        
        assert 'ds' in result.columns
        assert 'y' in result.columns
    
    def test_save_alert(self, temp_dir):
        class DummyDetector(BaseDetector):
            name = "dummy"
            
            def generate_data(self): return True
            def clean_data(self): return True
            def train_model(self): return True
            def predict_and_alert(self): return True
        
        detector = DummyDetector(base_dir=temp_dir)
        
        alert = {
            "alert_type": "Test_Alert",
            "timestamp": datetime.now().isoformat(),
            "severity": "HIGH"
        }
        
        filepath = detector._save_alert(alert, datetime.now())
        assert filepath is not None
        assert Path(filepath).exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
