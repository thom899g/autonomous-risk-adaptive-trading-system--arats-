"""
ARATS Configuration Management
Centralized configuration with environment-aware settings and validation
"""
import os
from typing import Dict, Optional, Literal
from dataclasses import dataclass, field
from pydantic import BaseModel, Field, validator
import structlog
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize structured logging
logger = structlog.get_logger(__name__)


class FirebaseConfig(BaseModel):
    """Firebase configuration with validation"""
    project_id: str = Field(..., description="Firebase Project ID")
    credentials_path: str = Field("credentials/firebase_service_account.json", 
                                 description="Path to service account JSON")
    firestore_collection: str = Field("arats_trading_data", 
                                     description="Primary Firestore collection")
    realtime_database_ref: str = Field("arats/state", 
                                      description="Realtime Database reference")
    
    @validator('credentials_path')
    def validate_credentials_path(cls, v):
        if not os.path.exists(v):
            logger.warning("Firebase credentials file not found", path=v)
            raise FileNotFoundError(f"Firebase credentials not found at {v}")
        return v


class ExchangeConfig(BaseModel):
    """Exchange connection configuration"""
    exchange_id: Literal['binance', 'coinbase', 'kraken', 'bybit'] = 'binance'
    api_key: Optional[str] = None
    api_secret: Optional[str] = None
    sandbox_mode: bool = Field(True, description="Use testnet/sandbox for development")
    rate_limit: int = Field(1000, description="Rate limit in milliseconds")
    timeout: int = Field(30000, description="Connection timeout in ms")


class RiskConfig(BaseModel):
    """Risk management configuration"""
    max_position_size_pct: float = Field(0.02, ge=0.001, le=0.1, 
                                        description="Max position as % of portfolio")
    max_daily_loss_pct: float = Field(0.05, ge=0.01, le=0.2, 
                                      description="Max daily loss percentage")
    var_confidence_level: float = Field(0.95, ge=0.9, le=0.99, 
                                       description="VaR confidence level")
    stress_test_scenarios: Dict[str, float] = Field(
        default_factory=lambda: {
            'flash_crash': -0.15,
            'volatility_spike': 0.3,
            'liquidity_crisis': -0.25
        }
    )
    stop_loss_pct: float = Field(0.02, ge=0.005, le=0.1)
    take_profit_pct: float = Field(0.04, ge=0.01, le=0.2)


class ARATSConfig(BaseModel):
    """Main ARATS configuration"""
    # Component configurations
    firebase: FirebaseConfig
    exchange: ExchangeConfig
    risk: RiskConfig
    
    # Operational settings
    data_refresh_interval: int = Field(60, description="Data refresh in seconds")
    risk_recalc_interval: int = Field(300, description="Risk recalculation in seconds")
    logging_level: Literal['DEBUG', 'INFO', 'WARNING', 'ERROR'] = 'INFO'
    
    # Model parameters
    ml_model_path: str = Field("models/risk_model.pkl", 
                              description="Path to trained ML model")
    feature_window: int = Field(50, description="Window for feature calculation")
    
    # System flags
    enable_live_trading: bool = Field(False, 
                                     description="Enable actual trade execution")
    enable_hedging: bool = Field(True, description="Enable automated hedging")
    
    class Config:
        env_prefix = 'ARATS_'
        case_sensitive = False


def load_config() -> ARATSConfig:
    """
    Load and validate configuration from environment and defaults
    
    Returns:
        ARATSConfig: Validated configuration object
    
    Raises:
        ValueError: If required environment variables are missing
    """
    try:
        # Load Firebase config from environment
        firebase_config = FirebaseConfig(
            project_id=os.getenv('FIREBASE_PROJECT_ID', 'arats-dev'),
            credentials_path=os.getenv('FIREBASE_CREDENTIALS_PATH', 
                                      'credentials/firebase_service_account.json')
        )
        
        # Load exchange config (keys should be in environment for security)
        exchange_config = ExchangeConfig(
            api_key=os.getenv('EXCHANGE_API_KEY'),
            api_secret=os.getenv('EXCHANGE_API_SECRET'),
            sandbox_mode=os.getenv('EXCHANGE_SANDBOX', 'True').lower() == 'true'
        )
        
        # Load risk config
        risk_config = RiskConfig()
        
        # Create main config
        config = ARATSConfig(
            firebase=firebase_config,
            exchange=exchange_config,
            risk=risk_config,
            data_refresh_interval=int(os.getenv('DATA_REFRESH_INTERVAL', '60')),
            risk_recalc_interval=int(os.getenv('RISK_RECALC_INTERVAL', '300')),
            logging_level=os.getenv('LOGGING_LEVEL', 'INFO'),
            enable_live_trading=os.getenv('ENABLE_LIVE_TRADING', 'False').lower() == 'true'
        )
        
        logger.info("Configuration loaded successfully", 
                   project_id=config.firebase.project_id,
                   exchange=config.exchange.exchange_id)
        return