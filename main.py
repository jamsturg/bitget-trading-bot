import json
import time
import sys
import os
import argparse

from bitget.client import BitgetClient
from bot.strategy import TradingStrategy
from bot.risk_manager import RiskManager
from bot.monitor import MonitoringSystem

class BitgetTradingBot:
    def __init__(self, config_path="config.json", debug=True):
        """
        Initialize the trading bot
        
        Parameters:
        - config_path: Path to configuration file
        - debug: Whether to enable debug output
        """
        # Load configuration
        self.config = self._load_config(config_path)
        self.debug = debug
        
        # Extract configuration parameters
        api_key = self.config["api_credentials"]["api_key"]
        api_secret = self.config["api_credentials"]["api_secret"]
        passphrase = self.config["api_credentials"]["passphrase"]
        
        risk_per_trade = self.config["trading_parameters"]["risk_per_trade"]
        leverage = self.config["trading_parameters"]["leverage"]
        max_risk_percent = self.config["trading_parameters"]["max_risk_percent"]
        max_positions = self.config["trading_parameters"]["max_positions"]
        
        trade_opportunities = self.config["trade_opportunities"]
        
        # Initialize client
        self.client = BitgetClient(api_key, api_secret, passphrase, is_futures=True, debug=debug)
        
        # Find a working API endpoint before proceeding
        if not self.find_working_endpoint():
            print("Failed to find a working Bitget API endpoint. Bot initialization incomplete.")
            return
            
        # Initialize components
        self.strategy = TradingStrategy(self.client, trade_opportunities, risk_per_trade, leverage)
        self.risk_manager = RiskManager(self.client, max_risk_percent, max_positions)
        self.monitoring = MonitoringSystem(self.client)
    
    def _load_config(self, config_path):
        """
        Load configuration from file
        
        Parameters:
        - config_path: Path to configuration file
        
        Returns:
        - Configuration as dict
        """
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
                
                # Validate credentials - make sure they're not empty
                credentials = config.get("api_credentials", {})
                if not credentials.get("api_key") or not credentials.get("api_secret") or not credentials.get("passphrase"):
                    print("WARNING: API credentials are missing or empty. Please update config.json with valid credentials.")
                
                return config
        except FileNotFoundError:
            print(f"Configuration file not found: {config_path}")
            sys.exit(1)
        except json.JSONDecodeError:
            print(f"Invalid JSON in configuration file: {config_path}")
            sys.exit(1)
    
    def find_working_endpoint(self):
        """
        Find a working API endpoint for Bitget
        
        Returns:
        - True if a working endpoint was found, False otherwise
        """
        print("\n===== Finding Working Bitget API Endpoint =====")
        return self.client.try_alternate_base_urls()
    
    def test_authentication(self):
        """
        Test authentication with Bitget API
        
        Returns:
        - True if authentication is successful, False otherwise
        """
        print("\n===== Testing Bitget API Authentication =====")
        return self.client.test_authentication()

    def start(self):
        """
        Start the trading bot
        
        Returns:
        - Trade execution results
        """
        print("\n===== Starting Bitget Trading Bot =====\n")
        
        # Test authentication first
        if not self.test_authentication():
            print("Authentication failed. Please check your API credentials.")
            return
            
        try:
            # Get account balance
            balance = self.client.get_account_balance()
            print(f"Account Balance: {balance:.2f} USDT\n")
            
            # Apply risk filters to trades
            filtered_trades = self.risk_manager.apply_risk_filters(self.strategy.trade_opportunities)
            
            if not filtered_trades:
                print("No trades passed risk filters. Bot will not execute any trades.")
                return
            
            print(f"Executing {len(filtered_trades)} trades after risk filtering...\n")
            
            # Execute filtered trades
            results = self.strategy.execute_all_trades(filtered_trades)
            
            # Start monitoring system
            self.monitoring.start_monitoring()
            
            print("\nTrading bot is now running and monitoring positions.")
            return results
        except Exception as e:
            print(f"Error starting bot: {e}")
            return None
    
    def stop(self):
        """
        Stop the trading bot
        """
        print("\nStopping trading bot...")
        self.monitoring.stop_monitoring()
        print("Trading bot stopped.")

def main():
    """
    Main function to run the trading bot
    """
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Bitget Trading Bot')
    parser.add_argument('--config', default='config.json', help='Path to configuration file')
    parser.add_argument('--debug', action='store_true', help='Enable debug output')
    parser.add_argument('--test-auth', action='store_true', help='Test API authentication and exit')
    parser.add_argument('--find-endpoints', action='store_true', help='Only find working endpoints and exit')
    args = parser.parse_args()
    
    try:
        # Initialize bot
        bot = BitgetTradingBot(config_path=args.config, debug=args.debug)
        
        # Test endpoint discovery if requested
        if args.find_endpoints:
            success = bot.find_working_endpoint()
            print(f"Endpoint discovery {'successful' if success else 'failed'}")
            sys.exit(0 if success else 1)
            
        # Test authentication if requested
        if args.test_auth:
            success = bot.test_authentication()
            print(f"Authentication test {'successful' if success else 'failed'}")
            sys.exit(0 if success else 1)
        
        # Start bot with risk management
        bot.start()
        
        # Keep main thread alive to allow monitoring
        print("\nPress Ctrl+C to stop the bot...")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        # Stop bot on Ctrl+C
        if 'bot' in locals():
            bot.stop()
    except Exception as e:
        print(f"Error running bot: {e}")
        if 'bot' in locals():
            bot.stop()
        sys.exit(1)

if __name__ == "__main__":
    main()
